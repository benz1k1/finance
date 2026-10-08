"""
Engines that read Indian prices against the world (spec §120, §121; decided 2026-10-04).

``GlobalResilience``: when the world is in a drawdown, the companies worth owning are the ones
whose price has held up *and* whose business justifies it — not the ones that merely fell less by
accident. ``HistoricalPE``: a company's own P/E at past stress troughs and expansion peaks is the
yardstick for whether today's P/E has already priced a recession or has yet to.
"""

from statistics import median

from equity_engine.engines.base import BEAR, BULL, CONFIRMED, EMERGING, Signal, Snapshot
from equity_engine.engines.fundamentals import RoceInflection, _growth, _ttm

OUTPERFORM_POINTS = 10.0  # 3-month return at least this far above the global median
INDIA_STRESS_3M_PCT = -5.0


class GlobalResilience:
    """§120. Only while the world is in a drawdown (median global index down 5% over 3 months, or
    three of five below their 200-day average): a security whose 3-month return beats the global
    median by 10 points with ROCE ≥ 12% and TTM profit not shrinking is RESILIENT_IN_GLOBAL_SELLOFF;
    confirmed when its 6-month return is positive too. The mirror, GLOBAL_BETA_SELLOFF, is a name
    that fell 10 points more than the world while its profit shrank — the fall is not only the tide."""

    key = "global_resilience"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        world = snap.global_context
        if not world or not world["stress"]:
            return []
        world_3m = world["median_3m_pct"]
        out: list[Signal] = []
        for isin, p in snap.price_by_isin.items():
            if not p.get("c3m") or not p.get("c6m"):
                continue
            ret3 = (p["close"] / p["c3m"] - 1) * 100
            ret6 = (p["close"] / p["c6m"] - 1) * 100
            history = snap.fundamentals.get(isin) or []
            roce = RoceInflection.roce(history, 0) if history and not history[0].get("is_lender") else None
            pat_growth = (
                _growth(_ttm(history, "q_pat"), _ttm(history, "q_pat", 4)) if len(history) >= 8 else None
            )
            evidence = {
                "return_3m_pct": round(ret3, 2),
                "return_6m_pct": round(ret6, 2),
                "world_median_3m_pct": world_3m,
                "gap_points": round(ret3 - world_3m, 2),
                "roce_pct": roce,
                "ttm_pat_growth_pct": pat_growth,
                "world": {code: i["ret_3m_pct"] for code, i in world["indexes"].items()},
            }
            if (
                ret3 - world_3m >= OUTPERFORM_POINTS
                and roce is not None
                and roce >= 12
                and (pat_growth is None or pat_growth >= 0)
            ):
                out.append(
                    Signal(
                        isin,
                        p["symbol"],
                        "RESILIENT_IN_GLOBAL_SELLOFF",
                        BULL,
                        CONFIRMED if ret6 > 0 else EMERGING,
                        round(min(1.0, (ret3 - world_3m) / 30), 4),
                        f"{ret3:+.0f}% over 3 months while the world median is {world_3m:+.0f}%, with ROCE {roce:.0f}%"
                        + (f" and TTM profit {pat_growth:+.0f}%" if pat_growth is not None else ""),
                        evidence,
                        "Its 3-month return falls below the global median, or ROCE drops under 12%",
                        price_at=snap.close(isin),
                    )
                )
            elif ret3 - world_3m <= -OUTPERFORM_POINTS and pat_growth is not None and pat_growth < 0:
                out.append(
                    Signal(
                        isin,
                        p["symbol"],
                        "GLOBAL_BETA_SELLOFF",
                        BEAR,
                        EMERGING,
                        round(min(1.0, (world_3m - ret3) / 30), 4),
                        f"{ret3:+.0f}% over 3 months against a world median of {world_3m:+.0f}%, with TTM profit {pat_growth:+.0f}%",
                        evidence,
                        "It stops underperforming the world, or profit growth turns positive",
                        price_at=snap.close(isin),
                    )
                )
        return out


