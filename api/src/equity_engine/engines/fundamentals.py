"""
Fundamentals engines (spec §6–§17, §19, §34, §58–§60, §68, §104) on the canonical quarters in
``fin_quarter``, as known on the as-of date. Every engine here reads ``snap.fundamentals``: per
company, newest quarter first, consolidated preferred.

Conventions: TTM is the sum of the newest four quarters and needs all four; YoY compares a
quarter with the one four back; growth is undefined (None) when the base is not positive, so a
loss-to-profit swing is a *profitability inflection*, not an infinite growth rate. Banks have no
EBITDA or revenue in the manufacturing sense; the engines that need them skip banks and say so.
"""

from typing import Any

from equity_engine.engines.base import (
    BEAR,
    BULL,
    CONFIRMED,
    EARLY,
    EMERGING,
    GATE,
    Signal,
    Snapshot,
    percentile_of,
)
from equity_engine.service.fundamentals import ebitda

Quarter = dict[str, Any]


def _ttm(history: list[Quarter], key: str, offset: int = 0) -> float | None:
    window = history[offset : offset + 4]
    if len(window) < 4 or any(q.get(key) is None for q in window):
        return None
    return float(sum(q[key] for q in window))


def _ttm_ebitda(history: list[Quarter], offset: int = 0) -> float | None:
    window = history[offset : offset + 4]
    values = [ebitda(q) for q in window]
    if len(window) < 4 or any(v is None for v in values):
        return None
    return float(sum(v for v in values if v is not None))


def _growth(now: float | None, then: float | None) -> float | None:
    if now is None or then is None or then <= 0:
        return None
    return round((now / then - 1) * 100, 2)


def _latest(history: list[Quarter], key: str) -> float | None:
    """The newest quarter carrying this balance-sheet item (most file it twice a year)."""
    for q in history:
        if q.get(key) is not None:
            return float(q[key])
    return None


def _latest_at(history: list[Quarter], key: str, offset_quarters: int) -> float | None:
    for q in history[offset_quarters:]:
        if q.get(key) is not None:
            return float(q[key])
    return None


def _fy_ytd(history: list[Quarter], key: str) -> list[tuple[Quarter, float]]:
    """Year-end quarters (period_end in March) that carry the year-to-date item: the annual figure."""
    return [(q, float(q[key])) for q in history if q["period_end"].month == 3 and q.get(key) is not None]


def _margin(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator * 100, 2)


def _signal(
    snap: Snapshot,
    history: list[Quarter],
    signal_type: str,
    direction: str,
    stage: str,
    strength: float,
    headline: str,
    evidence: dict[str, Any],
    invalidation: str,
    percentile: float | None = None,
) -> Signal:
    newest = history[0]
    evidence = {
        "quarter": str(newest["period_end"]),
        "consolidated": newest["consolidated"],
        "filed": str(newest["broadcast_at"].date()),
    } | evidence
    return Signal(
        newest["isin"],
        newest["symbol"],
        signal_type,
        direction,
        stage,
        round(min(1.0, strength), 4),
        headline,
        evidence,
        invalidation,
        percentile=percentile,
        price_at=snap.close(newest["isin"]),
    )


class ProfitabilityInflection:
    """§6. Losses turning: TTM PAT negative a year ago, the newest two quarters profitable, with
    revenue not shrinking. Stage counts the consecutive profitable quarters."""

    key = "profitability_inflection"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if len(history) < 8:
                continue
            ttm_then = _ttm(history, "q_pat", 4)
            if ttm_then is None or ttm_then >= 0:
                continue
            streak = 0
            for q in history:
                if q.get("q_pat") is None or float(q["q_pat"]) <= 0:
                    break
                streak += 1
            if streak < 2:
                continue
            rev_growth = _growth(_ttm(history, "q_revenue"), _ttm(history, "q_revenue", 4))
            if rev_growth is not None and rev_growth < -10:
                continue
            stage = CONFIRMED if streak >= 4 else (EMERGING if streak == 3 else EARLY)
            out.append(
                _signal(
                    snap,
                    history,
                    "LOSS_TO_PROFIT",
                    BULL,
                    stage,
                    0.5 + streak / 8,
                    f"{streak} profitable quarters after a loss-making year (TTM PAT then ₹{ttm_then / 1e7:,.0f} cr)",
                    {
                        "profitable_quarters": streak,
                        "ttm_pat_then_crore": round(ttm_then / 1e7, 1),
                        "ttm_pat_now_crore": round((_ttm(history, "q_pat") or 0) / 1e7, 1),
                        "revenue_growth_ttm_pct": rev_growth,
                    },
                    "A loss-making quarter",
                )
            )
        return out


