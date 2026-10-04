"""
The company stance (spec §118): a deterministic, versioned summary of one security's signals.

Not a score sold as advice (§39, §52) — a tally the user can check. Each signal contributes its
strength weighted by stage; bull and bear sides are summed separately and both are shown. Any GATE
signal makes the stance AVOID with the gate named. Conviction counts CONFIRMED signals, not points:
one quarter's spike never makes HIGH.

Change the numbers here and bump VERSION — every emission carries it, so the ledger can judge one
version against another.

v2 (2026-10-04) adds a per-engine weight on top of stage × strength. The weights come from the
2019–2024 backtest ledger at the 12-month horizon (``python ingest.py retune`` reprints the table):
an engine and direction with at least 200 marked signals gets 1.5 above a 57% hit rate, 1.0 at
52–57%, 0.5 at 47–52% and 0 below 47%; everything else stays at 1.0. Held out on 2025–2026, long
stances went from 50.8% to 54.2% hit (+5.5% to +11.3% mean excess) and short from 52.9% to 55.5%.
Caveat recorded in TODO.md: past universes are survivor-biased, which hurts bear engines most
(credit distress at 0 is the clearest casualty; its DISTRESS gate is unaffected).
"""

from dataclasses import dataclass
from typing import Any

from equity_engine.engines.base import BEAR, BULL, CONFIRMED, EARLY, EMERGING, GATE, MATURE, REVERSING

VERSION = "2"

# (engine_key, direction) -> multiplier on strength. Absent means 1.0. Derived from the ledger, see
# the module docstring; a weight of 0 keeps the signal visible on the panel but out of the tally.
ENGINE_WEIGHT: dict[tuple[str, str], float] = {
    ("turnaround", BULL): 1.5,
    ("profitability_inflection", BULL): 1.5,
    ("volume_delivery", BULL): 0.5,
    ("technical_price", BULL): 0.5,
    ("catalyst", BULL): 0.5,
    ("operating_leverage", BULL): 0.5,
    ("relative_strength", BULL): 0.5,
    ("derivatives_signal", BULL): 0.5,
    ("margin_inflection", BULL): 0.5,
    ("earnings_acceleration", BULL): 0.5,
    ("roce_inflection", BULL): 0.5,
    ("cash_flow_inflection", BULL): 0.0,
    ("capital_allocation", BULL): 0.0,
    ("corporate_event", BULL): 0.0,
    ("deleveraging", BEAR): 1.5,
    ("supply_overhang", BEAR): 1.5,
    ("insider_deal_flow", BEAR): 1.5,
    ("manipulation_risk", BEAR): 1.5,
    ("roce_inflection", BEAR): 0.5,
    ("implied_growth", BEAR): 0.5,
    ("accounting_quality", BEAR): 0.5,
    ("derivatives_signal", BEAR): 0.5,
    ("capital_allocation", BEAR): 0.5,
    ("valuation", BEAR): 0.5,
    ("credit_distress", BEAR): 0.0,
}

STAGE_WEIGHT = {EARLY: 0.3, EMERGING: 0.6, CONFIRMED: 1.0, MATURE: 0.5, REVERSING: 0.3}

LONG, LEAN_LONG, NEUTRAL, LEAN_SHORT, SHORT, AVOID = (
    "LONG",
    "LEAN_LONG",
    "NEUTRAL",
    "LEAN_SHORT",
    "SHORT",
    "AVOID",
)
NONE, LOW, MEDIUM, HIGH = "NONE", "LOW", "MEDIUM", "HIGH"

# Net weighted score needed for each stance; symmetric for short.
LEAN_AT, FULL_AT = 0.6, 1.5

STANCE_LABEL = {
    LONG: "Long",
    LEAN_LONG: "Lean long",
    NEUTRAL: "Neutral",
    LEAN_SHORT: "Lean short",
    SHORT: "Short",
    AVOID: "Avoid",
}
CONVICTION_LABEL = {NONE: "No signals", LOW: "Low", MEDIUM: "Medium", HIGH: "High"}


@dataclass(frozen=True)
class Stance:
    stance: str
    conviction: str
    bull_score: float
    bear_score: float
    bull_count: int
    bear_count: int
    gate: str | None
    inputs: dict[str, Any]
    version: str = VERSION


def weight(signal: dict[str, Any]) -> float:
    """One signal's contribution to its side: stage weight × engine weight × strength."""
    return (
        STAGE_WEIGHT[signal["stage"]]
        * ENGINE_WEIGHT.get((signal["engine_key"], signal["direction"]), 1.0)
        * float(signal["strength"])
    )


def compute(signals: list[dict[str, Any]]) -> Stance:
    """``signals`` are ledger rows (or Signal-like dicts) for one security from one run."""
    gates = [s for s in signals if s["direction"] == GATE]
    bulls = [s for s in signals if s["direction"] == BULL]
    bears = [s for s in signals if s["direction"] == BEAR]
    weights = {
        s.get("signal_id", f"{s['engine_key']}:{s['signal_type']}"): round(weight(s), 4)
        for s in bulls + bears
    }
    bull_score = round(sum(weight(s) for s in bulls), 4)
    bear_score = round(sum(weight(s) for s in bears), 4)
    inputs = {
        "weights": weights,
        "stage_weight": STAGE_WEIGHT,
        "engine_weight": {
            f"{k}:{d}": w
            for (k, d), w in ENGINE_WEIGHT.items()
            if any(s["engine_key"] == k for s in bulls + bears)
        },
        "lean_at": LEAN_AT,
        "full_at": FULL_AT,
    }
    if gates:
        gate = sorted(gates, key=lambda s: s["headline"])[0]
        return Stance(
            AVOID,
            NONE,
            bull_score,
            bear_score,
            len(bulls),
            len(bears),
            gate["headline"],
            inputs | {"gate_signal_type": gate["signal_type"], "gate_engine": gate["engine_key"]},
        )
    net = bull_score - bear_score
    if net >= FULL_AT:
        stance = LONG
    elif net >= LEAN_AT:
        stance = LEAN_LONG
    elif net <= -FULL_AT:
        stance = SHORT
    elif net <= -LEAN_AT:
        stance = LEAN_SHORT
    else:
        stance = NEUTRAL
    if not bulls and not bears:
        conviction = NONE
    elif stance == NEUTRAL:
        conviction = LOW
    else:
        with_us, against = (bulls, bears) if net > 0 else (bears, bulls)
        confirmed_for = sum(1 for s in with_us if s["stage"] == CONFIRMED)
        confirmed_against = sum(1 for s in against if s["stage"] == CONFIRMED)
        if confirmed_for >= 3 and confirmed_against == 0:
            conviction = HIGH
        elif confirmed_for >= 1 or len(with_us) >= 3:
            conviction = MEDIUM
        else:
            conviction = LOW
    return Stance(stance, conviction, bull_score, bear_score, len(bulls), len(bears), None, inputs)
