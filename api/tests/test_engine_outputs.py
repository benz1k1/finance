"""
Engine outputs checked against the database they were computed from (spec §85: engines are pure
functions of the snapshot, so their numbers can be recomputed independently). Every test reads
the newest finished LIVE run from the ledger and recomputes a sample of its evidence from the raw
tables with plain SQL — not through the engine code. They fail loudly when the app has no run.

Added 2026-10-04 after the UI showed identical outputs on many securities: some were by design
(a sector-level engine), some were defects (catalyst evidence named no documents, a sector
signal count exceeded its member count, float noise in ownership percentages).
"""

import re
from collections import Counter
from datetime import date
from decimal import Decimal
from typing import Any

import orjson
import pytest

from equity_engine.db import rows, transaction
from equity_engine.engines.base import _FUNDAMENTALS, _OWNERSHIP
from equity_engine.service import stance

# Engines whose signal is the same for every member of a list or industry, by design.
GROUP_LEVEL_ENGINES = {"sector_rotation", "investability"}

ADJUSTING_ACTION = """
    SELECT 1 FROM corporate_action a
     WHERE a.symbol = :symbol AND a.adjust_factor IS NOT NULL
       AND a.ex_date > CAST(:d AS date) - 420 AND a.ex_date <= :d
"""


def _evidence(signal: dict[str, Any]) -> dict[str, Any]:
    raw = signal["evidence"]
    return raw if isinstance(raw, dict) else orjson.loads(raw)


@pytest.fixture(scope="module")
def live() -> dict[str, Any]:
    with transaction() as connection:
        run = rows(
            connection,
            "SELECT run_id, as_of FROM engine_run WHERE kind = 'LIVE' AND finished_at IS NOT NULL ORDER BY started_at DESC LIMIT 1",
        )
        if not run:
            pytest.fail("No finished LIVE engine run in the ledger. Run: python ingest.py signals")
        signals = rows(
            connection,
            "SELECT * FROM signal WHERE run_id = :r ORDER BY symbol, engine_key",
            {"r": run[0]["run_id"]},
        )
        stances = rows(connection, "SELECT * FROM stance WHERE run_id = :r", {"r": run[0]["run_id"]})
    if not signals:
        pytest.fail(f"Run {run[0]['run_id']} wrote no signals")
    return {"run": run[0], "signals": signals, "stances": stances}


def _by_engine(live: dict[str, Any], key: str) -> list[dict[str, Any]]:
    found = [s for s in live["signals"] if s["engine_key"] == key]
    if not found:
        pytest.fail(f"The run has no {key} signals; the engine or its data is missing")
    return found


# ------------------------------------------------------------------ ledger shape


def test_one_signal_per_security_engine_and_type(live):
    keys = Counter((s["isin"], s["engine_key"], s["signal_type"]) for s in live["signals"])
    duplicates = [k for k, n in keys.items() if n > 1]
    assert duplicates == [], f"duplicate signals in one run: {duplicates[:5]}"


def test_every_signal_is_in_the_universe_and_priced_on_the_as_of_date(live, connection):
    as_of = live["run"]["as_of"]
    closes = {
        r["isin"]: r["close"]
        for r in rows(
            connection,
            "SELECT isin, close FROM price_daily WHERE trade_date = :d AND series IN ('EQ', 'SM')",
            {"d": as_of},
        )
    }
    universe = {
        r["isin"]
        for r in rows(
            connection,
            "SELECT isin FROM index_constituent_snapshot WHERE index_code = 'nifty500' AND snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot WHERE index_code = 'nifty500')",
        )
    }
    outside = sorted({s["symbol"] for s in live["signals"] if s["isin"] not in universe})
    assert outside == [], f"signals for securities outside the Nifty 500: {outside[:10]}"
    wrong_price = [
        (s["symbol"], s["price_at"], closes[s["isin"]])
        for s in live["signals"]
        if s["price_at"] is not None
        and s["isin"] in closes
        and Decimal(s["price_at"]) != Decimal(closes[s["isin"]])
    ]
    assert wrong_price == [], f"price_at is not the as-of close: {wrong_price[:5]}"