class EarningsAcceleration:
    """§7. Year-on-year PAT growth rising for consecutive quarters, all positive; the mirror is
    deceleration from a high rate."""

    key = "earnings_acceleration"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if len(history) < 7:
                continue
            growths = []
            for i in range(3):
                now, then = history[i].get("q_pat"), history[i + 4].get("q_pat")
                growths.append(
                    _growth(
                        float(now) if now is not None else None, float(then) if then is not None else None
                    )
                )
            if any(g is None for g in growths):
                continue
            g0, g1, g2 = (g for g in growths if g is not None)
            evidence = {"yoy_pat_growth_pct": [g0, g1, g2]}
            if g0 > g1 > g2 and g0 > 10:
                stage = CONFIRMED if g2 > 0 else EMERGING
                out.append(
                    _signal(
                        snap,
                        history,
                        "EARNINGS_ACCELERATING",
                        BULL,
                        stage,
                        min(1.0, g0 / 100),
                        f"PAT growth accelerating: {g2:+.0f}% → {g1:+.0f}% → {g0:+.0f}% year on year",
                        evidence,
                        "A quarter whose YoY growth is below the previous quarter's",
                    )
                )
            elif g0 < g1 < g2 and g2 > 20 and g0 < 5:
                out.append(
                    _signal(
                        snap,
                        history,
                        "EARNINGS_DECELERATING",
                        BEAR,
                        EMERGING,
                        min(1.0, (g2 - g0) / 100),
                        f"PAT growth fading: {g2:+.0f}% → {g1:+.0f}% → {g0:+.0f}% year on year",
                        evidence,
                        "YoY growth re-accelerates",
                    )
                )
        return out


class MarginInflection:
    """§8. TTM EBITDA margin rising for consecutive quarters after a trough at least 200bp below
    its 3-year peak; compression is the mirror. Not for banks."""

    key = "margin_inflection"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if history[0].get("is_bank") or len(history) < 9:
                continue
            margins = []
            for offset in range(0, len(history) - 3):
                m = _margin(_ttm_ebitda(history, offset), _ttm(history, "q_revenue", offset))
                if m is None:
                    break
                margins.append(m)
            if len(margins) < 5:
                continue
            rising = 0
            for newer, older in zip(margins, margins[1:], strict=False):
                if newer <= older:
                    break
                rising += 1
            falling = 0
            for newer, older in zip(margins, margins[1:], strict=False):
                if newer >= older:
                    break
                falling += 1
            peak = max(margins[1:])
            trough = min(margins[: rising + 1]) if rising else margins[0]
            evidence = {"ttm_ebitda_margin_pct": margins[:6], "peak_margin_pct": peak}
            if rising >= 2 and peak - trough >= 2:
                stage = CONFIRMED if rising >= 4 else (EMERGING if rising == 3 else EARLY)
                out.append(
                    _signal(
                        snap,
                        history,
                        "MARGIN_EXPANDING",
                        BULL,
                        stage,
                        min(1.0, (margins[0] - trough) / 10),
                        f"EBITDA margin up {margins[0] - trough:.1f} points from its trough over {rising} quarters, to {margins[0]:.1f}%",
                        evidence,
                        "TTM EBITDA margin falls quarter on quarter",
                    )
                )
            elif falling >= 3 and margins[1] - margins[0] >= 0.5:
                out.append(
                    _signal(
                        snap,
                        history,
                        "MARGIN_COMPRESSING",
                        BEAR,
                        EMERGING if falling == 3 else CONFIRMED,
                        min(1.0, (peak - margins[0]) / 10),
                        f"EBITDA margin down for {falling} quarters, to {margins[0]:.1f}% from a peak of {peak:.1f}%",
                        evidence,
                        "TTM EBITDA margin rises quarter on quarter",
                    )
                )
        return out


class OperatingLeverage:
    """§9. TTM PAT growing at least 1.5× as fast as TTM revenue, with revenue itself growing: fixed
    costs being absorbed. Not for lenders."""

    key = "operating_leverage"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if history[0].get("is_lender") or len(history) < 8:
                continue
            rev_g = _growth(_ttm(history, "q_revenue"), _ttm(history, "q_revenue", 4))
            pat_g = _growth(_ttm(history, "q_pat"), _ttm(history, "q_pat", 4))
            if rev_g is None or pat_g is None or rev_g < 5 or pat_g < rev_g * 1.5:
                continue
            ratio = round(pat_g / rev_g, 2)
            stage = CONFIRMED if ratio >= 3 and rev_g >= 10 else EMERGING
            out.append(
                _signal(
                    snap,
                    history,
                    "OPERATING_LEVERAGE",
                    BULL,
                    stage,
                    min(1.0, ratio / 4),
                    f"TTM PAT +{pat_g:.0f}% on revenue +{rev_g:.0f}%: {ratio}× operating leverage",
                    {"ttm_revenue_growth_pct": rev_g, "ttm_pat_growth_pct": pat_g, "leverage_ratio": ratio},
                    "PAT growth falls below revenue growth",
                )
            )
        return out


