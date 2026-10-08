"""Fundamentals engines on synthetic quarter histories, and outcome measurement (pure)."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from equity_engine.engines import fundamentals as fe
from equity_engine.service import outcomes


class _Snap:
    """Just enough of a Snapshot for the fundamentals engines."""

    def __init__(
        self, histories: dict[str, list[dict[str, Any]]], market_caps: dict[str, float] | None = None
    ):
        self.fundamentals = histories
        self.price_by_isin = {
            isin: {"market_cap": cap, "raw_close": 100.0, "close": 100.0}
            for isin, cap in (market_caps or {}).items()
        }
        self.industry: dict[str, dict[str, Any]] = {}
        self.results_reactions: list[dict[str, Any]] = []

    def close(self, isin: str) -> Decimal | None:
        return Decimal("100")


def _history(
    isin: str, pats: list[float], revenues: list[float] | None = None, **extra: Any
) -> list[dict[str, Any]]:
    """Newest first. ``pats``/``revenues`` are in crore and oldest-last like the engines expect."""
    out = []
    end = date(2026, 6, 30)
    for i, pat in enumerate(pats):
        period_end = (
            date(end.year - (i // 4), [6, 3, 12, 9][i % 4] if False else end.month, 30)
            if False
            else end - timedelta(days=91 * i)
        )
        row = {
            "isin": isin,
            "symbol": isin,
            "period_end": period_end,
            "consolidated": True,
            "broadcast_at": datetime(2026, 7, 15),
            "is_bank": False,
            "is_lender": False,
            "q_pat": pat * 1e7,
            "q_pat_owners": pat * 1e7,
            "q_revenue": (revenues[i] if revenues else 100.0) * 1e7,
            "q_other_income": 0.0,
            "q_finance_costs": 1e7,
            "q_depreciation": 2e7,
            "q_pbt": pat * 1e7 * 1.3,
            "q_exceptional": 0.0,
            "q_eps_basic": pat / 10,
        }
        row.update({k: (v[i] if isinstance(v, list) else v) for k, v in extra.items()})
        out.append(row)
    return out


def test_profitability_inflection_fires_on_loss_to_profit():
    history = _history("A", [5, 4, 3, 2, -3, -4, -5, -6])
    found = fe.ProfitabilityInflection().evaluate(_Snap({"A": history}))  # type: ignore[arg-type]
    assert len(found) == 1 and found[0].signal_type == "LOSS_TO_PROFIT" and found[0].stage == "CONFIRMED"
    assert fe.ProfitabilityInflection().evaluate(_Snap({"A": _history("A", [5, 4, 3, 2, 3, 4, 5, 6])})) == []  # type: ignore[arg-type]


def test_earnings_acceleration_needs_rising_yoy_growth():
    # YoY growth: newest 10 vs 5 (+100%), then 8 vs 5 (+60%), then 6 vs 5 (+20%)
    history = _history("B", [10, 8, 6, 5, 5, 5, 5, 5])
    found = fe.EarningsAcceleration().evaluate(_Snap({"B": history}))  # type: ignore[arg-type]
    assert [s.signal_type for s in found] == ["EARNINGS_ACCELERATING"] and found[0].stage == "CONFIRMED"


def test_deleveraging_and_leverage_spike():
    down = _history(
        "C", [5] * 8, bs_borrowings=[50e7] + [None] * 3 + [100e7] + [None] * 3, bs_equity=[100e7] * 8
    )
    up = _history(
        "D", [5] * 8, bs_borrowings=[150e7] + [None] * 3 + [100e7] + [None] * 3, bs_equity=[100e7] * 8
    )
    found = fe.Deleveraging().evaluate(_Snap({"C": down, "D": up}))  # type: ignore[arg-type]
    assert {s.signal_type for s in found} == {"DELEVERAGING", "LEVERAGE_SPIKE"}


def test_valuation_percentiles_and_undervalued_growth():
    histories = {f"S{i}": _history(f"S{i}", [10] * 8) for i in range(10)}
    histories["CHEAP"] = _history("CHEAP", [20, 20, 20, 20, 10, 10, 10, 10])  # PAT doubled YoY
    caps = {k: 40 * 10 * 1e7 for k in histories}  # P/E 10 for the ten; CHEAP at P/E 5
    caps["CHEAP"] = 5 * 80 * 1e7
    snap = _Snap(histories, caps)
    valuation = {s.isin: s for s in fe.Valuation().evaluate(snap)}  # type: ignore[arg-type]
    assert valuation["CHEAP"].signal_type == "CHEAP_ON_EARNINGS"
    growth = fe.UndervaluedGrowth().evaluate(snap)  # type: ignore[arg-type]
    assert [s.isin for s in growth] == ["CHEAP"]


def test_credit_distress_gate_and_cash_runway():
    # PAT negative, so EBIT (PBT + finance costs) is below the finance costs: cover under 1×
    stressed = _history("E", [-5] * 8, q_finance_costs=20e7, bs_equity=[10e7] * 8, bs_borrowings=[50e7] * 8)
    gates = fe.CreditDistress().evaluate(_Snap({"E": stressed}))  # type: ignore[arg-type]
    assert gates and gates[0].direction == "GATE" and gates[0].signal_type == "DISTRESS"
    burning = _history("F", [-10] * 8, bs_cash=[15e7] * 8)
    runway = fe.UnitEconomics().evaluate(_Snap({"F": burning}))  # type: ignore[arg-type]
    assert runway[0].signal_type == "CASH_RUNWAY_CRITICAL" and runway[0].evidence["runway_quarters"] == 1.5


def test_outcome_measure_return_excess_and_drawdown():
    path = [
        {"trade_date": date(2026, 1, 1) + timedelta(days=i), "close": c}
        for i, c in enumerate([110, 90, 95, 120, 130])
    ]
    measured = outcomes._measure(path, 100.0, 5, universe_return=10.0)
    assert measured is not None
    assert measured["return_pct"] == 30.0 and measured["excess_pct"] == 20.0
    assert round(measured["max_drawdown_pct"], 2) == round((90 / 110 - 1) * 100, 2)
    assert outcomes._measure(path, 100.0, 6, 0.0) is None  # window not complete yet


def test_window_end_counts_trading_sessions():
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(30)]
    assert outcomes._window_end(dates, date(2026, 1, 5), 3) == date(2026, 1, 8)
    assert outcomes._window_end(dates, date(2026, 1, 29), 3) is None
