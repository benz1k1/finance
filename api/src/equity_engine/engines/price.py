"""Price-only engines (spec §25–§27): relative strength, trend, volume and delivery. Full
coverage from day one because every security has prices; raw (unadjusted) closes, so a split or
bonus shows as a false drop until corporate-action adjustment lands (TODO.md)."""

from equity_engine.engines.base import BEAR, BULL, CONFIRMED, EARLY, EMERGING, Signal, Snapshot, percentile_of


def _ret(now: float | None, then: float | None) -> float | None:
    if now is None or then is None or then <= 0:
        return None
    return round((now / then - 1.0) * 100.0, 2)


class RelativeStrength:
    """§26. Return over 6 and 12 months ranked within the priced universe. A leader sits in the top
    quintile on both; a laggard in the bottom quintile on both. Persistence over the shorter 3-month
    window is what promotes the stage."""

    key = "relative_strength"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        feats = [p for p in snap.prices if p["c6m"] is not None and p["c12m"] is not None and p["n"] >= 253]
        r6 = {p["isin"]: _ret(p["close"], p["c6m"]) for p in feats}
        r12 = {p["isin"]: _ret(p["close"], p["c12m"]) for p in feats}
        r3 = {p["isin"]: _ret(p["close"], p["c3m"]) for p in feats}
        all6 = [v for v in r6.values() if v is not None]
        all12 = [v for v in r12.values() if v is not None]
        all3 = [v for v in r3.values() if v is not None]
        out: list[Signal] = []
        for p in feats:
            isin = p["isin"]
            r6_value, r12_value = r6[isin], r12[isin]
            if r6_value is None or r12_value is None:
                continue
            p6, p12 = percentile_of(all6, r6_value), percentile_of(all12, r12_value)
            r3_value = r3[isin]
            p3 = percentile_of(all3, r3_value) if r3_value is not None else 50.0
            evidence = {
                "return_6m_pct": r6[isin],
                "return_12m_pct": r12[isin],
                "return_3m_pct": r3[isin],
                "percentile_6m": p6,
                "percentile_12m": p12,
                "percentile_3m": p3,
            }
            if p6 >= 80 and p12 >= 80:
                stage = CONFIRMED if p3 >= 70 else (EMERGING if p3 >= 50 else EARLY)
                out.append(
                    Signal(
                        isin,
                        p["symbol"],
                        "RS_LEADER",
                        BULL,
                        stage,
                        round(min(p6, p12) / 100, 4),
                        f"Top-quintile return over 6m ({r6[isin]:+.0f}%) and 12m ({r12[isin]:+.0f}%)",
                        evidence,
                        "6-month return percentile falls below 60",
                        percentile=min(p6, p12),
                        price_at=snap.close(isin),
                    )
                )
            elif p6 <= 20 and p12 <= 20:
                stage = CONFIRMED if p3 <= 30 else (EMERGING if p3 <= 50 else EARLY)
                out.append(
                    Signal(
                        isin,
                        p["symbol"],
                        "RS_LAGGARD",
                        BEAR,
                        stage,
                        round(1 - max(p6, p12) / 100, 4),
                        f"Bottom-quintile return over 6m ({r6[isin]:+.0f}%) and 12m ({r12[isin]:+.0f}%)",
                        evidence,
                        "6-month return percentile rises above 40",
                        percentile=max(p6, p12),
                        price_at=snap.close(isin),
                    )
                )
        return out


def _from_extreme(pct: float | None, which: str) -> str:
    if pct is None:
        return f"52-week {which} unknown"
    return f"at its 52-week {which}" if abs(pct) < 0.5 else f"{pct:+.0f}% from 52-week {which}"


class TechnicalPrice:
    """§25. Trend from the 50- and 200-row averages of the close. Up-trend: close above a rising
    50-day average that is above the 200-day; confirmed when within 5% of the 52-week high."""

    key = "technical_price"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        for p in snap.prices:
            if p["n"] < 220 or p["sma50"] is None or p["sma200"] is None or p["sma200_prev"] is None:
                continue
            close, sma50, sma200 = p["close"], p["sma50"], p["sma200"]
            slope = _ret(sma200, p["sma200_prev"])
            from_high, from_low = _ret(close, p["hi252"]), _ret(close, p["lo252"])
            evidence = {
                "close": close,
                "sma50": round(sma50, 2),
                "sma200": round(sma200, 2),
                "sma200_slope_pct": slope,
                "from_52w_high_pct": from_high,
                "from_52w_low_pct": from_low,
            }
            if close > sma50 > sma200 and slope is not None and slope > 0:
                stage = CONFIRMED if from_high is not None and from_high >= -5 else EMERGING
                out.append(
                    Signal(
                        p["isin"],
                        p["symbol"],
                        "TREND_UP",
                        BULL,
                        stage,
                        round(min(1.0, (close / sma200 - 1) * 2), 4),
                        f"Close above rising 50- and 200-day averages, {_from_extreme(from_high, 'high')}",
                        evidence,
                        "Close falls below the 200-day average",
                        price_at=snap.close(p["isin"]),
                    )
                )
            elif close < sma50 < sma200 and slope is not None and slope < 0:
                stage = CONFIRMED if from_low is not None and from_low <= 5 else EMERGING
                out.append(
                    Signal(
                        p["isin"],
                        p["symbol"],
                        "TREND_DOWN",
                        BEAR,
                        stage,
                        round(min(1.0, (1 - close / sma200) * 2), 4),
                        f"Close below falling 50- and 200-day averages, {_from_extreme(from_low, 'low')}",
                        evidence,
                        "Close rises above the 200-day average",
                        price_at=snap.close(p["isin"]),
                    )
                )
        return out


class VolumeDelivery:
    """§27. Turnover in the last 20 sessions at least twice the 120-session average while the
    median delivery percentage also rose: volume that is being taken home, not churned."""

    key = "volume_delivery"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        for p in snap.prices:
            if p["n"] < 120 or not p["t120"] or p["med_d20"] is None or p["med_d120"] is None:
                continue
            ratio = p["t20"] / p["t120"]
            delta_delivery = p["med_d20"] - p["med_d120"]
            if ratio >= 2.0 and delta_delivery >= 5.0 and _ret(p["close"], p["c1m"]) is not None:
                stage = (
                    CONFIRMED if ratio >= 4 and delta_delivery >= 15 else (EMERGING if ratio >= 3 else EARLY)
                )
                out.append(
                    Signal(
                        p["isin"],
                        p["symbol"],
                        "DELIVERY_VOLUME_SURGE",
                        BULL,
                        stage,
                        round(min(1.0, ratio / 5), 4),
                        f"Turnover {ratio:.1f}× its 120-day average with delivery up {delta_delivery:.0f} points",
                        {
                            "turnover_20d_vs_120d": round(ratio, 2),
                            "median_delivery_20d": p["med_d20"],
                            "median_delivery_120d": p["med_d120"],
                            "return_1m_pct": _ret(p["close"], p["c1m"]),
                        },
                        "Turnover ratio falls below 1.2× or delivery median returns to its 120-day level",
                        price_at=snap.close(p["isin"]),
                    )
                )
        return out
