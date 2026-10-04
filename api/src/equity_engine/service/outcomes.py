"""
Outcome marking (spec §72) and the backtester (spec §86).

``mark`` finds every signal and stance whose horizon has elapsed and has not been marked, and
writes its return, excess return over the universe median for the same window, and maximum
drawdown. Nothing is ever re-marked. ``backtest`` replays the engine run over past as-of dates;
the Snapshot is point in time by construction (filings by broadcast time, prices by trade date),
with one known leak recorded in the spec: exclusion and surveillance snapshots exist only from
Oct-2026, so before that the investability gate sees today's lists.
"""

from collections import Counter
from datetime import date
from typing import Any

from loguru import logger
from sqlalchemy import Connection

from equity_engine.db import execute_many, rows, scalar, transaction
from equity_engine.service import signals as signal_service
from equity_engine.service import stance as stance_service

HORIZONS = (21, 63, 126, 252, 504)  # trading sessions: 1, 3, 6, 12, 24 months

# The price path for one security after its as-of date, in trading rows.
_PATH = """
    SELECT p.trade_date, p.close
      FROM price_daily p
     WHERE p.isin = :isin AND p.trade_date > :as_of
     ORDER BY p.trade_date LIMIT :n
"""

# Universe median return between two trade dates, over every security priced on both.
_UNIVERSE_RETURN = """
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY (b.close / a.close - 1) * 100)
      FROM price_daily a JOIN price_daily b ON b.isin = a.isin AND b.series = a.series
     WHERE a.trade_date = :start AND b.trade_date = :end_date AND a.series IN ('EQ', 'SM') AND a.close > 0
"""


def _trade_dates(connection: Connection) -> list[date]:
    return [
        item["trade_date"]
        for item in rows(connection, "SELECT DISTINCT trade_date FROM price_daily ORDER BY 1")
    ]


def _window_end(dates: list[date], as_of: date, horizon: int) -> date | None:
    """The trade date ``horizon`` sessions after as_of, or None if it has not happened yet."""
    later = [d for d in dates if d > as_of]
    return later[horizon - 1] if len(later) >= horizon else None


def mark() -> Counter[str]:
    tally: Counter[str] = Counter()
    with transaction() as connection:
        dates = _trade_dates(connection)
        runs = rows(
            connection, "SELECT run_id, as_of FROM engine_run WHERE finished_at IS NOT NULL ORDER BY as_of"
        )
    for run in runs:
        for horizon in HORIZONS:
            end = _window_end(dates, run["as_of"], horizon)
            if end is not None:
                tally += _mark_run(run, horizon, end)
    return tally


def _mark_run(run: dict[str, Any], horizon: int, end: date) -> Counter[str]:
    tally: Counter[str] = Counter()
    with transaction() as connection:
        start = scalar(
            connection, "SELECT max(trade_date) FROM price_daily WHERE trade_date <= :d", {"d": run["as_of"]}
        )
        universe = scalar(connection, _UNIVERSE_RETURN, {"start": start, "end_date": end})
        if universe is None:
            return tally
        universe = float(universe)
        pending_signals = rows(
            connection,
            """
            SELECT s.signal_id, s.isin, s.price_at FROM signal s
             WHERE s.run_id = :run_id AND s.price_at IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM signal_outcome o WHERE o.signal_id = s.signal_id AND o.horizon_days = :h)
            """,
            {"run_id": run["run_id"], "h": horizon},
        )
        pending_stances = rows(
            connection,
            """
            SELECT st.stance_id, st.isin, st.price_at FROM stance st
             WHERE st.run_id = :run_id AND st.price_at IS NOT NULL AND st.stance <> 'NEUTRAL'
               AND NOT EXISTS (SELECT 1 FROM stance_outcome o WHERE o.stance_id = st.stance_id AND o.horizon_days = :h)
            """,
            {"run_id": run["run_id"], "h": horizon},
        )
        if not pending_signals and not pending_stances:
            return tally
        paths: dict[str, list[dict[str, Any]]] = {}
        for isin in {item["isin"] for item in pending_signals + pending_stances}:
            paths[isin] = rows(connection, _PATH, {"isin": isin, "as_of": run["as_of"], "n": horizon})
        signal_rows, stance_rows = [], []
        for item in pending_signals:
            measured = _measure(paths.get(item["isin"], []), float(item["price_at"]), horizon, universe)
            if measured:
                signal_rows.append(
                    {
                        "signal_id": item["signal_id"],
                        "horizon_days": horizon,
                        "as_of": run["as_of"],
                        "price_at": item["price_at"],
                    }
                    | measured
                )
        for item in pending_stances:
            measured = _measure(paths.get(item["isin"], []), float(item["price_at"]), horizon, universe)
            if measured:
                stance_rows.append(
                    {"stance_id": item["stance_id"], "horizon_days": horizon, "as_of": run["as_of"]}
                    | measured
                )
        execute_many(
            connection,
            """
            INSERT INTO signal_outcome (signal_id, horizon_days, as_of, end_date, price_at, price_end, return_pct, excess_pct, max_drawdown_pct)
            VALUES (:signal_id, :horizon_days, :as_of, :end_date, :price_at, :price_end, :return_pct, :excess_pct, :max_drawdown_pct)
            ON CONFLICT DO NOTHING
            """,
            signal_rows,
        )
        execute_many(
            connection,
            """
            INSERT INTO stance_outcome (stance_id, horizon_days, as_of, end_date, return_pct, excess_pct, max_drawdown_pct)
            VALUES (:stance_id, :horizon_days, :as_of, :end_date, :return_pct, :excess_pct, :max_drawdown_pct)
            ON CONFLICT DO NOTHING
            """,
            stance_rows,
        )
    tally[f"signals@{horizon}"] += len(signal_rows)
    tally[f"stances@{horizon}"] += len(stance_rows)
    return tally