def test_security_level_engines_do_not_repeat_the_same_evidence(live):
    repeated = {}
    for key in {s["engine_key"] for s in live["signals"]} - GROUP_LEVEL_ENGINES:
        signals = _by_engine(live, key)
        distinct = len({orjson.dumps(_evidence(s), option=orjson.OPT_SORT_KEYS) for s in signals})
        if distinct < len(signals):
            repeated[key] = (distinct, len(signals))
    assert repeated == {}, (
        f"engines emitting identical evidence for different securities (distinct, total): {repeated}"
    )


def test_evidence_numbers_carry_no_float_noise(live):
    def noisy(value: Any) -> bool:
        if isinstance(value, float):
            return round(value, 4) != value
        if isinstance(value, dict):
            return any(noisy(v) for v in value.values())
        if isinstance(value, list):
            return any(noisy(v) for v in value)
        return False

    bad = [(s["engine_key"], s["symbol"], _evidence(s)) for s in live["signals"] if noisy(_evidence(s))]
    assert bad == [], f"unrounded floats in evidence: {bad[:3]}"


def test_run_writes_a_stance_for_every_priced_security(live, connection):
    priced = rows(
        connection,
        """
        SELECT count(DISTINCT p.isin) AS n FROM price_daily p
          JOIN index_constituent_snapshot c ON c.isin = p.isin AND c.index_code = 'nifty500'
           AND c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot WHERE index_code = 'nifty500')
         WHERE p.trade_date = :d AND p.series IN ('EQ', 'SM')
        """,
        {"d": live["run"]["as_of"]},
    )[0]["n"]
    stanced = {st["isin"] for st in live["stances"]}
    assert len(stanced) >= priced, f"{priced} priced universe securities but {len(stanced)} stances"


def test_every_stored_stance_is_the_function_of_its_signals(live):
    by_isin: dict[str, list[dict[str, Any]]] = {}
    for s in live["signals"]:
        by_isin.setdefault(s["isin"], []).append(s)
    mismatches = []
    for stored in live["stances"]:
        expected = stance.compute(by_isin.get(stored["isin"], []))
        if (
            expected.stance != stored["stance"]
            or expected.conviction != stored["conviction"]
            or round(expected.bull_score, 4) != float(stored["bull_score"])
            or round(expected.bear_score, 4) != float(stored["bear_score"])
            or stored["version"] != stance.VERSION
        ):
            mismatches.append((stored["symbol"], stored["stance"], expected.stance, stored["version"]))
    assert mismatches == [], f"stored stance differs from recomputation: {mismatches[:5]}"


# ------------------------------------------------------------------ price engines


def test_technical_price_distances_match_the_price_history(live, connection):
    as_of = live["run"]["as_of"]
    checked, bad = 0, []
    for s in _by_engine(live, "technical_price"):
        if rows(connection, ADJUSTING_ACTION, {"symbol": s["symbol"], "d": as_of}):
            continue  # adjusted closes are tested separately; here the raw series must agree exactly
        window = rows(
            connection,
            """
            SELECT close FROM price_daily WHERE isin = :isin AND series IN ('EQ', 'SM') AND trade_date <= :d
             ORDER BY trade_date DESC LIMIT 252
            """,
            {"isin": s["isin"], "d": as_of},
        )
        closes = [float(r["close"]) for r in window]
        ev = _evidence(s)
        expect = {
            "close": closes[0],
            "sma50": round(sum(closes[:50]) / 50, 2),
            "from_52w_high_pct": round((closes[0] / max(closes) - 1) * 100, 2),
            "from_52w_low_pct": round((closes[0] / min(closes) - 1) * 100, 2),
        }
        for key, value in expect.items():
            if abs(float(ev[key]) - value) > 0.011:
                bad.append((s["symbol"], key, ev[key], value))
        checked += 1
        if checked >= 60:
            break
    assert checked >= 10, "too few unadjusted technical_price signals to check"
    assert bad == [], f"evidence disagrees with price_daily: {bad[:6]}"


