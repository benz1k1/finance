"""Ownership and deal-flow engines (spec §22–§24, §65) on the shareholding filings and the bulk
and block deal history. Coverage is limited by how many quarters of filings are loaded (TODO.md):
a company with one filed quarter cannot show a change."""

from equity_engine.engines.base import BEAR, BULL, CONFIRMED, EARLY, EMERGING, Signal, Snapshot, percentile_of


def _delta(history: list[dict], key: str) -> float | None:
    if len(history) < 2 or history[0][key] is None or history[1][key] is None:
        return None
    return round(history[0][key] - history[1][key], 2)


def _inst(q: dict) -> float | None:
    if q["fii_pct"] is None and q["dii_pct"] is None:
        return None
    return round((q["fii_pct"] or 0.0) + (q["dii_pct"] or 0.0), 2)


def _streak(history: list[dict], value, rising: bool) -> int:
    """Consecutive quarter-on-quarter moves in one direction, newest first."""
    count = 0
    for newer, older in zip(history, history[1:], strict=False):
        a, b = value(newer), value(older)
        if a is None or b is None or (a <= b if rising else a >= b):
            break
        count += 1
    return count


def _stage(streak: int) -> str:
    return CONFIRMED if streak >= 3 else (EMERGING if streak == 2 else EARLY)


class InstitutionalAccumulation:
    """§23. FII plus DII holding up at least one point quarter on quarter; distribution is the
    mirror. The stage is the number of consecutive quarters the move has run."""

    key = "institutional_accumulation"
    version = "1"
    THRESHOLD = 1.0

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        deltas = {}
        for isin, history in snap.ownership.items():
            if len(history) >= 2:
                a, b = _inst(history[0]), _inst(history[1])
                if a is not None and b is not None:
                    deltas[isin] = round(a - b, 2)
        universe = list(deltas.values())
        out: list[Signal] = []
        for isin, delta in deltas.items():
            history = snap.ownership[isin]
            if abs(delta) < self.THRESHOLD:
                continue
            rising = delta > 0
            streak = _streak(history, _inst, rising)
            pct = percentile_of(universe, delta)
            evidence = {
                "institutional_pct": _inst(history[0]),
                "institutional_pct_prev": _inst(history[1]),
                "change_points": delta,
                "quarter": str(history[0]["period_end"]),
                "prev_quarter": str(history[1]["period_end"]),
                "consecutive_quarters": streak,
            }
            out.append(
                Signal(
                    isin,
                    history[0]["symbol"],
                    "INSTITUTIONAL_ACCUMULATION" if rising else "INSTITUTIONAL_DISTRIBUTION",
                    BULL if rising else BEAR,
                    _stage(streak),
                    round(min(1.0, abs(delta) / 5), 4),
                    f"Institutions {'raised' if rising else 'cut'} their stake by {abs(delta):.1f} points to {_inst(history[0]):.1f}%",
                    evidence,
                    "The next quarter's filing reverses the move",
                    percentile=pct if rising else 100 - pct,
                    price_at=snap.close(isin),
                )
            )
        return out


class PromoterActivity:
    """§22. Promoter stake moving at least one point quarter on quarter. Selling is a risk signal;
    buying a mild opportunity one. Companies with no promoter group have nothing to say here."""

    key = "promoter_activity"
    version = "1"
    THRESHOLD = 1.0

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        for isin, history in snap.ownership.items():
            delta = _delta(history, "promoter_pct")
            if delta is None or abs(delta) < self.THRESHOLD:
                continue
            rising = delta > 0
            streak = _streak(history, lambda q: q["promoter_pct"], rising)
            out.append(
                Signal(
                    isin,
                    history[0]["symbol"],
                    "PROMOTER_BUYING" if rising else "PROMOTER_SELLING",
                    BULL if rising else BEAR,
                    _stage(streak),
                    round(min(1.0, abs(delta) / 5), 4),
                    f"Promoters {'raised' if rising else 'cut'} their stake by {abs(delta):.1f} points to {history[0]['promoter_pct']:.1f}%",
                    {
                        "promoter_pct": history[0]["promoter_pct"],
                        "promoter_pct_prev": history[1]["promoter_pct"],
                        "change_points": delta,
                        "quarter": str(history[0]["period_end"]),
                        "consecutive_quarters": streak,
                    },
                    "The next quarter's filing reverses the move",
                    price_at=snap.close(isin),
                )
            )
        return out


class SmartMoneyDivergence:
    """§24. Institutions accumulating while the price has gone nowhere over six months."""

    key = "smart_money_divergence"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        prices = snap.price_by_isin
        for isin, history in snap.ownership.items():
            if len(history) < 2:
                continue
            a, b = _inst(history[0]), _inst(history[1])
            price = prices.get(isin)
            if a is None or b is None or price is None or not price["c6m"]:
                continue
            delta = round(a - b, 2)
            ret6 = round((price["close"] / price["c6m"] - 1) * 100, 2)
            if delta >= 1.0 and ret6 <= 0:
                streak = _streak(history, _inst, True)
                out.append(
                    Signal(
                        isin,
                        history[0]["symbol"],
                        "ACCUMULATION_FLAT_PRICE",
                        BULL,
                        _stage(streak),
                        round(min(1.0, delta / 5), 4),
                        f"Institutions up {delta:.1f} points while the price is {ret6:+.0f}% over 6 months",
                        {
                            "institutional_change_points": delta,
                            "return_6m_pct": ret6,
                            "quarter": str(history[0]["period_end"]),
                        },
                        "Institutions sell in the next filing, or the price re-rates above +25% over 6 months",
                        price_at=snap.close(isin),
                    )
                )
        return out


class InsiderDealFlow:
    """§65. Net bulk and block buying over the last 90 days measured against market cap (or, when
    market cap is unknown, against 20-day average turnover). Large, one-sided deal flow by named
    counterparties is informative in both directions."""

    key = "insider_deal_flow"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        prices = snap.price_by_isin
        for deal in snap.deals:
            net = deal["buy_value"] - deal["sell_value"]
            gross = deal["buy_value"] + deal["sell_value"]
            if gross <= 0 or abs(net) / gross < 0.6:
                continue  # two-sided: a transfer between parties, not a position
            price = prices.get(deal["isin"])
            if price is None:
                continue
            if price["market_cap"]:
                share = abs(net) / price["market_cap"] * 100
                basis, floor = "market_cap_pct", 1.0
            elif price["t20"]:
                share = abs(net) / price["t20"]
                basis, floor = "days_of_turnover", 20.0
            else:
                continue
            if share < floor:
                continue
            buying = net > 0
            stage = CONFIRMED if share >= floor * 5 else (EMERGING if share >= floor * 2 else EARLY)
            crore = abs(net) / 1e7
            out.append(
                Signal(
                    deal["isin"],
                    deal["symbol"],
                    "NET_DEAL_BUYING" if buying else "NET_DEAL_SELLING",
                    BULL if buying else BEAR,
                    stage,
                    round(min(1.0, share / (floor * 5)), 4),
                    f"Net {'buying' if buying else 'selling'} of ₹{crore:,.0f} cr in bulk/block deals over 90 days",
                    {
                        "net_value": round(net, 2),
                        "buy_value": deal["buy_value"],
                        "sell_value": deal["sell_value"],
                        "deals": deal["deals"],
                        "distinct_buyers": deal["buyers"],
                        basis: round(share, 2),
                    },
                    "Deal flow reverses direction over the next 90 days",
                    price_at=snap.close(deal["isin"]),
                )
            )
        return out
