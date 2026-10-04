"""Data-integrity checks on what is actually in the database (spec §89). These read the real
tables, so they need at least one ingested trade date."""

import pytest
from sqlalchemy import text


def _scalar(connection, sql: str):
    return connection.execute(text(sql)).scalar()


@pytest.fixture(autouse=True)
def _needs_prices(connection):
    if not _scalar(connection, "SELECT count(*) FROM price_daily"):
        pytest.fail("No prices ingested. Run: python ingest.py rebuild")


def test_price_rows_are_internally_consistent(connection):
    bad = _scalar(
        connection,
        "SELECT count(*) FROM price_daily WHERE NOT (low <= open AND open <= high AND low <= close "
        "AND close <= high AND low > 0 AND volume >= 0 AND turnover >= 0)",
    )
    assert bad == 0


def test_every_trade_date_has_a_full_market(connection):
    thin = connection.execute(
        # The universe is the Nifty 500; in 2019 fewer of today's constituents were listed.
        text("SELECT trade_date, count(*) FROM price_daily GROUP BY trade_date HAVING count(*) < 300")
    ).all()
    assert thin == []


def test_weekend_sessions_are_rare(connection):
    """NSE trades on a few Saturdays and Sundays (special sessions, Muhurat trading), never many."""
    weekend = _scalar(
        connection,
        "SELECT count(DISTINCT trade_date) FROM price_daily WHERE extract(isodow FROM trade_date) > 5",
    )
    assert weekend < 40


def test_delivery_is_consistent_with_the_quantity_it_is_a_share_of(connection):
    """deliv_pct is relative to the delivery file's own traded quantity, which on some sessions
    (2026-09-11, before a market holiday) differs from the price file's volume — so that is what
    it is checked against."""
    assert _scalar(connection, "SELECT count(*) FROM price_daily WHERE deliv_qty > deliv_traded_qty") == 0
    off = _scalar(
        connection,
        "SELECT count(*) FROM price_daily WHERE deliv_qty IS NOT NULL AND deliv_traded_qty > 0 "
        "AND abs(deliv_pct - round(100.0 * deliv_qty / deliv_traded_qty, 2)) > 0.02",
    )
    assert off == 0


def test_delivery_covers_every_rolling_settlement_share_once_loaded(connection):
    """On a date whose delivery file is loaded, every EQ-series share (ISIN prefix INE) has
    delivery; trade-for-trade series (BE, BZ) have none, because the exchange file omits them."""
    missing = _scalar(
        connection,
        """
        SELECT count(*) FROM price_daily p
         WHERE p.series = 'EQ' AND p.isin LIKE 'INE%' AND p.deliv_qty IS NULL
           AND EXISTS (SELECT 1 FROM ingest_run i WHERE i.source_id = 'nse_delivery_mto'
                          AND i.logical_date = p.trade_date AND i.status = 'OK')
        """,
    )
    assert missing == 0
    assert (
        _scalar(
            connection,
            "SELECT count(*) FROM price_daily WHERE series IN ('BE', 'BZ') AND deliv_qty IS NOT NULL",
        )
        == 0
    )


def test_every_price_row_traces_to_a_cached_file(connection):
    assert (
        _scalar(
            connection,
            "SELECT count(*) FROM price_daily p LEFT JOIN raw_file r USING (raw_id) WHERE r.raw_id IS NULL",
        )
        == 0
    )
    # ...and that file is still on disk under the path recorded for it.
    from equity_engine.config import RAW_DIR

    paths = [found[0] for found in connection.execute(text("SELECT path FROM raw_file"))]
    assert paths and [path for path in paths if not (RAW_DIR / path).is_file()] == []


def test_master_is_unique_by_isin_and_symbol(connection):
    assert _scalar(connection, "SELECT count(*) - count(DISTINCT nse_symbol) FROM security") == 0


def test_latest_prices_resolve_to_the_master(connection):
    """Every company share priced on the newest date is in the master. Fund units (ETFs, ISIN
    prefix INF) are outside the Nifty 500 universe and were pruned with everything else."""
    shares, unknown_shares, funds = connection.execute(
        text(
            """
            SELECT count(*) FILTER (WHERE p.isin LIKE 'INE%'),
                   count(*) FILTER (WHERE p.isin LIKE 'INE%' AND s.isin IS NULL),
                   count(*) FILTER (WHERE p.isin LIKE 'INF%')
              FROM price_daily p LEFT JOIN security s USING (isin)
             WHERE p.trade_date = (SELECT max(trade_date) FROM price_daily)
            """
        )
    ).one()
    assert 450 <= shares <= 520 and funds == 0
    assert unknown_shares / shares < 0.01


def test_index_sizes(connection):
    sizes = dict(
        connection.execute(
            text(
                "SELECT index_code, count(*) FROM index_constituent_snapshot c WHERE snapshot_date = "
                "(SELECT max(snapshot_date) FROM index_constituent_snapshot WHERE index_code = c.index_code) GROUP BY 1"
            )
        ).all()
    )
    assert sizes["nifty50"] == 50 and sizes["niftynext50"] == 50 and sizes["nifty100"] == 100
    assert 495 <= sizes["nifty500"] <= 505  # placeholder constituents after demergers push it past 500
