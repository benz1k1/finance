"""
Run the engines and read the ledger (spec §72, §85, §118).

``run_all`` evaluates every implemented engine against one :class:`Snapshot`, appends the signals
and a stance for every priced security to the app schema, and returns a summary. Nothing is ever
updated or deleted; readers take the newest run for a date.
"""

from datetime import UTC, date, datetime
from typing import Any

import orjson
from loguru import logger
from sqlalchemy import Connection

from equity_engine.db import execute, execute_many, row, rows, scalar, transaction
from equity_engine.engines import IMPLEMENTED
from equity_engine.engines.base import STAGES, Snapshot
from equity_engine.engines.market import MarketRegime, SectorRotation
from equity_engine.ids import new_id
from equity_engine.service import stance as stance_service
from equity_engine.universe import DEFAULT_FOCUS, in_index

# ------------------------------------------------------------------ write


def run_all(as_of: date | None, kind: str = "LIVE") -> dict[str, Any]:
    with transaction() as connection:
        day = as_of or scalar(connection, "SELECT max(trade_date) FROM price_daily")
        if day is None:
            raise ValueError("No prices loaded; nothing to evaluate")
        run_id = new_id()
        started = datetime.now(UTC)
        engines = [f"{engine.key}@{engine.version}" for engine in IMPLEMENTED.values()]
        execute(
            connection,
            "INSERT INTO engine_run (run_id, as_of, started_at, engines, kind) VALUES (:run_id, :as_of, :started_at, :engines, :kind)",
            {"run_id": run_id, "as_of": day, "started_at": started, "engines": engines, "kind": kind},
        )
        snap = Snapshot(connection, day)
        per_engine: dict[str, int] = {}
        ledger: list[dict[str, Any]] = []
        for engine in IMPLEMENTED.values():
            found = [signal for signal in engine.evaluate(snap) if signal.isin in snap.universe]
            per_engine[engine.key] = len(found)
            logger.info(f"engine {engine.key}@{engine.version} as of {day}: {len(found)} signals")
            for signal in found:
                ledger.append(
                    {
                        "signal_id": new_id(),
                        "run_id": run_id,
                        "as_of": day,
                        "isin": signal.isin,
                        "symbol": signal.symbol,
                        "engine_key": engine.key,
                        "engine_version": engine.version,
                        "signal_type": signal.signal_type,
                        "direction": signal.direction,
                        "stage": signal.stage,
                        "strength": signal.strength,
                        "percentile": signal.percentile,
                        "headline": signal.headline,
                        "evidence": orjson.dumps(signal.evidence).decode(),
                        "invalidation": signal.invalidation,
                        "price_at": signal.price_at,
                    }
                )
        execute_many(
            connection,
            """
            INSERT INTO signal (signal_id, run_id, as_of, isin, symbol, engine_key, engine_version, signal_type,
                                direction, stage, strength, percentile, headline, evidence, invalidation, price_at)
            VALUES (:signal_id, :run_id, :as_of, :isin, :symbol, :engine_key, :engine_version, :signal_type,
                    :direction, :stage, :strength, :percentile, :headline, CAST(:evidence AS jsonb), :invalidation, :price_at)
            """,
            ledger,
        )
        stances = _write_stances(connection, run_id, day, snap, ledger)
        _write_regime(connection, run_id, day, snap)
        execute(
            connection,
            "UPDATE engine_run SET finished_at = :finished_at, signals = :signals, stances = :stances WHERE run_id = :run_id",
            {"finished_at": datetime.now(UTC), "signals": len(ledger), "stances": stances, "run_id": run_id},
        )
    return {
        "run_id": run_id,
        "as_of": day,
        "signals": len(ledger),
        "stances": stances,
        "per_engine": per_engine,
    }


def _write_regime(connection: Connection, run_id: str, day: date, snap: Snapshot) -> None:
    described = MarketRegime().describe(snap)
    execute(
        connection,
        """
        INSERT INTO market_regime (run_id, as_of, regime, universe, above_200dma_pct, median_return_3m_pct,
                                   advancing_1m_pct, sectors)
        VALUES (:run_id, :as_of, :regime, :universe, :above_200dma_pct, :median_return_3m_pct,
                :advancing_1m_pct, CAST(:sectors AS jsonb))
        """,
        described | {"run_id": run_id, "sectors": orjson.dumps(SectorRotation().industries(snap)).decode()},
    )