def _measure(
    path: list[dict[str, Any]], price_at: float, horizon: int, universe_return: float
) -> dict[str, Any] | None:
    if len(path) < horizon or price_at <= 0:
        return None  # delisted or suspended inside the window: left unmarked
    closes = [float(p["close"]) for p in path[:horizon]]
    peak, drawdown = price_at, 0.0
    for close in closes:
        peak = max(peak, close)
        drawdown = min(drawdown, (close / peak - 1) * 100)
    ret = (closes[-1] / price_at - 1) * 100
    return {
        "end_date": path[horizon - 1]["trade_date"],
        "price_end": closes[-1],
        "return_pct": round(ret, 4),
        "excess_pct": round(ret - universe_return, 4),
        "max_drawdown_pct": round(drawdown, 4),
    }


# ------------------------------------------------------------------ backtest


def backtest(first: date, last: date, step: int, shard: tuple[int, int] = (0, 1)) -> list[dict[str, Any]]:
    """Run the engines as of every ``step``-th trade date in the range. Each run is an ordinary
    ledger run flagged BACKTEST; outcomes are marked afterwards with ``mark``. Resumable: dates
    that already have a finished backtest run are skipped. ``shard=(i, n)`` takes every n-th
    chosen date starting at i, so n processes can run the same range side by side."""
    with transaction() as connection:
        dates = [d for d in _trade_dates(connection) if first <= d <= last]
        done = {
            item["as_of"]
            for item in rows(
                connection, "SELECT as_of FROM engine_run WHERE kind = 'BACKTEST' AND finished_at IS NOT NULL"
            )
        }
    chosen = [d for i, d in enumerate(dates) if i % step == 0 and d not in done]
    index, count = shard
    chosen = [d for j, d in enumerate(chosen) if j % count == index]
    summaries = []
    for day in chosen:
        summary = signal_service.run_all(day, kind="BACKTEST")
        logger.info(f"backtest {day}: {summary['signals']} signals, {summary['stances']} stances")
        summaries.append(summary)
    return summaries


# ------------------------------------------------------------------ read side


def engine_performance(connection: Connection, engine_key: str) -> list[dict[str, Any]]:
    """Per horizon, direction and stage: marked count, hit rate (excess return in the signal's
    direction), mean and median excess return, mean return, mean drawdown."""
    return rows(
        connection,
        """
        SELECT o.horizon_days, s.direction, s.stage, count(*) AS marked,
               round(100.0 * avg(CASE WHEN (s.direction = 'BULL' AND o.excess_pct > 0) OR (s.direction <> 'BULL' AND o.excess_pct < 0) THEN 1 ELSE 0 END), 1) AS hit_rate_pct,
               round(avg(o.excess_pct), 2) AS mean_excess_pct,
               round(CAST(percentile_cont(0.5) WITHIN GROUP (ORDER BY o.excess_pct) AS numeric), 2) AS median_excess_pct,
               round(avg(o.return_pct), 2) AS mean_return_pct,
               round(avg(o.max_drawdown_pct), 2) AS mean_drawdown_pct
          FROM signal_outcome o JOIN signal s USING (signal_id)
         WHERE s.engine_key = :k
         GROUP BY o.horizon_days, s.direction, s.stage
         ORDER BY o.horizon_days, s.direction, CASE s.stage WHEN 'CONFIRMED' THEN 0 WHEN 'EMERGING' THEN 1 ELSE 2 END
        """,
        {"k": engine_key},
    )


