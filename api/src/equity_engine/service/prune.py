"""
Keep the project to the universe (spec §119): delete every database row and every per-company
cache file that belongs to a company outside the newest Nifty 500 constituent list.

Database: both schemas, children before parents, one transaction per table. Market-wide tables
with no company (source_registry, raw_file for market-wide files, ingest_run, exclusion_rule,
engine, engine_run, market_regime) stay.

Cache: only files that belong to one company go — results XBRL, shareholding XBRL, BRSR XBRL,
announcement PDFs. Market-wide files (price files, bundles, monthly lists) are shared and stay.
The file list is computed from the database *before* the rows are deleted, because the rows are
the only map from a file to its company. Deleting cached files breaks the project's standing
rule; this was run once, on 2026-10-03, at the user's instruction, as a one-time clean-up when
the universe was narrowed. The rule still stands; do not run this casually.

Run through ``python ingest.py prune``; it asks for the index code before deleting.
"""

from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import Connection

from equity_engine.config import RAW_DIR
from equity_engine.db import engine, execute, rows, transaction
from equity_engine.sources import bronze
from equity_engine.sources.registry import BY_ID
from equity_engine.universe import in_universe


def _symbol_in_universe(table: str) -> str:
    return (
        f"EXISTS (SELECT 1 FROM security s WHERE s.nse_symbol = {table}.symbol AND {in_universe('s.isin')})"
    )


# Every deletion, children first: (table, WHERE clause selecting the rows to delete).
def _plan() -> list[tuple[str, str]]:
    def by_symbol(table: str) -> str:
        return f"NOT {_symbol_in_universe(table)}"

    def via(child_key: str, parent: str) -> str:
        return f"{child_key} IN (SELECT {child_key} FROM {parent} WHERE NOT {_symbol_in_universe(parent)})"

    return [
        ("fin_fact", via("filing_id", "fin_filing")),
        ("fin_quarter", via("filing_id", "fin_filing")),
        ("results_xbrl_skip", via("filing_id", "fin_filing")),
        ("document_extraction", via("document_id", "document")),
        ("document_text", via("document_id", "document")),
        ("company_brand", by_symbol("company_brand")),
        ("shareholding_pattern", by_symbol("shareholding_pattern")),
        ("company_product", by_symbol("company_product")),
        ("company_activity", by_symbol("company_activity")),
        ("fin_filing", by_symbol("fin_filing")),
        ("document", by_symbol("document")),
        ("shareholding_filing", by_symbol("shareholding_filing")),
        ("company_profile", by_symbol("company_profile")),
        ("deal", by_symbol("deal")),
        ("board_meeting", by_symbol("board_meeting")),
        ("credit_rating", by_symbol("credit_rating")),
        ("derivative_oi", by_symbol("derivative_oi")),
        ("corporate_action", by_symbol("corporate_action")),
        ("circuit_hit", by_symbol("circuit_hit")),
        ("series_band_snapshot", by_symbol("series_band_snapshot")),
        ("price_daily", f"NOT {in_universe('price_daily.isin')}"),
        ("surveillance_snapshot", f"NOT {in_universe('surveillance_snapshot.isin')}"),
        ("index_constituent_snapshot", f"NOT {in_universe('index_constituent_snapshot.isin')}"),
        (
            "signal_outcome",
            f"signal_id IN (SELECT signal_id FROM signal WHERE NOT {in_universe('signal.isin')})",
        ),
        (
            "stance_outcome",
            f"stance_id IN (SELECT stance_id FROM stance WHERE NOT {in_universe('stance.isin')})",
        ),
        ("signal", f"NOT {in_universe('signal.isin')}"),
        ("stance", f"NOT {in_universe('stance.isin')}"),
        ("security", f"NOT {in_universe('security.isin')}"),
    ]


def counts(connection: Connection) -> dict[str, int]:
    return {
        table: rows(connection, f"SELECT count(*) AS n FROM {table} WHERE {where}")[0]["n"]
        for table, where in _plan()
    }


def cache_files_outside(connection: Connection) -> list[Path]:
    """Per-company cached files of companies outside the universe, whether or not registered."""
    paths: set[Path] = set()
    for item in rows(
        connection,
        f"SELECT period_end, xbrl_url FROM fin_filing WHERE xbrl_url IS NOT NULL AND NOT {_symbol_in_universe('fin_filing')}",
    ):
        paths.add(bronze.document_path(BY_ID["nse_results_xbrl"], item["period_end"].year, item["xbrl_url"]))
    for item in rows(
        connection,
        f"SELECT period_end, xbrl_url FROM shareholding_filing WHERE xbrl_url IS NOT NULL AND NOT {_symbol_in_universe('shareholding_filing')}",
    ):
        paths.add(
            bronze.document_path(BY_ID["nse_shareholding_xbrl"], item["period_end"].year, item["xbrl_url"])
        )
    for item in rows(
        connection,
        f"SELECT broadcast_at, attachment_url FROM document WHERE attachment_url LIKE '%.pdf' AND NOT {_symbol_in_universe('document')}",
    ):
        try:
            paths.add(
                bronze.document_path(
                    BY_ID["nse_announcement_pdf"], item["broadcast_at"].year, item["attachment_url"]
                )
            )
        except ValueError:
            continue
    for item in rows(
        connection,
        f"SELECT r.path FROM company_profile p JOIN raw_file r USING (raw_id) WHERE NOT {_symbol_in_universe('p')}",
    ):
        paths.add(RAW_DIR / item["path"])
    return sorted(path for path in paths if path.is_file())


def prune(delete_cache: bool = True) -> dict[str, Any]:
    with transaction() as connection:
        files = cache_files_outside(connection) if delete_cache else []
    deleted: dict[str, int] = {}
    for table, where in _plan():
        with transaction() as connection:
            deleted[table] = execute(connection, f"DELETE FROM {table} WHERE {where}")
    removed, freed = 0, 0
    if files:
        relative = [str(path.relative_to(RAW_DIR)) for path in files]
        with transaction() as connection:
            execute(connection, "DELETE FROM raw_file WHERE path = ANY(:paths)", {"paths": relative})
        for path in files:
            freed += path.stat().st_size
            path.unlink()
            removed += 1
        logger.info(f"prune: removed {removed} cached files, {freed / 1e6:.0f} MB")
    deleted["cache_files"] = removed
    deleted["cache_mb"] = int(freed / 1e6)
    return deleted


def vacuum() -> None:
    """Return the space; VACUUM cannot run inside a transaction."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        for table, _ in _plan():
            connection.exec_driver_sql(f"VACUUM (ANALYZE) {table}")
        connection.exec_driver_sql("VACUUM (ANALYZE) raw_file")