class RoceInflection:
    """§10. Return on capital employed (TTM EBIT over equity plus borrowings) up at least 200bp
    against a year earlier. Not for lenders, whose capital is their business."""

    key = "roce_inflection"
    version = "1"

    @staticmethod
    def roce(history: list[Quarter], offset: int) -> float | None:
        ebit_parts = [(ebitda(q), q.get("q_depreciation")) for q in history[offset : offset + 4]]
        if len(ebit_parts) < 4 or any(e is None for e, _ in ebit_parts):
            return None
        ebit = sum((e or 0) - float(d or 0) for e, d in ebit_parts)
        equity, debt = _latest_at(history, "bs_equity", offset), _latest_at(history, "bs_borrowings", offset)
        if equity is None or equity <= 0:
            return None
        return round(ebit / (equity + (debt or 0)) * 100, 2)

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if history[0].get("is_lender") or len(history) < 8:
                continue
            now, then = self.roce(history, 0), self.roce(history, 4)
            if now is None or then is None:
                continue
            delta = round(now - then, 2)
            evidence = {"roce_pct": now, "roce_pct_year_ago": then, "change_points": delta}
            if delta >= 2 and now >= 8:
                stage = CONFIRMED if delta >= 5 and now >= 15 else EMERGING
                out.append(
                    _signal(
                        snap,
                        history,
                        "ROCE_RISING",
                        BULL,
                        stage,
                        min(1.0, delta / 10),
                        f"ROCE {now:.1f}%, up {delta:.1f} points on a year ago",
                        evidence,
                        "ROCE falls below its year-ago level",
                    )
                )
            elif delta <= -3 and then >= 10:
                out.append(
                    _signal(
                        snap,
                        history,
                        "ROCE_FALLING",
                        BEAR,
                        EMERGING,
                        min(1.0, -delta / 10),
                        f"ROCE {now:.1f}%, down {-delta:.1f} points on a year ago",
                        evidence,
                        "ROCE recovers to its year-ago level",
                    )
                )
        return out


class CashFlowInflection:
    """§11. Annual operating cash flow turning positive, or converging with profit after a year of
    weak conversion. Uses the year-end filings, which carry the cash-flow statement."""

    key = "cash_flow_inflection"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            years = _fy_ytd(history, "ytd_cfo")
            if len(years) < 2:
                continue
            (q_now, cfo_now), (q_then, cfo_then) = years[0], years[1]
            pat_now = float(q_now["ytd_pat"]) if q_now.get("ytd_pat") is not None else None
            pat_then = float(q_then["ytd_pat"]) if q_then.get("ytd_pat") is not None else None
            evidence = {
                "fy": str(q_now["period_end"]),
                "cfo_crore": round(cfo_now / 1e7, 1),
                "cfo_prev_crore": round(cfo_then / 1e7, 1),
                "pat_crore": round(pat_now / 1e7, 1) if pat_now is not None else None,
            }
            if cfo_then <= 0 < cfo_now:
                out.append(
                    _signal(
                        snap,
                        history,
                        "CFO_TURNED_POSITIVE",
                        BULL,
                        EMERGING,
                        0.6,
                        f"Operating cash flow turned positive: ₹{cfo_now / 1e7:,.0f} cr after ₹{cfo_then / 1e7:,.0f} cr",
                        evidence,
                        "Next year's operating cash flow is negative",
                    )
                )
            elif (
                pat_now
                and pat_then
                and pat_then > 0
                and cfo_then / pat_then < 0.5 <= cfo_now / pat_now
                and pat_now > 0
            ):
                out.append(
                    _signal(
                        snap,
                        history,
                        "CASH_CONVERSION_RECOVERED",
                        BULL,
                        EARLY,
                        0.4,
                        f"Cash conversion {cfo_now / pat_now:.2f}× PAT after {cfo_then / pat_then:.2f}× the year before",
                        evidence | {"cfo_to_pat": round(cfo_now / pat_now, 2)},
                        "Cash conversion falls below 0.5× again",
                    )
                )
        return out


