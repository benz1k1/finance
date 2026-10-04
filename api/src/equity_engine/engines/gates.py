"""Gates (spec §69, §69.2): what removes a security from any stance. A gate is shown with its
reason, never applied silently (§118)."""

from equity_engine.engines.base import BEAR, CONFIRMED, EARLY, EMERGING, GATE, Signal, Snapshot

LIQUIDITY_FLOOR_RUPEES = 1e7  # ₹1 crore median daily turnover over 60 sessions


class Investability:
    """§69. Hard exclusions (trade-for-trade series, ESM and GSM) and an illiquidity floor are
    gates. ASM membership is a warning, not a gate, as the spec says."""

    key = "investability"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        prices = snap.price_by_isin
        for isin, labels in snap.excluded.items():
            price = prices.get(isin)
            symbol = price["symbol"] if price else snap.symbol_of(isin)
            out.append(
                Signal(
                    isin,
                    symbol,
                    "EXCLUDED",
                    GATE,
                    CONFIRMED,
                    1.0,
                    f"Excluded from the universe: {', '.join(labels)}",
                    {"labels": labels},
                    "The security leaves the series or surveillance list",
                    price_at=snap.close(isin),
                )
            )
        for p in snap.prices:
            if p["isin"] in snap.excluded or p["n"] < 60 or p["med_t60"] is None:
                continue
            if p["med_t60"] < LIQUIDITY_FLOOR_RUPEES:
                lakh = p["med_t60"] / 1e5
                out.append(
                    Signal(
                        p["isin"],
                        p["symbol"],
                        "ILLIQUID",
                        GATE,
                        CONFIRMED,
                        1.0,
                        f"Median daily turnover ₹{lakh:,.0f} lakh over 60 sessions, below the ₹1 cr floor",
                        {"median_turnover_60d": round(p["med_t60"], 2), "floor": LIQUIDITY_FLOOR_RUPEES},
                        "Median turnover rises above the floor",
                        price_at=snap.close(p["isin"]),
                    )
                )
        for isin, label in snap.asm.items():
            if isin in snap.excluded:
                continue
            price = prices.get(isin)
            out.append(
                Signal(
                    isin,
                    price["symbol"] if price else snap.symbol_of(isin),
                    "SURVEILLANCE_ASM",
                    BEAR,
                    EARLY,
                    0.5,
                    f"On NSE's additional surveillance list ({label})",
                    {"list": label},
                    "Removed from the ASM list",
                    price_at=snap.close(isin),
                )
            )
        return out


class ManipulationRisk:
    """§69.2, rules first. A steep run-up on thin turnover with low delivery is the classic
    operator pattern: a gate when extreme, a risk signal when merely suspicious."""

    key = "manipulation_risk"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        for p in snap.prices:
            if (
                p["isin"] in snap.excluded
                or p["n"] < 127
                or not p["c6m"]
                or p["med_d60"] is None
                or p["med_t60"] is None
            ):
                continue
            ret6 = (p["close"] / p["c6m"] - 1) * 100
            thin = p["med_t60"] < 2e7
            evidence = {
                "return_6m_pct": round(ret6, 2),
                "median_delivery_60d": round(float(p["med_d60"]), 2),
                "median_turnover_60d_crore": round(p["med_t60"] / 1e7, 2),
            }
            if ret6 >= 150 and p["med_d60"] < 30 and thin:
                out.append(
                    Signal(
                        p["isin"],
                        p["symbol"],
                        "OPERATOR_PATTERN",
                        GATE,
                        CONFIRMED,
                        1.0,
                        f"+{ret6:.0f}% in 6 months on thin turnover with {p['med_d60']:.0f}% median delivery",
                        evidence,
                        "Delivery median rises above 40% or the run-up unwinds",
                        price_at=snap.close(p["isin"]),
                    )
                )
            elif ret6 >= 100 and p["med_d60"] < 35:
                out.append(
                    Signal(
                        p["isin"],
                        p["symbol"],
                        "SUSPECT_RUN_UP",
                        BEAR,
                        EMERGING,
                        0.6,
                        f"+{ret6:.0f}% in 6 months with only {p['med_d60']:.0f}% median delivery",
                        evidence,
                        "Delivery median rises above 45%",
                        price_at=snap.close(p["isin"]),
                    )
                )
        return out