def stance_performance(connection: Connection) -> list[dict[str, Any]]:
    return rows(
        connection,
        """
        SELECT o.horizon_days, st.stance, st.conviction, count(*) AS marked,
               round(100.0 * avg(CASE WHEN (st.stance IN ('LONG', 'LEAN_LONG') AND o.excess_pct > 0)
                                        OR (st.stance IN ('SHORT', 'LEAN_SHORT') AND o.excess_pct < 0) THEN 1 ELSE 0 END), 1) AS hit_rate_pct,
               round(avg(o.excess_pct), 2) AS mean_excess_pct,
               round(CAST(percentile_cont(0.5) WITHIN GROUP (ORDER BY o.excess_pct) AS numeric), 2) AS median_excess_pct,
               round(avg(o.max_drawdown_pct), 2) AS mean_drawdown_pct
          FROM stance_outcome o JOIN stance st USING (stance_id)
         WHERE st.stance <> 'AVOID'
         GROUP BY o.horizon_days, st.stance, st.conviction
         ORDER BY o.horizon_days, CASE st.stance WHEN 'LONG' THEN 0 WHEN 'LEAN_LONG' THEN 1 WHEN 'LEAN_SHORT' THEN 2 ELSE 3 END,
                  CASE st.conviction WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END
        """,
    )


def runs(connection: Connection, limit: int = 400) -> list[dict[str, Any]]:
    return rows(
        connection,
        """
        SELECT r.run_id, r.as_of, r.kind, r.signals, r.stances, r.finished_at,
               (SELECT count(*) FROM signal_outcome o JOIN signal s USING (signal_id) WHERE s.run_id = r.run_id) AS marked
          FROM engine_run r WHERE r.finished_at IS NOT NULL ORDER BY r.as_of DESC, r.started_at DESC LIMIT :limit
        """,
        {"limit": limit},
    )


# ------------------------------------------------------------------ retune


def stance_retune(horizon: int = 252, split: date = date(2025, 1, 1)) -> dict[str, Any]:
    """The numbers behind ``stance.ENGINE_WEIGHT``. Recomputes every backtest stance offline from
    the stored signals — no engine is re-run — twice: with every engine at weight 1 (v1) and with
    the current table (v2). Runs before ``split`` are the training period the table was derived
    from; runs on or after it are held out. Returns the per-engine training table and both
    evaluations; ``python ingest.py retune`` prints them."""
    with transaction() as connection:
        signals = rows(
            connection,
            """
            SELECT s.run_id, s.isin, s.as_of, s.engine_key, s.signal_type, s.stage, s.strength, s.direction, s.headline
              FROM signal s JOIN engine_run r USING (run_id)
             WHERE r.kind = 'BACKTEST' AND s.price_at IS NOT NULL
            """,
        )
        marked = rows(
            connection,
            """
            SELECT DISTINCT ON (s.run_id, s.isin) s.run_id, s.isin, o.excess_pct
              FROM signal_outcome o JOIN signal s USING (signal_id) WHERE o.horizon_days = :h
            """,
            {"h": horizon},
        )
    excess = {(m["run_id"], m["isin"]): float(m["excess_pct"]) for m in marked}
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for s in signals:
        groups.setdefault((s["run_id"], s["isin"]), []).append(s)

    table: dict[tuple[str, str], list[float]] = {}
    for key, group in groups.items():
        x = excess.get(key)
        if x is None or group[0]["as_of"] >= split:
            continue
        for s in group:
            if s["direction"] == "GATE":
                continue
            hit = x > 0 if s["direction"] == "BULL" else x < 0
            cell = table.setdefault((s["engine_key"], s["direction"]), [0, 0, 0.0])
            cell[0] += 1
            cell[1] += hit
            cell[2] += x

    def evaluate(engine_weights: dict[tuple[str, str], float]) -> dict[tuple[str, str, str], list[float]]:
        saved = dict(stance_service.ENGINE_WEIGHT)
        stance_service.ENGINE_WEIGHT.clear()
        stance_service.ENGINE_WEIGHT.update(engine_weights)
        result: dict[tuple[str, str, str], list[float]] = {}
        try:
            for key, group in groups.items():
                x = excess.get(key)
                if x is None:
                    continue
                verdict = stance_service.compute(group)
                if verdict.stance in (stance_service.NEUTRAL, stance_service.AVOID):
                    continue
                period = "train" if group[0]["as_of"] < split else "held-out"
                side = (
                    "LONG" if verdict.stance in (stance_service.LONG, stance_service.LEAN_LONG) else "SHORT"
                )
                full = verdict.stance in (stance_service.LONG, stance_service.SHORT)
                hit = x > 0 if side == "LONG" else x < 0
                for bucket in ((period, side, "all"), (period, side, "full" if full else "lean")):
                    cell = result.setdefault(bucket, [0, 0, 0.0])
                    cell[0] += 1
                    cell[1] += hit
                    cell[2] += x
        finally:
            stance_service.ENGINE_WEIGHT.clear()
            stance_service.ENGINE_WEIGHT.update(saved)
        return result

    return {
        "horizon": horizon,
        "split": split,
        "signals": len(signals),
        "groups": len(groups),
        "marked": len(excess),
        "table": table,
        "equal_weights": evaluate({}),
        "current_weights": evaluate(dict(stance_service.ENGINE_WEIGHT)),
    }
