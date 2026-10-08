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


_OWNERSHIP_VALUE = (
    """
    WITH latest AS (
        SELECT DISTINCT ON (p.symbol) p.symbol, p.period_end, p.promoter_pct, p.fii_pct, p.dii_pct, p.mutual_fund_pct,
               p.insurance_pct, p.retail_pct, p.hni_pct, p.public_pct
          FROM shareholding_pattern p JOIN shareholding_filing f USING (record_id)
         ORDER BY p.symbol, p.period_end DESC, f.broadcast_at DESC
    ),
    mcap AS (
        SELECT DISTINCT ON (pd.isin) pd.isin, pd.market_cap FROM price_daily pd
         WHERE pd.market_cap IS NOT NULL AND pd.series IN ('EQ', 'SM') AND """
    + in_index("pd.isin", "nifty500")
    + """
         ORDER BY pd.isin, pd.trade_date DESC
    )
    SELECT l.*, m.market_cap FROM latest l JOIN security s ON s.nse_symbol = l.symbol JOIN mcap m ON m.isin = s.isin
"""
)

OWNER_GROUPS: tuple[tuple[str, str, str], ...] = (
    # key, label, colour class — fixed order so the bar reads the same every day
    ("promoter", "Promoters", "bg-neutral"),
    ("fii", "FII / FPI", "bg-secondary"),
    ("mutual_fund", "Mutual funds", "bg-primary"),
    ("insurance", "Insurance", "bg-accent"),
    ("other_dii", "Other DII", "bg-info"),
    ("retail", "Retail", "bg-success"),
    ("hni", "HNI", "bg-warning"),
    ("other", "Other public", "bg-base-300"),
)


def ownership_value(connection: Connection) -> dict[str, Any]:
    """What each investor class holds across the universe, in rupees: the newest shareholding
    percentages of every company times its newest market cap, summed. Other DII is DII less mutual
    funds and insurers (pension, AIF, banks, government); other public is what remains of the public
    float after FII, DII, retail and HNI (NRIs, bodies corporate, trusts, employee trusts)."""
    totals = {key: 0.0 for key, _, _ in OWNER_GROUPS}
    companies, newest = 0, None
    for r in rows(connection, _OWNERSHIP_VALUE):
        cap = float(r["market_cap"])
        pct = {
            k: float(r[f"{k}_pct"] or 0)
            for k in ("promoter", "fii", "dii", "mutual_fund", "insurance", "retail", "hni", "public")
        }
        totals["promoter"] += cap * pct["promoter"] / 100
        totals["fii"] += cap * pct["fii"] / 100
        totals["mutual_fund"] += cap * pct["mutual_fund"] / 100
        totals["insurance"] += cap * pct["insurance"] / 100
        totals["other_dii"] += cap * max(0.0, pct["dii"] - pct["mutual_fund"] - pct["insurance"]) / 100
        totals["retail"] += cap * pct["retail"] / 100
        totals["hni"] += cap * pct["hni"] / 100
        totals["other"] += (
            cap * max(0.0, pct["public"] - pct["fii"] - pct["dii"] - pct["retail"] - pct["hni"]) / 100
        )
        companies += 1
        newest = max(newest, r["period_end"]) if newest else r["period_end"]
    grand = sum(totals.values())
    groups = [
        {
            "key": key,
            "label": label,
            "colour": colour,
            "value": totals[key],
            "share_pct": (totals[key] / grand * 100) if grand else 0.0,
        }
        for key, label, colour in OWNER_GROUPS
    ]
    return {"groups": groups, "total": grand, "companies": companies, "newest_quarter": newest}


def psu_tags(connection: Connection) -> dict[str, dict[str, Any]]:
    """Government-ownership tag per symbol from the seeded list (resources/seed/psu.csv)."""
    return {
        r["symbol"]: r
        for r in rows(connection, "SELECT symbol, name, owner, category, parent, note FROM psu")
    }


def psu_tag(connection: Connection, symbol: str) -> dict[str, Any] | None:
    found = rows(
        connection,
        "SELECT symbol, name, owner, category, parent, note FROM psu WHERE symbol = :s",
        {"s": symbol},
    )
    return found[0] if found else None
