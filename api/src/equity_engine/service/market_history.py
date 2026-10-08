"""
Market-wide history for the charts behind the Radar: industry rotation over time (spec §28) and
breadth (§29). Rotation is recomputed from prices for the chosen dates, because past engine runs
stored no industry mapping (index snapshots exist only from Oct-2026); the mapping used is
today's, which the page says. Breadth comes straight from the regime rows the runs wrote.
"""

from datetime import date
from typing import Any

from sqlalchemy import Connection

from equity_engine.db import rows
from equity_engine.universe import in_universe

RANGES = {"1y": 365, "3y": 3 * 365, "all": None}
TARGET_POINTS = 160

_ROTATION = (
    """
    WITH dates AS (
        SELECT trade_date, row_number() OVER (ORDER BY trade_date) AS rn
          FROM (SELECT DISTINCT trade_date FROM price_daily WHERE trade_date >= :start AND trade_date <= :end_date) d
    ),
    chosen AS (SELECT trade_date FROM dates WHERE (rn - 1) % :step = 0 OR rn = (SELECT max(rn) FROM dates)),
    industry AS (
        SELECT DISTINCT ON (c.isin) c.isin, c.industry FROM index_constituent_snapshot c
         WHERE c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot)
         ORDER BY c.isin, CASE c.index_code WHEN 'nifty500' THEN 0 ELSE 1 END
    ),
    series AS (
        SELECT p.isin, p.trade_date, p.close,
               lag(p.close, 63) OVER (PARTITION BY p.isin ORDER BY p.trade_date) AS close_3m
          FROM price_daily p
         WHERE p.series IN ('EQ', 'SM') AND p.trade_date >= CAST(:start AS date) - 130 AND p.trade_date <= :end_date
           AND """
    + in_universe("p.isin")
    + """
    ),
    returns AS (
        SELECT s.trade_date, i.industry, (s.close / s.close_3m - 1) * 100 AS ret_3m
          FROM series s JOIN chosen c USING (trade_date) JOIN industry i ON i.isin = s.isin
         WHERE s.close_3m > 0 AND i.industry IS NOT NULL
    ),
    market AS (
        SELECT trade_date, percentile_cont(0.5) WITHIN GROUP (ORDER BY ret_3m) AS median_ret, count(*) AS n
          FROM returns GROUP BY trade_date
    ),
    by_industry AS (
        SELECT trade_date, industry, percentile_cont(0.5) WITHIN GROUP (ORDER BY ret_3m) AS median_ret, count(*) AS members
          FROM returns GROUP BY trade_date, industry
    )
    SELECT b.trade_date, b.industry, round(CAST(b.median_ret - m.median_ret AS numeric), 2) AS rel_3m,
           b.members, round(CAST(m.median_ret AS numeric), 2) AS market_median_3m, m.n AS market_n
      FROM by_industry b JOIN market m USING (trade_date)
     WHERE b.members >= 5
     ORDER BY b.trade_date, b.industry
"""
)

_BREADTH = """
    SELECT DISTINCT ON (m.as_of) m.as_of, m.above_200dma_pct, m.advancing_1m_pct, m.median_return_3m_pct, m.regime
      FROM market_regime m JOIN engine_run r USING (run_id)
     WHERE r.finished_at IS NOT NULL AND m.as_of >= :start AND m.as_of <= :end_date
     ORDER BY m.as_of, r.started_at DESC
"""


def window(connection: Connection, range_key: str) -> tuple[date, date, int]:
    """Start, end and the sampling step (every n-th trade date) that yields about 160 points."""
    if range_key not in RANGES:
        raise ValueError(f"unknown range {range_key!r}; one of {sorted(RANGES)}")
    bounds = rows(connection, "SELECT min(trade_date) AS first, max(trade_date) AS last FROM price_daily")[0]
    end = bounds["last"]
    days = RANGES[range_key]
    start = bounds["first"] if days is None else max(bounds["first"], end.fromordinal(end.toordinal() - days))
    sessions = rows(
        connection,
        "SELECT count(DISTINCT trade_date) AS n FROM price_daily WHERE trade_date >= :s AND trade_date <= :e",
        {"s": start, "e": end},
    )[0]["n"]
    return start, end, max(1, round(sessions / TARGET_POINTS))


def rotation(connection: Connection, start: date, end: date, step: int) -> dict[str, Any]:
    """Per industry, the series of (date, relative 3-month median return); plus the market median."""
    found = rows(connection, _ROTATION, {"start": start, "end_date": end, "step": step})
    series: dict[str, list[dict[str, Any]]] = {}
    market: dict[date, dict[str, Any]] = {}
    for r in found:
        series.setdefault(r["industry"], []).append(
            {"date": r["trade_date"], "value": float(r["rel_3m"]), "members": r["members"]}
        )
        market[r["trade_date"]] = {
            "date": r["trade_date"],
            "value": float(r["market_median_3m"]),
            "n": r["market_n"],
        }
    return {"industries": series, "market": [market[d] for d in sorted(market)]}


def breadth(connection: Connection, start: date, end: date) -> list[dict[str, Any]]:
    return rows(connection, _BREADTH, {"start": start, "end_date": end})