class Deleveraging:
    """§12. Borrowings down at least 15% year on year with debt-to-equity falling; a leverage
    spike is the mirror. Not for lenders."""

    key = "deleveraging"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if history[0].get("is_lender"):
                continue
            debt_now, debt_then = _latest(history, "bs_borrowings"), _latest_at(history, "bs_borrowings", 4)
            equity = _latest(history, "bs_equity")
            if debt_now is None or debt_then is None or equity is None or equity <= 0 or debt_then <= 0:
                continue
            change = round((debt_now / debt_then - 1) * 100, 1)
            de = round(debt_now / equity, 2)
            evidence = {
                "borrowings_crore": round(debt_now / 1e7, 1),
                "borrowings_year_ago_crore": round(debt_then / 1e7, 1),
                "change_pct": change,
                "debt_to_equity": de,
            }
            if change <= -15 and debt_then / equity >= 0.3:
                stage = CONFIRMED if change <= -40 else EMERGING
                out.append(
                    _signal(
                        snap,
                        history,
                        "DELEVERAGING",
                        BULL,
                        stage,
                        min(1.0, -change / 50),
                        f"Borrowings down {-change:.0f}% in a year to {de}× equity",
                        evidence,
                        "Borrowings rise year on year",
                    )
                )
            elif change >= 30 and de >= 1.0:
                out.append(
                    _signal(
                        snap,
                        history,
                        "LEVERAGE_SPIKE",
                        BEAR,
                        EMERGING,
                        min(1.0, change / 100),
                        f"Borrowings up {change:.0f}% in a year to {de}× equity",
                        evidence,
                        "Debt-to-equity falls below 1",
                    )
                )
        return out


def _market_cap(snap: Snapshot, isin: str) -> float | None:
    price = snap.price_by_isin.get(isin)
    return float(price["market_cap"]) if price and price.get("market_cap") else None


class Valuation:
    """§13. Trailing P/E, P/B and EV/EBITDA against the priced universe; cheap or dear is the
    bottom or top quintile with positive earnings. Within-industry percentile when the industry
    has five or more members with a multiple."""

    key = "valuation"
    version = "1"

    def multiples(self, snap: Snapshot) -> dict[str, dict[str, Any]]:
        out = {}
        for isin, history in snap.fundamentals.items():
            mcap = _market_cap(snap, isin)
            if mcap is None:
                continue
            pat = _ttm(history, "q_pat_owners") or _ttm(history, "q_pat")
            equity = _latest(history, "bs_equity")
            debt, cash = _latest(history, "bs_borrowings"), _latest(history, "bs_cash")
            ttm_ebitda = _ttm_ebitda(history) if not history[0].get("is_bank") else None
            pe = round(mcap / pat, 2) if pat and pat > 0 else None
            pb = round(mcap / equity, 2) if equity and equity > 0 else None
            ev = mcap + (debt or 0) - (cash or 0)
            ev_ebitda = (
                round(ev / ttm_ebitda, 2)
                if ttm_ebitda and ttm_ebitda > 0 and not history[0].get("is_lender")
                else None
            )
            out[isin] = {
                "pe": pe,
                "pb": pb,
                "ev_ebitda": ev_ebitda,
                "ttm_pat": pat,
                "market_cap": mcap,
                "industry": (snap.industry.get(isin) or {}).get("industry"),
            }
        return out

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        multiples = self.multiples(snap)
        by_industry: dict[str, list[float]] = {}
        universe = []
        for m in multiples.values():
            if m["pe"] is not None:
                universe.append(m["pe"])
                if m["industry"]:
                    by_industry.setdefault(m["industry"], []).append(m["pe"])
        out = []
        for isin, m in multiples.items():
            if m["pe"] is None:
                continue
            peers = by_industry.get(m["industry"] or "", [])
            basis, pool = ("industry", peers) if len(peers) >= 5 else ("universe", universe)
            pct = percentile_of(pool, m["pe"])
            history = snap.fundamentals[isin]
            evidence = {
                "pe": m["pe"],
                "pb": m["pb"],
                "ev_ebitda": m["ev_ebitda"],
                "pe_percentile": pct,
                "percentile_basis": basis,
                "industry": m["industry"],
                "ttm_pat_crore": round(m["ttm_pat"] / 1e7, 1),
            }
            if pct <= 20:
                out.append(
                    _signal(
                        snap,
                        history,
                        "CHEAP_ON_EARNINGS",
                        BULL,
                        EARLY,
                        (20 - pct) / 20,
                        f"P/E {m['pe']} — bottom quintile of its {basis} ({pct:.0f}th percentile)",
                        evidence,
                        "P/E percentile rises above 40",
                        percentile=pct,
                    )
                )
            elif pct >= 90:
                out.append(
                    _signal(
                        snap,
                        history,
                        "RICH_ON_EARNINGS",
                        BEAR,
                        EARLY,
                        (pct - 90) / 10,
                        f"P/E {m['pe']} — top decile of its {basis} ({pct:.0f}th percentile)",
                        evidence,
                        "P/E percentile falls below 75",
                        percentile=pct,
                    )
                )
        return out


