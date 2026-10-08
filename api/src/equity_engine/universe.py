"""
The investable universe (decided 2026-10-03): the Nifty 500 constituents, as of the newest
constituent file loaded. Every engine, list page, stance and results download is restricted to
it; the price, deal and filing tables still hold every NSE security, because the files that feed
them are market-wide and cost nothing extra to keep.

Membership history is not loaded yet (spec §82.2), so a backtest sees today's list for every
past date. That is a known survivorship leak, recorded in TODO.md.
"""

INDEX = "nifty500"

# The UI focus (spec §119): a view filter inside the universe, chosen in the sidebar and kept in
# a cookie. Engines always run over the whole universe; the focus only narrows what pages show.
FOCUS_CHOICES = {
    "nifty50": "Nifty 50",
    "nifty100": "Nifty 100",
    "nifty200": "Nifty 200",
    "nifty500": "Nifty 500",
}
DEFAULT_FOCUS = "nifty500"


def in_index(isin_expr: str, index_code: str) -> str:
    """SQL predicate: ``isin_expr`` (a column reference) is in that index's newest constituent list."""
    if index_code not in FOCUS_CHOICES:
        raise ValueError(f"unknown index {index_code}")
    return (
        f"EXISTS (SELECT 1 FROM index_constituent_snapshot u WHERE u.isin = {isin_expr} AND u.index_code = '{index_code}'"
        f" AND u.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot WHERE index_code = '{index_code}'))"
    )


def in_universe(isin_expr: str) -> str:
    return in_index(isin_expr, INDEX)


def in_universe_as_of(isin_expr: str, as_of_param: str = ":d") -> str:
    """SQL predicate: ``isin_expr`` was in the universe on the as-of date, using the newest
    membership snapshot on or before it (yearly to Mar-2022, then the live list). Falls back to
    the earliest snapshot for dates before any. Survivorship-free to the grain of the source."""
    return (
        f"EXISTS (SELECT 1 FROM index_membership m WHERE m.isin = {isin_expr} AND m.index_code = '{INDEX}'"
        f" AND m.as_of = coalesce((SELECT max(as_of) FROM index_membership WHERE index_code = '{INDEX}' AND as_of <= CAST({as_of_param} AS date)),"
        f" (SELECT min(as_of) FROM index_membership WHERE index_code = '{INDEX}')))"
    )