def _write_stances(
    connection: Connection, run_id: str, day: date, snap: Snapshot, ledger: list[dict[str, Any]]
) -> int:
    by_isin: dict[str, list[dict[str, Any]]] = {}
    for signal in ledger:
        by_isin.setdefault(signal["isin"], []).append(signal)
    # Every priced security gets a stance, plus any security a gate fired on outside the EQ/SM
    # series (trade-for-trade names), so its page shows the gate rather than "not in the run".
    universe = [(p["isin"], p["symbol"], p["close"]) for p in snap.prices]
    priced = {isin for isin, _, _ in universe}
    for isin, found in by_isin.items():
        if isin not in priced:
            universe.append((isin, found[0]["symbol"], found[0]["price_at"]))
    out = []
    for isin, symbol, close in universe:
        result = stance_service.compute(by_isin.get(isin, []))
        out.append(
            {
                "stance_id": new_id(),
                "run_id": run_id,
                "as_of": day,
                "isin": isin,
                "symbol": symbol,
                "stance": result.stance,
                "conviction": result.conviction,
                "version": result.version,
                "bull_score": result.bull_score,
                "bear_score": result.bear_score,
                "bull_count": result.bull_count,
                "bear_count": result.bear_count,
                "gate": result.gate,
                "inputs": orjson.dumps(result.inputs).decode(),
                "price_at": close,
            }
        )
    execute_many(
        connection,
        """
        INSERT INTO stance (stance_id, run_id, as_of, isin, symbol, stance, conviction, version, bull_score, bear_score,
                            bull_count, bear_count, gate, inputs, price_at)
        VALUES (:stance_id, :run_id, :as_of, :isin, :symbol, :stance, :conviction, :version, :bull_score, :bear_score,
                :bull_count, :bear_count, :gate, CAST(:inputs AS jsonb), :price_at)
        """,
        out,
    )
    return len(out)


# ------------------------------------------------------------------ read

# The newest finished run (the one every page reads), or a specific date's newest run.
_LATEST_RUN = """
    SELECT * FROM engine_run WHERE finished_at IS NOT NULL AND kind = 'LIVE' AND (CAST(:as_of AS date) IS NULL OR as_of = CAST(:as_of AS date))
     ORDER BY as_of DESC, started_at DESC LIMIT 1
"""


def latest_run(connection: Connection, as_of: date | None = None) -> dict[str, Any] | None:
    return row(connection, _LATEST_RUN, {"as_of": as_of})


def previous_run(connection: Connection, run: dict[str, Any]) -> dict[str, Any] | None:
    return row(
        connection,
        "SELECT * FROM engine_run WHERE finished_at IS NOT NULL AND kind = 'LIVE' AND as_of < :as_of ORDER BY as_of DESC, started_at DESC LIMIT 1",
        {"as_of": run["as_of"]},
    )