class UndervaluedGrowth:
    """§15. Below-median P/E with TTM PAT growing at least 15% and ROCE at least 12%."""

    key = "undervalued_growth"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        multiples = Valuation().multiples(snap)
        pes = [m["pe"] for m in multiples.values() if m["pe"] is not None]
        out = []
        for isin, m in multiples.items():
            if m["pe"] is None:
                continue
            history = snap.fundamentals[isin]
            growth = _growth(_ttm(history, "q_pat"), _ttm(history, "q_pat", 4))
            roce = RoceInflection.roce(history, 0) if not history[0].get("is_lender") else None
            pct = percentile_of(pes, m["pe"])
            if growth is None or growth < 15 or pct > 40 or (roce is not None and roce < 12):
                continue
            stage = CONFIRMED if growth >= 25 and pct <= 25 else EMERGING
            out.append(
                _signal(
                    snap,
                    history,
                    "UNDERVALUED_GROWTH",
                    BULL,
                    stage,
                    min(1.0, growth / 50 * (1 - pct / 100)),
                    f"P/E {m['pe']} ({pct:.0f}th percentile) with TTM PAT +{growth:.0f}%{f' and ROCE {roce:.0f}%' if roce is not None else ''}",
                    {"pe": m["pe"], "pe_percentile": pct, "ttm_pat_growth_pct": growth, "roce_pct": roce},
                    "PAT growth falls below 10% or the P/E percentile rises above 60",
                    percentile=100 - pct,
                )
            )
        return out


class ValueTrap:
    """§16. Cheap for a reason: bottom-quintile P/E with TTM revenue and PAT both shrinking."""

    key = "value_trap"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        multiples = Valuation().multiples(snap)
        pes = [m["pe"] for m in multiples.values() if m["pe"] is not None]
        out = []
        for isin, m in multiples.items():
            if m["pe"] is None:
                continue
            history = snap.fundamentals[isin]
            rev_g = _growth(_ttm(history, "q_revenue"), _ttm(history, "q_revenue", 4))
            pat_g = _growth(_ttm(history, "q_pat"), _ttm(history, "q_pat", 4))
            pct = percentile_of(pes, m["pe"])
            if pct > 20 or rev_g is None or pat_g is None or rev_g >= 0 or pat_g >= -10:
                continue
            out.append(
                _signal(
                    snap,
                    history,
                    "VALUE_TRAP",
                    BEAR,
                    CONFIRMED if pat_g <= -30 else EMERGING,
                    min(1.0, -pat_g / 50),
                    f"P/E {m['pe']} but revenue {rev_g:+.0f}% and PAT {pat_g:+.0f}% TTM: cheap for a reason",
                    {
                        "pe": m["pe"],
                        "pe_percentile": pct,
                        "ttm_revenue_growth_pct": rev_g,
                        "ttm_pat_growth_pct": pat_g,
                    },
                    "TTM revenue and PAT both grow again",
                )
            )
        return out


class DeepValue:
    """§17. Price below book, or EV under five times EBITDA, with positive operating cash flow in
    the latest year."""

    key = "deep_value"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for isin, m in Valuation().multiples(snap).items():
            history = snap.fundamentals[isin]
            years = _fy_ytd(history, "ytd_cfo")
            cfo_ok = bool(years) and years[0][1] > 0
            cheap_book = m["pb"] is not None and m["pb"] < 1.0
            cheap_ev = m["ev_ebitda"] is not None and 0 < m["ev_ebitda"] < 5
            if not cfo_ok or not (cheap_book or cheap_ev):
                continue
            stage = CONFIRMED if cheap_book and cheap_ev else EMERGING
            out.append(
                _signal(
                    snap,
                    history,
                    "DEEP_VALUE",
                    BULL,
                    stage,
                    0.5 + (0.25 if cheap_book else 0) + (0.25 if cheap_ev else 0),
                    ", ".join(
                        f"{label} {m[key]}"
                        for label, key in (("P/B", "pb"), ("EV/EBITDA", "ev_ebitda"))
                        if m[key] is not None
                    )
                    + " with positive operating cash flow",
                    {
                        "pb": m["pb"],
                        "ev_ebitda": m["ev_ebitda"],
                        "latest_fy_cfo_crore": round(years[0][1] / 1e7, 1),
                    },
                    "P/B rises above 1.5 and EV/EBITDA above 8",
                )
            )
        return out


