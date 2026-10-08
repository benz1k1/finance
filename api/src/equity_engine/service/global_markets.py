"""
Global index levels (spec §120, decided 2026-10-04): five headline indexes, so a fall in Indian
stocks can be read against the world. Index levels only — no foreign stock prices, by decision.
Source: Yahoo Finance's public chart endpoint (unofficial, free). Each fetch is one JSON file per
index per calendar day under ``raw/_reference/global_index/``, kept for good like every other
download; a second run on the same day reads the file.
"""

import time
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import median
from typing import Any

import httpx
import orjson
from loguru import logger
from sqlalchemy import Connection

from equity_engine.config import RAW_DIR
from equity_engine.db import execute_many, rows, transaction

CACHE_DIR = Path(RAW_DIR) / "_reference" / "global_index"
# period1/period2 (epoch seconds) keep daily granularity; range=max silently degrades to monthly bars
CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start}&period2={end}&interval=1d"
)
HISTORY_START = datetime(1990, 1, 1, tzinfo=UTC)
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) EquityEngine/1.0"

# code -> (Yahoo symbol, name, region)
INDEXES: dict[str, tuple[str, str, str]] = {
    "SPX": ("^GSPC", "S&P 500", "United States"),
    "N225": ("^N225", "Nikkei 225", "Japan"),
    "DAX": ("^GDAXI", "DAX", "Germany"),
    "STOXX50": ("^STOXX50E", "Euro Stoxx 50", "Euro area"),
    "SSEC": ("000001.SS", "Shanghai Composite", "China"),
}
STRESS_3M_PCT = -5.0  # the world is in a drawdown when the median index is down this much over 3 months
STRESS_BELOW_200DMA = 3  # or when at least this many of the five sit below their 200-day average


def fetch(code: str, *, client: httpx.Client | None = None) -> list[tuple[date, float]]:
    """Daily closes for one index since 1990, from today's cached file or one network call."""
    symbol = INDEXES[code][0]
    path = CACHE_DIR / f"{code}_daily_{date.today():%Y%m%d}.json"
    if path.exists():
        payload = orjson.loads(path.read_bytes())
    else:
        own = client is None
        client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30)
        try:
            time.sleep(0.5)
            response = client.get(
                CHART_URL.format(
                    symbol=symbol,
                    start=int(HISTORY_START.timestamp()),
                    end=int(datetime.now(UTC).timestamp()),
                )
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if own:
                client.close()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(orjson.dumps(payload))
    result = payload["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    out = []
    for stamp, close in zip(result["timestamp"], closes, strict=False):
        if close is not None:
            out.append((datetime.fromtimestamp(stamp, UTC).date(), float(close)))
    return out


def load_all() -> dict[str, int]:
    tally: dict[str, int] = {}
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30) as client:
        for code in INDEXES:
            series = fetch(code, client=client)
            with transaction() as connection:
                execute_many(
                    connection,
                    """
                    INSERT INTO global_index_daily (index_code, trade_date, close) VALUES (:code, :d, :close)
                    ON CONFLICT (index_code, trade_date) DO UPDATE SET close = EXCLUDED.close, fetched_at = now()
                    """,
                    [{"code": code, "d": d, "close": c} for d, c in series],
                )
            tally[code] = len(series)
            logger.info(f"global index {code}: {len(series)} closes to {series[-1][0] if series else '—'}")
    return tally


_AS_OF = """
    SELECT index_code, trade_date, close,
           row_number() OVER (PARTITION BY index_code ORDER BY trade_date DESC) AS rn
      FROM global_index_daily WHERE trade_date <= :d AND trade_date > CAST(:d AS date) - 420
"""


def context(connection: Connection, as_of: date) -> dict[str, Any]:
    """What the world looked like on ``as_of``: per index the last close, 1-month and 3-month
    returns and whether it is above its 200-day average; the median 3-month return; the stress flag."""
    found = rows(connection, _AS_OF, {"d": as_of})
    by_code: dict[str, list[dict[str, Any]]] = {}
    for r in found:
        by_code.setdefault(r["index_code"], []).append(r)
    indexes: dict[str, dict[str, Any]] = {}
    for code, (symbol, name, region) in INDEXES.items():
        series = by_code.get(code, [])
        if len(series) < 64:
            continue
        last = float(series[0]["close"])
        c21, c63 = float(series[21]["close"]), float(series[63]["close"])
        window = [float(r["close"]) for r in series[:200]]
        sma200 = sum(window) / len(window) if len(window) >= 200 else None
        indexes[code] = {
            "name": name,
            "region": region,
            "date": str(series[0]["trade_date"]),
            "close": round(last, 2),
            "ret_1m_pct": round((last / c21 - 1) * 100, 2),
            "ret_3m_pct": round((last / c63 - 1) * 100, 2),
            "above_200dma": (last > sma200) if sma200 is not None else None,
        }
    threes = [i["ret_3m_pct"] for i in indexes.values()]
    below = sum(1 for i in indexes.values() if i["above_200dma"] is False)
    median_3m = round(median(threes), 2) if threes else None
    stress = bool(threes) and (median_3m <= STRESS_3M_PCT or below >= STRESS_BELOW_200DMA)
    return {"indexes": indexes, "median_3m_pct": median_3m, "below_200dma": below, "stress": stress}


def series(connection: Connection, start: date, end: date) -> dict[str, list[tuple[date, float]]]:
    found = rows(
        connection,
        "SELECT index_code, trade_date, close FROM global_index_daily WHERE trade_date BETWEEN :s AND :e ORDER BY trade_date",
        {"s": start, "e": end},
    )
    out: dict[str, list[tuple[date, float]]] = {}
    for r in found:
        out.setdefault(r["index_code"], []).append((r["trade_date"], float(r["close"])))
    return out
