"""Read side of the master and price tables: search, one security's profile, its price history."""

from typing import Any

from sqlalchemy import Connection

from equity_engine.db import row, rows
from equity_engine.universe import DEFAULT_FOCUS, in_index, in_universe

# Each security's newest price row, found through the (isin, trade_date) primary key — a scan of
# the whole price table per page would take seconds. Market cap and issue size ride on the row
# (NSE's daily reports bundle); they are NULL when it predates that file (before Feb-2024).
_LATEST_PRICE = """
    LEFT JOIN LATERAL (
        SELECT trade_date, close, deliv_pct, market_cap, issue_size
          FROM price_daily WHERE isin = s.isin ORDER BY trade_date DESC LIMIT 1
    ) p ON true
"""


def search(
    connection: Connection, query: str, limit: int, *, universe_only: bool = True, focus: str = DEFAULT_FOCUS
) -> list[dict[str, Any]]:
    """By symbol prefix, name fragment or exact ISIN; largest market cap first. The universe
    (Nifty 500) by default; ``universe_only=False`` searches every NSE security."""
    scope = in_index("s.isin", focus) if universe_only else "true"
    return rows(
        connection,
        f"""
        SELECT s.isin, s.nse_symbol, s.name, s.series, s.segment, s.listing_date,
               p.close, p.trade_date, p.deliv_pct, p.market_cap, {in_universe("s.isin")} AS in_universe
          FROM security s {_LATEST_PRICE}
         WHERE {scope} AND (:q = '' OR s.nse_symbol ILIKE :prefix OR s.name ILIKE :fragment OR s.isin = upper(:q))
         ORDER BY p.market_cap DESC NULLS LAST, s.nse_symbol
         LIMIT :limit
        """,
        {"q": query, "prefix": f"{query}%", "fragment": f"%{query}%", "limit": limit},
    )


def by_symbol(connection: Connection, symbol: str) -> dict[str, Any] | None:
    return row(
        connection,
        f"""
        SELECT s.*, p.market_cap, p.issue_size, p.trade_date AS market_cap_date, {in_universe("s.isin")} AS in_universe
          FROM security s {_LATEST_PRICE}
         WHERE s.nse_symbol = upper(:symbol)
        """,
        {"symbol": symbol},
    )


def prices(connection: Connection, isin: str, limit: int) -> list[dict[str, Any]]:
    """Newest first. Keyed by ISIN, so a renamed symbol keeps one continuous history."""
    return rows(
        connection,
        """
        SELECT trade_date, series, symbol, open, high, low, close, prev_close, volume, turnover,
               trades, deliv_traded_qty, deliv_qty, deliv_pct, issue_size, market_cap
          FROM price_daily WHERE isin = :isin ORDER BY trade_date DESC LIMIT :limit
        """,
        {"isin": isin, "limit": limit},
    )


def profile(connection: Connection, isin: str, symbol: str) -> dict[str, Any]:
    """Everything the snapshots say about one security today: band, surveillance, indices."""
    band = row(
        connection,
        """
        SELECT series, band, remarks, snapshot_date FROM series_band_snapshot
         WHERE symbol = :symbol ORDER BY snapshot_date DESC LIMIT 1
        """,
        {"symbol": symbol},
    )
    surveillance = rows(
        connection,
        """
        SELECT v.list_code, v.stage, v.surv_desc, v.snapshot_date FROM surveillance_snapshot v
         WHERE v.isin = :isin
           AND v.snapshot_date = (SELECT max(snapshot_date) FROM surveillance_snapshot WHERE list_code = v.list_code)
         ORDER BY v.list_code
        """,
        {"isin": isin},
    )
    indices = rows(
        connection,
        """
        SELECT c.index_code, c.industry FROM index_constituent_snapshot c
         WHERE c.isin = :isin
           AND c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot WHERE index_code = c.index_code)
         ORDER BY c.index_code
        """,
        {"isin": isin},
    )
    return {"band": band, "surveillance": surveillance, "indices": indices}
