"""Data health: what has been ingested, how fresh it is, and how much of it there is."""

from typing import Any

from sqlalchemy import Connection

from equity_engine.db import row, rows

_COUNTED_TABLES = (
    "security",
    "price_daily",
    "series_band_snapshot",
    "surveillance_snapshot",
    "index_constituent_snapshot",
    "deal",
    "raw_file",
)


def sources(connection: Connection) -> list[dict[str, Any]]:
    """One row per source with its newest file. ``stale`` is true when the newest file is older
    than the source's staleness threshold; a historical-only source (threshold 0) is never stale."""
    return rows(
        connection,
        """
        SELECT s.source_id, s.name, s.kind, s.owner, s.cadence, s.staleness_hours,
               f.files, f.first_date, f.last_date, f.last_fetched_at,
               r.rows_loaded AS last_rows, r.no_data_dates,
               CASE WHEN f.files IS NULL THEN 'EMPTY'
                    WHEN s.staleness_hours > 0
                         AND f.last_fetched_at < now() - make_interval(hours => s.staleness_hours) THEN 'STALE'
                    ELSE 'OK' END AS state
          FROM source_registry s
          LEFT JOIN (SELECT source_id, count(*) AS files, min(logical_date) AS first_date,
                            max(logical_date) AS last_date, max(fetched_at) AS last_fetched_at
                       FROM raw_file GROUP BY source_id) f USING (source_id)
          LEFT JOIN (SELECT i.source_id,
                            count(*) FILTER (WHERE i.status = 'NO_DATA') AS no_data_dates,
                            (array_agg(i.rows_loaded ORDER BY i.logical_date DESC)
                               FILTER (WHERE i.status = 'OK'))[1] AS rows_loaded
                       FROM ingest_run i GROUP BY i.source_id) r USING (source_id)
         ORDER BY s.kind, s.source_id
        """,
    )


def summary(connection: Connection) -> dict[str, Any]:
    """Headline numbers. Nothing here scans the price table: row and date counts come from the
    ingest log, and the date range and the newest day from the trade-date index."""
    counts = {
        table: row(connection, f"SELECT count(*) AS n FROM {table}")["n"]  # type: ignore[index]
        for table in _COUNTED_TABLES
        if table != "price_daily"
    }
    prices = row(
        connection,
        """
        SELECT (SELECT min(trade_date) FROM price_daily) AS first_trade_date,
               (SELECT max(trade_date) FROM price_daily) AS last_trade_date,
               count(*) AS trade_dates, coalesce(sum(rows_loaded), 0) AS price_rows
          FROM ingest_run
         WHERE source_id IN ('nse_bhav_udiff', 'nse_bhav_legacy') AND status = 'OK'
        """,
    )
    counts["price_daily"] = prices["price_rows"]  # type: ignore[index]
    latest = row(
        connection,
        """
        SELECT count(*) AS priced, count(deliv_qty) AS with_delivery, sum(turnover) AS turnover,
               sum(trades) AS trades
          FROM price_daily WHERE trade_date = (SELECT max(trade_date) FROM price_daily)
        """,
    )
    return {"counts": counts, "prices": prices, "latest": latest}