class Turnaround:
    """§19. Two loss-making years followed by two profitable quarters."""

    key = "turnaround"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if len(history) < 12:
                continue
            y1, y2 = _ttm(history, "q_pat", 4), _ttm(history, "q_pat", 8)
            if y1 is None or y2 is None or y1 >= 0 or y2 >= 0:
                continue
            recent = [float(q["q_pat"]) for q in history[:2] if q.get("q_pat") is not None]
            if len(recent) < 2 or min(recent) <= 0:
                continue
            out.append(
                _signal(
                    snap,
                    history,
                    "TURNAROUND",
                    BULL,
                    EMERGING,
                    0.6,
                    f"Profitable for two quarters after losses of ₹{-y1 / 1e7:,.0f} cr and ₹{-y2 / 1e7:,.0f} cr in the two prior years",
                    {
                        "ttm_pat_year1_crore": round(y1 / 1e7, 1),
                        "ttm_pat_year2_crore": round(y2 / 1e7, 1),
                        "recent_quarters_pat_crore": [round(v / 1e7, 1) for v in recent],
                    },
                    "A loss-making quarter",
                )
            )
        return out


class AccountingQuality:
    """§34. Accruals: profit far ahead of operating cash flow for the latest year, scaled by
    assets. Not for lenders."""

    key = "accounting_quality"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if history[0].get("is_lender"):
                continue
            years = _fy_ytd(history, "ytd_cfo")
            if not years or years[0][0].get("ytd_pat") is None:
                continue
            q, cfo = years[0]
            pat, assets = float(q["ytd_pat"]), _latest(history, "bs_total_assets")
            if assets is None or assets <= 0 or pat <= 0:
                continue
            accrual = round((pat - cfo) / assets * 100, 2)
            if accrual >= 10:
                out.append(
                    _signal(
                        snap,
                        history,
                        "HIGH_ACCRUALS",
                        BEAR,
                        CONFIRMED if accrual >= 20 else EMERGING,
                        min(1.0, accrual / 30),
                        f"PAT exceeds operating cash flow by {accrual:.0f}% of assets in FY{q['period_end'].year}",
                        {
                            "fy": str(q["period_end"]),
                            "pat_crore": round(pat / 1e7, 1),
                            "cfo_crore": round(cfo / 1e7, 1),
                            "accrual_ratio_pct": accrual,
                        },
                        "Next year's cash flow catches up with profit",
                    )
                )
        return out


class ForensicScorePack:
    """§59. An Altman Z'' (non-manufacturer form) from the balance sheet and TTM EBIT: below 1.1
    is the distress zone, above 2.6 safe. Not for lenders."""

    key = "forensic_score_pack"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if history[0].get("is_lender"):
                continue
            assets, equity = _latest(history, "bs_total_assets"), _latest(history, "bs_equity")
            ca, cl = _latest(history, "bs_current_assets"), _latest(history, "bs_current_liabilities")
            parts = [(ebitda(q), q.get("q_depreciation")) for q in history[:4]]
            if assets is None or equity is None or ca is None or cl is None or len(parts) < 4:
                continue
            if any(e is None for e, _ in parts) or assets <= 0 or assets - equity <= 0:
                continue
            ebit_ttm = sum((e or 0.0) - float(d or 0) for e, d in parts)
            retained = equity - (_latest(history, "bs_share_capital") or 0.0)
            z = (
                3.25
                + 6.56 * (ca - cl) / assets
                + 3.26 * retained / assets
                + 6.72 * ebit_ttm / assets
                + 1.05 * equity / (assets - equity)
            )
            z = round(z, 2)
            if z < 1.1:
                out.append(
                    _signal(
                        snap,
                        history,
                        "ALTMAN_DISTRESS_ZONE",
                        BEAR,
                        CONFIRMED,
                        min(1.0, (1.1 - z) / 2 + 0.5),
                        f"Altman Z'' {z}: distress zone",
                        {
                            "altman_z2": z,
                            "working_capital_to_assets": round((ca - cl) / assets, 3),
                            "ebit_to_assets": round(ebit_ttm / assets, 3),
                        },
                        "Z'' rises above 1.8",
                    )
                )
        return out