def catalogue(connection: Connection, run: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every engine with a derived status: LIVE (implemented and in the newest run), READY (data
    present, not implemented), BLOCKED (named tables empty or absent), FRAMEWORK (not an engine)."""
    engines = rows(connection, 'SELECT * FROM engine ORDER BY "group", phase, spec_section')
    present = {
        item["table_name"]
        for item in rows(
            connection,
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()",
        )
    }
    non_empty: dict[str, bool] = {}
    for table in sorted({t for e in engines for t in e["requires"]}):
        non_empty[table] = table in present and bool(
            scalar(connection, f"SELECT EXISTS (SELECT 1 FROM {table})")
        )
    counts: dict[str, dict[str, int]] = {}
    if run:
        for item in rows(
            connection,
            "SELECT engine_key, stage, count(*) AS n FROM signal WHERE run_id = :run_id GROUP BY engine_key, stage",
            {"run_id": run["run_id"]},
        ):
            counts.setdefault(item["engine_key"], {})[item["stage"]] = item["n"]
    for engine in engines:
        missing = [t for t in engine["requires"] if not non_empty.get(t)]
        implemented = engine["engine_key"] in IMPLEMENTED
        engine["implemented"] = implemented
        engine["version"] = IMPLEMENTED[engine["engine_key"]].version if implemented else None
        engine["missing"] = missing
        engine["by_stage"] = counts.get(engine["engine_key"], {})
        engine["signals"] = sum(engine["by_stage"].values())
        if implemented:
            engine["status"] = "LIVE" if run else "READY"
        elif engine["engine_key"] == "stance" or engine["group"] == "FRAMEWORK":
            engine["status"] = "FRAMEWORK"
        elif missing:
            engine["status"] = "BLOCKED"
        else:
            engine["status"] = "READY"
    return engines


def engine_by_key(connection: Connection, key: str) -> dict[str, Any] | None:
    return row(connection, "SELECT * FROM engine WHERE engine_key = :k", {"k": key})


def radar(
    connection: Connection, run: dict[str, Any], previous: dict[str, Any] | None, focus: str = DEFAULT_FOCUS
) -> list[dict[str, Any]]:
    """One tile per engine with signals in the run, stage counts, and the change in total since
    the previous run."""
    tiles = rows(
        connection,
        """
        SELECT e.engine_key, e.name, e.radar, e."group", e.spec_section, s.direction, s.stage, count(*) AS n
          FROM signal s JOIN engine e USING (engine_key)
         WHERE s.run_id = :run_id AND """
        + in_index("s.isin", focus)
        + """ GROUP BY 1, 2, 3, 4, 5, 6, 7
        """,
        {"run_id": run["run_id"]},
    )
    before = {}
    if previous:
        for item in rows(
            connection,
            "SELECT engine_key, direction, count(*) AS n FROM signal s WHERE run_id = :run_id AND "
            + in_index("s.isin", focus)
            + " GROUP BY 1, 2",
            {"run_id": previous["run_id"]},
        ):
            before[(item["engine_key"], item["direction"])] = item["n"]
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in tiles:
        key = (item["engine_key"], item["direction"])
        tile = grouped.setdefault(
            key,
            {
                "engine_key": item["engine_key"],
                "name": item["name"],
                "direction": item["direction"],
                "group": item["group"],
                "spec_section": item["spec_section"],
                "total": 0,
                "by_stage": dict.fromkeys(STAGES, 0),
                "change": -before.get(key, 0),
            },
        )
        tile["by_stage"][item["stage"]] += item["n"]
        tile["total"] += item["n"]
        tile["change"] += item["n"]
    return sorted(grouped.values(), key=lambda t: (t["direction"], -t["total"]))


def regime(connection: Connection, run: dict[str, Any]) -> dict[str, Any] | None:
    """The regime row written with the run (§29), sectors ranked by relative 3-month return."""
    found = row(connection, "SELECT * FROM market_regime WHERE run_id = :run_id", {"run_id": run["run_id"]})
    if found is None:
        return None
    sectors = found["sectors"] if isinstance(found["sectors"], dict) else orjson.loads(found["sectors"])
    found["sectors"] = sorted(sectors.values(), key=lambda i: -i["rel_3m"])
    for key in ("above_200dma_pct", "median_return_3m_pct", "advancing_1m_pct"):
        if found[key] is not None:
            found[key] = float(found[key])
    return found


FEED_FILTERS = ("engine", "stage", "direction", "q")


def feed(
    connection: Connection,
    run: dict[str, Any],
    engine: str,
    stage: str,
    direction: str,
    q: str,
    limit: int,
    focus: str = DEFAULT_FOCUS,
) -> list[dict[str, Any]]:
    return rows(
        connection,
        """
        SELECT s.*, e.name AS engine_name, e.radar
          FROM signal s JOIN engine e USING (engine_key)
         WHERE s.run_id = :run_id AND """
        + in_index("s.isin", focus)
        + """
           AND (:engine = '' OR s.engine_key = :engine)
           AND (:stage = '' OR s.stage = :stage)
           AND (:direction = '' OR s.direction = :direction)
           AND (:q = '' OR s.symbol ILIKE :prefix)
         ORDER BY CASE s.stage WHEN 'CONFIRMED' THEN 0 WHEN 'EMERGING' THEN 1 ELSE 2 END, s.strength DESC, s.symbol
         LIMIT :limit
        """,
        {
            "run_id": run["run_id"],
            "engine": engine,
            "stage": stage,
            "direction": direction,
            "q": q,
            "prefix": f"{q}%",
            "limit": limit,
        },
    )


def engine_signals(connection: Connection, run: dict[str, Any], key: str, limit: int) -> list[dict[str, Any]]:
    return feed(connection, run, key, "", "", "", limit)


def for_security(connection: Connection, run: dict[str, Any], isin: str) -> list[dict[str, Any]]:
    return rows(
        connection,
        """
        SELECT s.*, e.name AS engine_name, e."group", e.radar FROM signal s JOIN engine e USING (engine_key)
         WHERE s.run_id = :run_id AND s.isin = :isin
         ORDER BY CASE s.stage WHEN 'CONFIRMED' THEN 0 WHEN 'EMERGING' THEN 1 ELSE 2 END, s.strength DESC
        """,
        {"run_id": run["run_id"], "isin": isin},
    )


def stance_for(connection: Connection, run: dict[str, Any], isin: str) -> dict[str, Any] | None:
    return row(
        connection,
        "SELECT * FROM stance WHERE run_id = :run_id AND isin = :isin",
        {"run_id": run["run_id"], "isin": isin},
    )


def stance_history(connection: Connection, isin: str, limit: int) -> list[dict[str, Any]]:
    """Newest first, one row per as-of date — the latest finished run of that date speaks for it,
    so several runs on one day (a re-run, a backtest shard) do not repeat the same entry."""
    return rows(
        connection,
        """
        SELECT DISTINCT ON (st.as_of)
               st.as_of, st.stance, st.conviction, st.bull_score, st.bear_score, st.gate, st.price_at
          FROM stance st JOIN engine_run r USING (run_id)
         WHERE st.isin = :isin AND r.finished_at IS NOT NULL
         ORDER BY st.as_of DESC, r.started_at DESC LIMIT :limit
        """,
        {"isin": isin, "limit": limit},
    )


def stance_changes(
    connection: Connection,
    run: dict[str, Any],
    previous: dict[str, Any] | None,
    limit: int,
    focus: str = DEFAULT_FOCUS,
) -> list[dict[str, Any]]:
    """Securities whose stance differs from the previous run — the feed's own event type."""
    if previous is None:
        return []
    return rows(
        connection,
        """
        SELECT now.symbol, now.isin, now.stance, now.conviction, was.stance AS was_stance, was.conviction AS was_conviction
          FROM stance now JOIN stance was ON was.isin = now.isin AND was.run_id = :previous
         WHERE now.run_id = :run_id AND now.stance <> was.stance AND """
        + in_index("now.isin", focus)
        + """
         ORDER BY now.symbol LIMIT :limit
        """,
        {"run_id": run["run_id"], "previous": previous["run_id"], "limit": limit},
    )


def stance_counts(
    connection: Connection, run: dict[str, Any], focus: str = DEFAULT_FOCUS
) -> list[dict[str, Any]]:
    return rows(
        connection,
        "SELECT stance, conviction, count(*) AS n FROM stance st WHERE run_id = :run_id AND "
        + in_index("st.isin", focus)
        + " GROUP BY 1, 2 ORDER BY 1, 2",
        {"run_id": run["run_id"]},
    )


def stance_by_symbol(
    connection: Connection, run: dict[str, Any] | None, symbols: list[str]
) -> dict[str, dict[str, Any]]:
    """The stance column for a list page; empty when no run exists."""
    if run is None or not symbols:
        return {}
    found = rows(
        connection,
        "SELECT symbol, stance, conviction, gate FROM stance WHERE run_id = :run_id AND symbol = ANY(:symbols)",
        {"run_id": run["run_id"], "symbols": symbols},
    )
    return {item["symbol"]: item for item in found}


# ------------------------------------------------------------------ screener (§75, option 5)

SCREEN_STANCES = ("LONG", "LEAN_LONG", "NEUTRAL", "LEAN_SHORT", "SHORT", "AVOID")
SCREEN_CONVICTIONS = ("LOW", "MEDIUM", "HIGH")


def screen(
    connection: Connection,
    run: dict[str, Any],
    stances: list[str],
    convictions: list[str],
    has: list[str],
    has_not: list[str],
    confirmed_only: bool,
    min_mcap_crore: float | None,
    index_code: str,
    limit: int,
    focus: str = DEFAULT_FOCUS,
) -> list[dict[str, Any]]:
    """Securities from the run's stance table filtered by stance, conviction, engines that fired
    (or did not), market cap and index membership. Chips in the UI, one SQL here."""
    return rows(
        connection,
        """
        WITH universe AS (
            SELECT st.isin, st.symbol, st.stance, st.conviction, st.bull_score, st.bear_score,
                   st.bull_count, st.bear_count, st.gate, st.price_at
              FROM stance st WHERE st.run_id = :run_id AND """
        + in_index("st.isin", focus)
        + """
               AND (cardinality(CAST(:stances AS text[])) = 0 OR st.stance = ANY(:stances))
               AND (cardinality(CAST(:convictions AS text[])) = 0 OR st.conviction = ANY(:convictions))
        ),
        fired AS (
            SELECT isin, array_agg(DISTINCT engine_key) AS engines,
                   array_agg(DISTINCT engine_key) FILTER (WHERE stage = 'CONFIRMED') AS confirmed
              FROM signal WHERE run_id = :run_id GROUP BY isin
        )
        SELECT u.*, s.name, p.market_cap, p.close, coalesce(f.engines, '{}') AS engines,
               (SELECT array_agg(DISTINCT c.index_code) FROM index_constituent_snapshot c
                 WHERE c.isin = u.isin AND c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot)) AS indices
          FROM universe u
          JOIN security s ON s.isin = u.isin
          LEFT JOIN fired f ON f.isin = u.isin
          LEFT JOIN LATERAL (SELECT market_cap, close FROM price_daily WHERE isin = u.isin AND trade_date = :as_of LIMIT 1) p ON true
         WHERE (cardinality(CAST(:has AS text[])) = 0
                OR (CASE WHEN CAST(:confirmed_only AS boolean) THEN coalesce(f.confirmed, '{}') ELSE coalesce(f.engines, '{}') END) @> CAST(:has AS text[]))
           AND (cardinality(CAST(:has_not AS text[])) = 0 OR NOT (coalesce(f.engines, '{}') && CAST(:has_not AS text[])))
           AND (CAST(:min_mcap AS numeric) IS NULL OR p.market_cap >= CAST(:min_mcap AS numeric) * 10000000)
           AND (:index_code = '' OR EXISTS (SELECT 1 FROM index_constituent_snapshot c WHERE c.isin = u.isin AND c.index_code = :index_code
                                             AND c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot WHERE index_code = :index_code)))
         ORDER BY CASE u.stance WHEN 'LONG' THEN 0 WHEN 'LEAN_LONG' THEN 1 WHEN 'NEUTRAL' THEN 2 WHEN 'LEAN_SHORT' THEN 3 WHEN 'SHORT' THEN 4 ELSE 5 END,
                  CASE u.conviction WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 WHEN 'LOW' THEN 2 ELSE 3 END,
                  p.market_cap DESC NULLS LAST
         LIMIT :limit
        """,
        {
            "run_id": run["run_id"],
            "as_of": run["as_of"],
            "stances": stances,
            "convictions": convictions,
            "has": has,
            "has_not": has_not,
            "confirmed_only": confirmed_only,
            "min_mcap": min_mcap_crore,
            "index_code": index_code,
            "limit": limit,
        },
    )


def index_codes(connection: Connection) -> list[str]:
    return [
        item["index_code"]
        for item in rows(connection, "SELECT DISTINCT index_code FROM index_constituent_snapshot ORDER BY 1")
    ]
