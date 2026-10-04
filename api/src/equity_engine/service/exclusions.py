"""
Hard exclusions (spec §69.1): the securities removed before any engine runs.

The rules are rows in ``exclusion_rule``, dated, and are applied to the newest snapshot on or
before the asked-for date — so the same function answers "what is excluded today" and, once
snapshots have accumulated, "what was excluded on that date". NSE data only.
"""

from datetime import date
from typing import Any

from sqlalchemy import Connection

from equity_engine.db import rows

_HITS = """
    WITH rule AS (
        SELECT kind, value, reason FROM exclusion_rule
         WHERE valid_from <= :day AND (valid_to IS NULL OR valid_to >= :day)
    ),
    hit AS (
        -- Series: the series file has no ISIN, so the symbol resolves through the master.
        SELECT s.isin, s.nse_symbol AS symbol, s.name, 'Series ' || b.series AS label, r.reason
          FROM series_band_snapshot b
          JOIN rule r ON r.kind = 'NSE_SERIES' AND r.value = b.series
          JOIN security s ON s.nse_symbol = b.symbol
         WHERE b.snapshot_date = (SELECT max(snapshot_date) FROM series_band_snapshot WHERE snapshot_date <= :day)
        UNION ALL
        -- Surveillance: ASM is split into two lists and is not excluded; ESM and GSM are.
        SELECT v.isin, v.symbol, v.company_name, v.list_code || ' ' || v.stage, r.reason
          FROM surveillance_snapshot v
          JOIN rule r ON r.kind = 'NSE_SURVEILLANCE' AND r.value = v.list_code
         WHERE v.snapshot_date = (SELECT max(snapshot_date) FROM surveillance_snapshot
                                   WHERE list_code = v.list_code AND snapshot_date <= :day)
    )
"""


def excluded(connection: Connection, day: date) -> list[dict[str, Any]]:
    """One row per excluded ISIN with every reason it is excluded for."""
    return rows(
        connection,
        _HITS
        + """
        SELECT isin, min(symbol) AS symbol, min(name) AS name,
               array_agg(DISTINCT label ORDER BY label) AS labels,
               array_agg(DISTINCT reason ORDER BY reason) AS reasons
          FROM hit GROUP BY isin ORDER BY min(symbol)
        """,
        {"day": day},
    )


def counts_by_rule(connection: Connection, day: date) -> list[dict[str, Any]]:
    return rows(
        connection,
        _HITS + "SELECT reason, count(DISTINCT isin) AS securities FROM hit GROUP BY reason ORDER BY 2 DESC",
        {"day": day},
    )


def is_excluded(connection: Connection, isin: str, day: date) -> list[str]:
    """The labels a single ISIN is excluded under; empty when it is in the universe."""
    found = rows(
        connection,
        _HITS + "SELECT DISTINCT label FROM hit WHERE isin = :isin ORDER BY label",
        {"day": day, "isin": isin},
    )
    return [item["label"] for item in found]