def test_technical_price_headline_states_the_evidence(live):
    bad = []
    for s in _by_engine(live, "technical_price"):
        ev = _evidence(s)
        which = "high" if s["signal_type"] == "TREND_UP" else "low"
        pct = ev[f"from_52w_{which}_pct"]
        if abs(pct) < 0.5:
            ok = f"at its 52-week {which}" in s["headline"]
        else:
            found = re.search(r"([+-]\d+)% from 52-week (high|low)", s["headline"])
            ok = found is not None and found.group(2) == which and int(found.group(1)) == round(pct)
        if not ok:
            bad.append((s["symbol"], s["headline"], pct))
    assert bad == [], f"headline and evidence disagree: {bad[:5]}"


def test_relative_strength_returns_match_the_price_history(live, connection):
    as_of = live["run"]["as_of"]
    bad, checked = [], 0
    for s in _by_engine(live, "relative_strength"):
        if rows(connection, ADJUSTING_ACTION, {"symbol": s["symbol"], "d": as_of}):
            continue
        window = rows(
            connection,
            "SELECT close FROM price_daily WHERE isin = :isin AND series IN ('EQ', 'SM') AND trade_date <= :d ORDER BY trade_date DESC LIMIT 253",
            {"isin": s["isin"], "d": as_of},
        )
        closes = [float(r["close"]) for r in window]
        ev = _evidence(s)
        for key, offset in (("return_3m_pct", 63), ("return_6m_pct", 126), ("return_12m_pct", 252)):
            if ev.get(key) is None or len(closes) <= offset:
                continue
            expected = round((closes[0] / closes[offset] - 1) * 100, 2)
            if abs(float(ev[key]) - expected) > 0.011:
                bad.append((s["symbol"], key, ev[key], expected))
        checked += 1
        if checked >= 40:
            break
    assert checked >= 10
    assert bad == [], f"returns disagree with price_daily: {bad[:6]}"


# ------------------------------------------------------------------ group-level engines


def test_sector_rotation_evidence_matches_the_industry_and_its_member_count(live, connection):
    as_of = live["run"]["as_of"]
    industry_of = {
        r["isin"]: r["industry"]
        for r in rows(
            connection,
            """
            SELECT DISTINCT ON (isin) isin, industry FROM index_constituent_snapshot
             WHERE snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot WHERE snapshot_date <= :d)
             ORDER BY isin, CASE index_code WHEN 'nifty500' THEN 0 ELSE 1 END
            """,
            {"d": as_of},
        )
    }
    signals = _by_engine(live, "sector_rotation")
    wrong_industry = [
        (s["symbol"], _evidence(s)["industry"], industry_of.get(s["isin"]))
        for s in signals
        if _evidence(s)["industry"] != industry_of.get(s["isin"])
    ]
    assert wrong_industry == [], f"signal carries another industry's figures: {wrong_industry[:5]}"
    per_industry = Counter(_evidence(s)["industry"] for s in signals)
    members = {_evidence(s)["industry"]: _evidence(s)["members"] for s in signals}
    overflow = {i: (n, members[i]) for i, n in per_industry.items() if n > members[i]}
    assert overflow == {}, f"more signals than counted members (signals, members): {overflow}"
    for s in signals:
        ev = _evidence(s)
        assert f"{ev['industry']}: {ev['rel_3m']:+.1f} points" in s["headline"], (
            s["symbol"],
            s["headline"],
            ev,
        )


# ------------------------------------------------------------------ document engines