class HistoricalPE:
    """§121. The company's own P/E on past stress dates (Indian median 3-month return ≤ −10%) and
    expansion dates (≥ +10%), each sampled monthly from the regime history, against today's P/E.
    BELOW_RECESSION_PE: today's P/E is at least 10% under its median stress-date P/E while TTM profit
    is not shrinking — the price has de-rated past crisis levels without earnings doing so.
    PE_YET_TO_DERATE: in a stressed market today's P/E still sits at or above its expansion-date
    median while profit shrinks."""

    key = "historical_pe"
    version = "1"
    MIN_DATES = 3

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        reference = snap.pe_reference  # isin -> {"stress": [pe...], "expansion": [pe...], "all": [pe...]}
        if not reference:
            return []
        india_stressed = (
            snap.market_median_3m_pct is not None and snap.market_median_3m_pct <= INDIA_STRESS_3M_PCT
        ) or bool(snap.global_context and snap.global_context["stress"])
        out: list[Signal] = []
        for isin, p in snap.price_by_isin.items():
            ref = reference.get(isin)
            history = snap.fundamentals.get(isin) or []
            if not ref or not p.get("market_cap") or len(history) < 4:
                continue
            ttm_pat = _ttm(history, "q_pat")
            if not ttm_pat or ttm_pat <= 0:
                continue
            pe_now = p["market_cap"] / ttm_pat
            pat_growth = _growth(ttm_pat, _ttm(history, "q_pat", 4)) if len(history) >= 8 else None
            stress, expansion, every = ref["stress"], ref["expansion"], ref["all"]
            own_pct = round(100 * sum(1 for x in every if x < pe_now) / len(every), 1) if every else None
            evidence = {
                "pe_now": round(pe_now, 1),
                "recession_pe_median": round(median(stress), 1) if stress else None,
                "recession_pe_min": round(min(stress), 1) if stress else None,
                "recession_dates": len(stress),
                "expansion_pe_median": round(median(expansion), 1) if expansion else None,
                "expansion_dates": len(expansion),
                "own_history_percentile": own_pct,
                "ttm_pat_growth_pct": pat_growth,
                "india_stressed": india_stressed,
            }
            if (
                len(stress) >= self.MIN_DATES
                and pe_now <= 0.9 * median(stress)
                and (pat_growth is None or pat_growth >= 0)
            ):
                rec = median(stress)
                out.append(
                    Signal(
                        isin,
                        p["symbol"],
                        "BELOW_RECESSION_PE",
                        BULL,
                        CONFIRMED if pe_now < min(stress) else EMERGING,
                        round(min(1.0, (1 - pe_now / rec) / 0.3), 4),
                        f"P/E {pe_now:.1f}, below the {rec:.1f} it fell to at its past {len(stress)} stress troughs"
                        + (f", with TTM profit {pat_growth:+.0f}%" if pat_growth is not None else ""),
                        evidence,
                        "P/E re-rates above its stress-date median, or TTM profit turns down",
                        price_at=snap.close(isin),
                    )
                )
            elif (
                india_stressed
                and len(expansion) >= self.MIN_DATES
                and pe_now >= median(expansion)
                and pat_growth is not None
                and pat_growth < 0
            ):
                exp = median(expansion)
                out.append(
                    Signal(
                        isin,
                        p["symbol"],
                        "PE_YET_TO_DERATE",
                        BEAR,
                        EMERGING,
                        round(min(1.0, (pe_now / exp - 1) / 0.5 + 0.3), 4),
                        f"P/E {pe_now:.1f}, {'above' if pe_now > exp * 1.02 else 'at'} its boom-time median of {exp:.1f}, "
                        f"while TTM profit is {pat_growth:+.0f}% in a stressed market: the price has not de-rated",
                        evidence,
                        "P/E falls below its expansion-date median, or profit growth turns positive",
                        price_at=snap.close(isin),
                    )
                )
        return out
