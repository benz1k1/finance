"""
The company view (spec §117): who owns it and what it does.

* Ownership comes from the shareholding-pattern filings. A company may file more than once for
  a quarter; the newest broadcast for each quarter is the one shown.
* Website, business activities and products come from the sustainability report (BRSR), which
  only the largest listed companies file — for everyone else there is no profile row.
* Brands are not in any structured filing. They are not shown until they are extracted from
  annual reports (TODO.md, Phase 3).
"""

from typing import Any

from sqlalchemy import Connection

from equity_engine.db import row, rows
from equity_engine.universe import DEFAULT_FOCUS, in_index

# One row per (symbol, quarter): the breakdown from the newest filing for that quarter.
_PATTERN_PER_QUARTER = """
    SELECT DISTINCT ON (p.symbol, p.period_end) p.*, f.broadcast_at, f.revised
      FROM shareholding_pattern p JOIN shareholding_filing f USING (record_id)
     ORDER BY p.symbol, p.period_end, f.broadcast_at DESC
"""


def ownership_history(connection: Connection, symbol: str, limit: int) -> list[dict[str, Any]]:
    """Newest quarter first."""
    return rows(
        connection,
        f"SELECT * FROM ({_PATTERN_PER_QUARTER}) q WHERE q.symbol = :symbol ORDER BY q.period_end DESC LIMIT :limit",
        {"symbol": symbol, "limit": limit},
    )


def website_url(website: str | None) -> str | None:
    """Filings give the site as typed ("www.ril.com"); a link needs a scheme."""
    if not website:
        return None
    site = website.strip()
    return site if site.lower().startswith(("http://", "https://")) else f"https://{site}"


def profile(connection: Connection, symbol: str) -> dict[str, Any] | None:
    """The newest financial year's profile with its activities and products, or None."""
    found = row(
        connection,
        "SELECT * FROM company_profile WHERE symbol = :symbol ORDER BY fy_to DESC LIMIT 1",
        {"symbol": symbol},
    )
    if found is None:
        return None
    key = {"symbol": symbol, "fy_to": found["fy_to"]}
    found["website_url"] = website_url(found["website"])
    found["activities"] = rows(
        connection,
        "SELECT seq, main_activity, description, turnover_pct FROM company_activity "
        "WHERE symbol = :symbol AND fy_to = :fy_to ORDER BY seq",
        key,
    )
    found["products"] = rows(
        connection,
        "SELECT seq, product, nic_code, turnover_pct FROM company_product "
        "WHERE symbol = :symbol AND fy_to = :fy_to ORDER BY turnover_pct DESC NULLS LAST, seq",
        key,
    )
    return found


def deals(connection: Connection, symbol: str, limit: int) -> list[dict[str, Any]]:
    return rows(
        connection,
        """
        SELECT kind, deal_date, client_name, side, quantity, price, remarks FROM deal
         WHERE symbol = :symbol ORDER BY deal_date DESC, kind, seq LIMIT :limit
        """,
        {"symbol": symbol, "limit": limit},
    )


def ownership_screen(
    connection: Connection, order_by: str, limit: int, focus: str = DEFAULT_FOCUS
) -> list[dict[str, Any]]:
    """Every company's newest ownership breakdown, sorted by one of the percentage columns."""
    if order_by not in OWNERSHIP_COLUMNS:
        raise ValueError(f"cannot sort ownership by {order_by!r}; choose one of {sorted(OWNERSHIP_COLUMNS)}")
    return rows(
        connection,
        f"""
        SELECT q.symbol, s.name, q.period_end, q.promoter_pct, q.fii_pct, q.dii_pct, q.mutual_fund_pct,
               q.insurance_pct, q.retail_pct, q.total_shareholders
          FROM (SELECT DISTINCT ON (symbol) * FROM ({_PATTERN_PER_QUARTER}) all_quarters
                 ORDER BY symbol, period_end DESC) q
          JOIN security s ON s.nse_symbol = q.symbol
         WHERE q.{order_by} IS NOT NULL AND {in_index("s.isin", focus)}
         ORDER BY q.{order_by} DESC, q.symbol
         LIMIT :limit
        """,
        {"limit": limit},
    )


OWNERSHIP_COLUMNS = frozenset(
    {"promoter_pct", "fii_pct", "dii_pct", "mutual_fund_pct", "insurance_pct", "retail_pct"}
)