def _documents_in_window(connection, symbol: str, as_of: date, kinds: tuple[str, ...]) -> Counter[str]:
    found = rows(
        connection,
        """
        SELECT event_kind FROM document
         WHERE symbol = :symbol AND broadcast_at <= CAST(:d AS date) + 1 AND broadcast_at > CAST(:d AS date) - 45
           AND event_kind = ANY(:kinds)
        """,
        {"symbol": symbol, "d": as_of, "kinds": list(kinds)},
    )
    return Counter(r["event_kind"] for r in found)


def test_catalyst_counts_match_the_document_table_and_name_the_documents(live, connection):
    as_of = live["run"]["as_of"]
    bad = []
    for s in _by_engine(live, "catalyst"):
        ev = _evidence(s)
        expected = _documents_in_window(
            connection, s["symbol"], as_of, ("ORDER_WIN", "ACQUISITION", "BUYBACK")
        )
        if Counter(ev["recent_announcements"]) != expected:
            bad.append((s["symbol"], ev["recent_announcements"], dict(expected)))
        counted = sum(ev["recent_announcements"].values())
        listed = ev.get("announcements", [])
        if counted and (not listed or len(listed) != min(counted, 6)):
            bad.append((s["symbol"], "announcements not listed", counted, len(listed)))
        for item in listed:
            if item["kind"] not in ev["recent_announcements"] or not item["summary"]:
                bad.append((s["symbol"], "listed announcement is not one that was counted", item))
    assert bad == [], f"catalyst evidence disagrees with the document table: {bad[:5]}"


def test_governance_counts_match_the_document_table_and_the_headline(live, connection):
    as_of = live["run"]["as_of"]
    bad = []
    for s in _by_engine(live, "corporate_governance"):
        ev = _evidence(s)
        expected = _documents_in_window(
            connection, s["symbol"], as_of, ("GOVERNANCE", "REGULATORY", "PLEDGE")
        )
        if Counter(ev["counts"]) != expected:
            bad.append((s["symbol"], ev["counts"], dict(expected)))
        found = re.match(
            r"(\d+) regulatory, (\d+) governance and (\d+) pledge filings in 45 days", s["headline"]
        )
        if found is None or [int(g) for g in found.groups()] != [
            expected["REGULATORY"],
            expected["GOVERNANCE"],
            expected["PLEDGE"],
        ]:
            bad.append((s["symbol"], s["headline"], dict(expected)))
        if not ev["examples"] or any(e.split(":")[0] == "" for e in ev["examples"]):
            bad.append((s["symbol"], "no examples quoted"))
    assert bad == [], f"governance evidence disagrees with the document table: {bad[:5]}"


# ------------------------------------------------------------------ fundamentals engines


def _history(connection, as_of: date) -> dict[str, list[dict[str, Any]]]:
    """Point-in-time quarters per symbol, newest first, through the same SQL the snapshot uses —
    so these tests check the engines' arithmetic, not the choice of filing."""
    out: dict[str, list[dict[str, Any]]] = {}
    for q in rows(connection, _FUNDAMENTALS, {"d": as_of}):
        out.setdefault(q["symbol"], []).append(q)
    return out


def _growth(now, then) -> float | None:
    if now is None or then is None or float(then) <= 0:
        return None
    return round((float(now) / float(then) - 1) * 100, 2)


def test_earnings_acceleration_growth_series_match_fin_quarter(live, connection):
    history = _history(connection, live["run"]["as_of"])
    bad = []
    for s in _by_engine(live, "earnings_acceleration"):
        quarters = history[s["symbol"]]
        expected = [_growth(quarters[i]["q_pat"], quarters[i + 4]["q_pat"]) for i in range(3)]
        ev = _evidence(s)
        if ev["yoy_pat_growth_pct"] != expected or str(quarters[0]["period_end"]) != ev["quarter"]:
            bad.append((s["symbol"], ev, expected))
        g0, g1, g2 = expected
        if s["signal_type"] == "EARNINGS_ACCELERATING" and not (g0 > g1 > g2 and g0 > 10):
            bad.append((s["symbol"], "fired without accelerating growth", expected))
    assert bad == [], f"earnings_acceleration disagrees with fin_quarter: {bad[:5]}"