class CreditDistress:
    """§68. Interest cover from TTM EBIT and finance costs with leverage: below 1× at over 1.5×
    debt-to-equity is a gate; below 1.5× a risk signal. Not for lenders."""

    key = "credit_distress"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if history[0].get("is_lender"):
                continue
            fin = _ttm(history, "q_finance_costs")
            parts = [(ebitda(q), q.get("q_depreciation")) for q in history[:4]]
            if fin is None or fin <= 0 or len(parts) < 4 or any(e is None for e, _ in parts):
                continue
            ebit = sum((e or 0) - float(d or 0) for e, d in parts)
            cover = round(ebit / fin, 2)
            equity, debt = _latest(history, "bs_equity"), _latest(history, "bs_borrowings")
            de = round(debt / equity, 2) if equity and equity > 0 and debt is not None else None
            evidence = {
                "interest_cover": cover,
                "ttm_ebit_crore": round(ebit / 1e7, 1),
                "ttm_finance_costs_crore": round(fin / 1e7, 1),
                "debt_to_equity": de,
            }
            if cover < 1 and (de is None or de > 1.5):
                out.append(
                    _signal(
                        snap,
                        history,
                        "DISTRESS",
                        GATE,
                        CONFIRMED,
                        1.0,
                        f"Interest cover {cover}× with debt {de}× equity",
                        evidence,
                        "Interest cover rises above 1.5×",
                    )
                )
            elif cover < 1.5:
                out.append(
                    _signal(
                        snap,
                        history,
                        "THIN_INTEREST_COVER",
                        BEAR,
                        EMERGING,
                        min(1.0, (1.5 - cover) + 0.3),
                        f"Interest cover {cover}×",
                        evidence,
                        "Interest cover rises above 2×",
                    )
                )
        return out


class ImpliedGrowth:
    """§14. What the price requires: with a trailing P/E read as the growth rate the market pays
    for (the PEG = 1 convention), compare it with delivered TTM PAT growth. Delivered growth far
    above the implied rate is an expectation gap; a high P/E with shrinking profit is the mirror."""

    key = "implied_growth"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for isin, m in Valuation().multiples(snap).items():
            if m["pe"] is None:
                continue
            history = snap.fundamentals[isin]
            delivered = _growth(_ttm(history, "q_pat"), _ttm(history, "q_pat", 4))
            if delivered is None:
                continue
            implied = m["pe"]
            evidence = {
                "pe": m["pe"],
                "implied_growth_pct": implied,
                "delivered_ttm_pat_growth_pct": delivered,
            }
            if delivered >= implied * 1.5 and delivered >= 20 and implied <= 40:
                out.append(
                    _signal(
                        snap,
                        history,
                        "GROWTH_EXCEEDS_IMPLIED",
                        BULL,
                        EMERGING,
                        min(1.0, (delivered - implied) / 50),
                        f"PAT growing {delivered:.0f}% against the ~{implied:.0f}% a P/E of {m['pe']} implies",
                        evidence,
                        "Delivered growth falls below the implied rate",
                    )
                )
            elif implied >= 40 and delivered < 5:
                out.append(
                    _signal(
                        snap,
                        history,
                        "PRICE_NEEDS_GROWTH",
                        BEAR,
                        EMERGING,
                        min(1.0, implied / 100),
                        f"P/E {m['pe']} with PAT growth of {delivered:+.0f}%",
                        evidence,
                        "PAT growth exceeds 15%",
                    )
                )
        return out


class ResultsReaction:
    """§58, the part that needs no consensus feed: the price move from the close before the newest
    results broadcast to three sessions after, read with the quarter's PAT change."""

    key = "consensus_reaction"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for reaction in snap.results_reactions:
            before, after = reaction["close_before"], reaction["close_after"]
            history = snap.fundamentals.get(reaction["isin"])
            if not before or not after or not history or history[0]["period_end"] != reaction["period_end"]:
                continue
            move = round((after / before - 1) * 100, 2)
            pat_g = None
            if (
                len(history) >= 5
                and history[0].get("q_pat") is not None
                and history[4].get("q_pat") is not None
            ):
                pat_g = _growth(float(history[0]["q_pat"]), float(history[4]["q_pat"]))
            evidence = {
                "broadcast": str(reaction["broadcast_at"]),
                "close_before": before,
                "close_after_3_sessions": after,
                "reaction_pct": move,
                "yoy_pat_growth_pct": pat_g,
            }
            if move >= 7:
                out.append(
                    _signal(
                        snap,
                        history,
                        "RESULTS_RERATED_UP",
                        BULL,
                        EMERGING if pat_g and pat_g > 0 else EARLY,
                        min(1.0, move / 20),
                        f"{move:+.1f}% in the three sessions after results{f' (PAT {pat_g:+.0f}% YoY)' if pat_g is not None else ''}",
                        evidence,
                        "The move retraces fully within a month",
                    )
                )
            elif move <= -7:
                out.append(
                    _signal(
                        snap,
                        history,
                        "RESULTS_RERATED_DOWN",
                        BEAR,
                        EMERGING,
                        min(1.0, -move / 20),
                        f"{move:+.1f}% in the three sessions after results{f' (PAT {pat_g:+.0f}% YoY)' if pat_g is not None else ''}",
                        evidence,
                        "The move retraces fully within a month",
                    )
                )
        return out


