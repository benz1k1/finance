"""Market-level engines (spec §28, §29). Sector rotation emits a per-security signal from its
industry's relative return; market regime emits none, and instead describes the whole market
for the run (stored in ``market_regime`` by the runner)."""

from typing import Any

from equity_engine.engines.base import BEAR, BULL, CONFIRMED, EARLY, EMERGING, Signal, Snapshot


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


class SectorRotation:
    """§28. Each industry's median 3-month return against the universe median, and whether that
    gap widened since the 6-month window. A security in a leading, improving industry gets a
    tailwind signal; in a lagging, worsening one a headwind."""

    key = "sector_rotation"
    version = "2"  # v2: a signal only for the members the industry figures were computed from
    MIN_MEMBERS = 5

    def industries(self, snap: Snapshot) -> dict[str, dict[str, Any]]:
        self._counted: set[str] = set()
        prices = snap.price_by_isin
        r3_all, r6_all = [], []
        groups: dict[str, list[tuple[float, float]]] = {}
        for isin, meta in snap.industry.items():
            p = prices.get(isin)
            if p is None or not p["c3m"] or not p["c6m"] or not meta["industry"]:
                continue
            r3 = (p["close"] / p["c3m"] - 1) * 100
            r6 = (p["close"] / p["c6m"] - 1) * 100
            r3_all.append(r3)
            r6_all.append(r6)
            groups.setdefault(meta["industry"], []).append((r3, r6))
            self._counted.add(isin)
        m3, m6 = _median(r3_all), _median(r6_all)
        if m3 is None or m6 is None:
            return {}
        out = {}
        for industry, pairs in groups.items():
            if len(pairs) < self.MIN_MEMBERS:
                continue
            rel3 = (_median([a for a, _ in pairs]) or 0) - m3
            rel6 = (_median([b for _, b in pairs]) or 0) - m6
            out[industry] = {
                "industry": industry,
                "members": len(pairs),
                "rel_3m": round(rel3, 2),
                "rel_6m": round(rel6, 2),
                "improving": rel3 > rel6 / 2,
            }
        return out

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        ranked = self.industries(snap)
        if not ranked:
            return []
        ordered = sorted(ranked.values(), key=lambda i: i["rel_3m"])
        quartile = max(1, len(ordered) // 4)
        leaders = {i["industry"] for i in ordered[-quartile:] if i["rel_3m"] > 0}
        laggards = {i["industry"] for i in ordered[:quartile] if i["rel_3m"] < 0}
        out: list[Signal] = []
        for isin, meta in snap.industry.items():
            industry = meta["industry"]
            info = ranked.get(industry)
            if info is None or isin not in self._counted:
                continue
            if industry in leaders:
                stage = (
                    CONFIRMED
                    if info["improving"] and info["rel_6m"] > 0
                    else (EMERGING if info["improving"] else EARLY)
                )
                out.append(
                    Signal(
                        isin,
                        snap.price_by_isin[isin]["symbol"],
                        "SECTOR_TAILWIND",
                        BULL,
                        stage,
                        round(min(1.0, info["rel_3m"] / 20), 4),
                        f"{industry}: {info['rel_3m']:+.1f} points vs the market over 3 months{', improving' if info['improving'] else ''}",
                        info,
                        "The industry's relative 3-month return turns negative",
                        price_at=snap.close(isin),
                    )
                )
            elif industry in laggards:
                stage = CONFIRMED if not info["improving"] and info["rel_6m"] < 0 else EMERGING
                out.append(
                    Signal(
                        isin,
                        snap.price_by_isin[isin]["symbol"],
                        "SECTOR_HEADWIND",
                        BEAR,
                        stage,
                        round(min(1.0, -info["rel_3m"] / 20), 4),
                        f"{industry}: {info['rel_3m']:+.1f} points vs the market over 3 months",
                        info,
                        "The industry's relative 3-month return turns positive",
                        price_at=snap.close(isin),
                    )
                )
        return out


class MarketRegime:
    """§29. Breadth and trend of the whole priced universe. No per-security signal; ``describe``
    gives the run's regime row: RISK_ON when most names are above their 200-day average and the
    median 3-month return is positive, RISK_OFF when both are weak, otherwise MIXED."""

    key = "market_regime"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        return []

    def describe(self, snap: Snapshot) -> dict[str, Any]:
        priced = [p for p in snap.prices if p["sma200"] is not None and p["n"] >= 200]
        above = sum(1 for p in priced if p["close"] > p["sma200"])
        returns = [(p["close"] / p["c3m"] - 1) * 100 for p in priced if p["c3m"]]
        advancing = sum(1 for p in snap.prices if p["c1m"] and p["close"] > p["c1m"])
        above_pct = round(100 * above / len(priced), 1) if priced else None
        median3 = _median(returns)
        if above_pct is None or median3 is None:
            regime = "UNKNOWN"
        elif above_pct >= 60 and median3 > 0:
            regime = "RISK_ON"
        elif above_pct <= 40 and median3 < 0:
            regime = "RISK_OFF"
        else:
            regime = "MIXED"
        world = snap.global_context
        return {
            "as_of": snap.as_of,
            "global_3m_pct": world["median_3m_pct"] if world else None,
            "global_stress": world["stress"] if world else None,
            "global_indexes": world["indexes"] if world else None,
            "universe": len(snap.prices),
            "with_200dma": len(priced),
            "above_200dma": above,
            "above_200dma_pct": above_pct,
            "advancing_1m": advancing,
            "median_return_3m_pct": round(median3, 1) if median3 is not None else None,
            "advancing_1m_pct": round(100 * advancing / len(snap.prices), 1) if snap.prices else None,
            "regime": regime,
        }