def test_operating_leverage_ratio_matches_ttm_growth(live, connection):
    history = _history(connection, live["run"]["as_of"])

    def ttm(quarters, key, offset=0):
        window = quarters[offset : offset + 4]
        if len(window) < 4 or any(q[key] is None for q in window):
            return None
        return float(sum(q[key] for q in window))

    bad = []
    for s in _by_engine(live, "operating_leverage"):
        quarters = history[s["symbol"]]
        rev_g = _growth(ttm(quarters, "q_revenue"), ttm(quarters, "q_revenue", 4))
        pat_g = _growth(ttm(quarters, "q_pat"), ttm(quarters, "q_pat", 4))
        ev = _evidence(s)
        if (
            ev["ttm_revenue_growth_pct"] != rev_g
            or ev["ttm_pat_growth_pct"] != pat_g
            or ev["leverage_ratio"] != round(pat_g / rev_g, 2)
        ):
            bad.append((s["symbol"], ev, rev_g, pat_g))
        if not (rev_g >= 5 and pat_g >= rev_g * 1.5):
            bad.append((s["symbol"], "fired below its own thresholds", rev_g, pat_g))
    assert bad == [], f"operating_leverage disagrees with fin_quarter: {bad[:5]}"


def test_deep_value_headline_never_prints_none(live):
    bad = [(s["symbol"], s["headline"]) for s in _by_engine(live, "deep_value") if "None" in s["headline"]]
    assert bad == [], bad


# ------------------------------------------------------------------ ownership engines


def test_institutional_accumulation_matches_shareholding_pattern(live, connection):
    ownership: dict[str, list[dict[str, Any]]] = {}
    for q in rows(connection, _OWNERSHIP, {"d": live["run"]["as_of"]}):
        ownership.setdefault(q["symbol"], []).append(q)

    def inst(q):
        if q["fii_pct"] is None and q["dii_pct"] is None:
            return None
        return round(float(q["fii_pct"] or 0) + float(q["dii_pct"] or 0), 2)

    bad = []
    for s in _by_engine(live, "institutional_accumulation"):
        quarters = ownership[s["symbol"]]
        ev = _evidence(s)
        now, prev = inst(quarters[0]), inst(quarters[1])
        if (
            ev["institutional_pct"] != now
            or ev["institutional_pct_prev"] != prev
            or ev["change_points"] != round(now - prev, 2)
        ):
            bad.append((s["symbol"], ev, now, prev))
        if (
            str(quarters[0]["period_end"]) != ev["quarter"]
            or str(quarters[1]["period_end"]) != ev["prev_quarter"]
        ):
            bad.append((s["symbol"], "quarters", ev["quarter"], str(quarters[0]["period_end"])))
        if (s["signal_type"] == "INSTITUTIONAL_ACCUMULATION") != (ev["change_points"] > 0):
            bad.append((s["symbol"], "direction", s["signal_type"], ev["change_points"]))
    assert bad == [], f"institutional_accumulation disagrees with shareholding_pattern: {bad[:5]}"


def test_promoter_activity_matches_shareholding_pattern(live, connection):
    ownership: dict[str, list[dict[str, Any]]] = {}
    for q in rows(connection, _OWNERSHIP, {"d": live["run"]["as_of"]}):
        ownership.setdefault(q["symbol"], []).append(q)
    bad = []
    for s in _by_engine(live, "promoter_activity"):
        quarters = ownership[s["symbol"]]
        ev = _evidence(s)
        now, prev = float(quarters[0]["promoter_pct"]), float(quarters[1]["promoter_pct"])
        if (
            ev["promoter_pct"] != round(now, 2)
            or ev["promoter_pct_prev"] != round(prev, 2)
            or ev["change_points"] != round(now - prev, 2)
        ):
            bad.append((s["symbol"], ev, now, prev))
    assert bad == [], f"promoter_activity disagrees with shareholding_pattern: {bad[:5]}"