class CapitalAllocation:
    """§60. From the year-end cash-flow statement: free cash flow after capex, cash returned
    (dividends and buybacks) against profit, and ROCE. Discipline is positive FCF with a 20–80%
    payout and ROCE ≥ 15%; a capex binge is capex above twice operating cash flow at low ROCE."""

    key = "capital_allocation"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            if history[0].get("is_lender"):
                continue
            years = _fy_ytd(history, "ytd_cfo")
            if not years:
                continue
            q, cfo = years[0]
            capex = float(q["ytd_capex"]) if q.get("ytd_capex") is not None else None
            pat = float(q["ytd_pat"]) if q.get("ytd_pat") is not None else None
            returned = float(q.get("ytd_dividends_paid") or 0) + float(q.get("ytd_buyback") or 0)
            roce = RoceInflection.roce(history, 0)
            if capex is None or pat is None:
                continue
            fcf = cfo - capex
            payout = round(returned / pat * 100, 1) if pat > 0 else None
            evidence = {
                "fy": str(q["period_end"]),
                "cfo_crore": round(cfo / 1e7, 1),
                "capex_crore": round(capex / 1e7, 1),
                "fcf_crore": round(fcf / 1e7, 1),
                "payout_pct": payout,
                "roce_pct": roce,
            }
            if fcf > 0 and payout is not None and 20 <= payout <= 80 and roce is not None and roce >= 15:
                out.append(
                    _signal(
                        snap,
                        history,
                        "DISCIPLINED_ALLOCATOR",
                        BULL,
                        CONFIRMED if roce >= 20 else EMERGING,
                        min(1.0, roce / 30),
                        f"FCF ₹{fcf / 1e7:,.0f} cr, {payout:.0f}% of profit returned, ROCE {roce:.0f}%",
                        evidence,
                        "FCF turns negative or ROCE falls below 12%",
                    )
                )
            elif cfo > 0 and capex > 2 * cfo and (roce is None or roce < 10):
                out.append(
                    _signal(
                        snap,
                        history,
                        "CAPEX_BINGE",
                        BEAR,
                        EMERGING,
                        min(1.0, capex / cfo / 5),
                        f"Capex {capex / cfo:.1f}× operating cash flow at ROCE {roce if roce is not None else '?'}%",
                        evidence,
                        "Capex falls below operating cash flow",
                    )
                )
        return out


class UnitEconomics:
    """§104, the cash-runway half: for a loss-making company, cash and bank balances divided by
    the trailing quarterly loss. Under four quarters of runway is a risk signal, under two a gate."""

    key = "unit_economics"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out = []
        for history in snap.fundamentals.values():
            ttm = _ttm(history, "q_pat")
            cash = _latest(history, "bs_cash")
            if ttm is None or ttm >= 0 or cash is None:
                continue
            burn_per_quarter = -ttm / 4
            runway = round(cash / burn_per_quarter, 1)
            evidence = {
                "cash_crore": round(cash / 1e7, 1),
                "quarterly_burn_crore": round(burn_per_quarter / 1e7, 1),
                "runway_quarters": runway,
            }
            if runway < 2:
                out.append(
                    _signal(
                        snap,
                        history,
                        "CASH_RUNWAY_CRITICAL",
                        GATE,
                        CONFIRMED,
                        1.0,
                        f"About {runway} quarters of cash at the current burn",
                        evidence,
                        "Cash is raised or losses stop",
                    )
                )
            elif runway < 4:
                out.append(
                    _signal(
                        snap,
                        history,
                        "CASH_RUNWAY_SHORT",
                        BEAR,
                        EMERGING,
                        min(1.0, (4 - runway) / 4 + 0.3),
                        f"About {runway} quarters of cash at the current burn",
                        evidence,
                        "Runway exceeds six quarters",
                    )
                )
        return out
