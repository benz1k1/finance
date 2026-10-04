"""Event-driven engines on the corporate-action table and the listing calendar (spec §30, §36,
§66). Announcements and documents (Phase 3) will add to them; what is here needs no document."""

from datetime import timedelta

from equity_engine.engines.base import BEAR, BULL, EARLY, EMERGING, Signal, Snapshot


class CorporateEvent:
    """§30. Dated actions with an ex-date in the next 30 days, read from the exchange's own
    bundle: a buyback or bonus/split is a mild positive (capital return, liquidity), a rights
    issue a dilution warning, a large dividend relative to price a yield marker."""

    key = "corporate_event"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        prices = snap.price_by_isin
        for action in snap.actions:
            if action["ex_date"] <= snap.as_of:
                continue
            price = prices.get(action["isin"])
            if price is None:
                continue
            days = (action["ex_date"] - snap.as_of).days
            evidence = {
                "ex_date": str(action["ex_date"]),
                "purpose": action["purpose"],
                "days_to_ex": days,
                "announced": str(action["first_seen"]),
            }
            kind = action["kind"]
            if kind == "BUYBACK":
                out.append(
                    Signal(
                        action["isin"],
                        action["symbol"],
                        "BUYBACK_AHEAD",
                        BULL,
                        EMERGING,
                        0.6,
                        f"Buyback record date in {days} days",
                        evidence,
                        "The ex-date passes",
                        price_at=snap.close(action["isin"]),
                    )
                )
            elif kind in ("BONUS", "SPLIT"):
                out.append(
                    Signal(
                        action["isin"],
                        action["symbol"],
                        f"{kind}_AHEAD",
                        BULL,
                        EARLY,
                        0.3,
                        f"{kind.title()} ({action['purpose']}) ex-date in {days} days",
                        evidence,
                        "The ex-date passes",
                        price_at=snap.close(action["isin"]),
                    )
                )
            elif kind == "RIGHTS":
                out.append(
                    Signal(
                        action["isin"],
                        action["symbol"],
                        "RIGHTS_ISSUE_AHEAD",
                        BEAR,
                        EARLY,
                        0.3,
                        f"Rights issue ({action['purpose']}) ex-date in {days} days: dilution",
                        evidence,
                        "The ex-date passes",
                        price_at=snap.close(action["isin"]),
                    )
                )
            elif kind == "DIVIDEND" and action["amount"] and price["raw_close"]:
                yield_pct = action["amount"] / float(price["raw_close"]) * 100
                if yield_pct >= 3:
                    out.append(
                        Signal(
                            action["isin"],
                            action["symbol"],
                            "HIGH_DIVIDEND_AHEAD",
                            BULL,
                            EARLY,
                            round(min(1.0, yield_pct / 10), 4),
                            f"Dividend of ₹{action['amount']:g} going ex in {days} days, {yield_pct:.1f}% of price",
                            evidence | {"yield_pct": round(yield_pct, 2)},
                            "The ex-date passes",
                            price_at=snap.close(action["isin"]),
                        )
                    )
            elif kind == "DEMERGER":
                out.append(
                    Signal(
                        action["isin"],
                        action["symbol"],
                        "DEMERGER_AHEAD",
                        BULL,
                        EMERGING,
                        0.5,
                        f"Demerger record date in {days} days",
                        evidence,
                        "The ex-date passes",
                        price_at=snap.close(action["isin"]),
                    )
                )
        return out


class IpoNewlyListed:
    """§36. Companies listed within the last year: performance since listing versus the first
    close, and the lock-in calendar (anchor investors at 90 days, pre-IPO holders at 6 and 18
    months) that governs their supply."""

    key = "ipo_newly_listed"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        prices = snap.price_by_isin
        for listing in snap.listings:
            listed = listing["listing_date"]
            age = (snap.as_of - listed).days
            if age < 30 or age > 365:
                continue
            price = prices.get(listing["isin"])
            if price is None or price["n"] < 20:
                continue
            ret3 = (price["close"] / price["c3m"] - 1) * 100 if price["c3m"] else None
            evidence = {
                "listing_date": str(listed),
                "days_listed": age,
                "return_3m_pct": round(ret3, 2) if ret3 is not None else None,
                "from_52w_high_pct": round((price["close"] / price["hi252"] - 1) * 100, 2)
                if price["hi252"]
                else None,
            }
            if ret3 is not None and ret3 >= 25 and price["close"] >= price["hi252"] * 0.95:
                out.append(
                    Signal(
                        listing["isin"],
                        listing["symbol"],
                        "NEW_LISTING_LEADER",
                        BULL,
                        EMERGING,
                        round(min(1.0, ret3 / 100), 4),
                        f"Listed {age} days ago, +{ret3:.0f}% over 3 months and near its high",
                        evidence,
                        "Falls more than 15% from its high",
                        price_at=snap.close(listing["isin"]),
                    )
                )
            elif ret3 is not None and ret3 <= -25:
                out.append(
                    Signal(
                        listing["isin"],
                        listing["symbol"],
                        "NEW_LISTING_LAGGARD",
                        BEAR,
                        EMERGING,
                        round(min(1.0, -ret3 / 100), 4),
                        f"Listed {age} days ago, {ret3:.0f}% over 3 months",
                        evidence,
                        "Recovers above its 50-day average",
                        price_at=snap.close(listing["isin"]),
                    )
                )
        return out


class SupplyOverhang:
    """§66. Known future supply: pre-IPO lock-in expiries (6 and 18 months after listing, the
    SEBI windows) falling in the next 30 days, and promoters cutting their stake while deal
    flow is net selling. Pledge data joins this once its feed is loaded."""

    key = "supply_overhang"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        prices = snap.price_by_isin
        for listing in snap.listings:
            listed = listing["listing_date"]
            for months, label in ((6, "6-month pre-IPO lock-in"), (18, "18-month promoter lock-in")):
                expiry = listed + timedelta(days=months * 30)
                days = (expiry - snap.as_of).days
                if 0 <= days <= 30 and listing["isin"] in prices:
                    out.append(
                        Signal(
                            listing["isin"],
                            listing["symbol"],
                            "LOCKIN_EXPIRY_AHEAD",
                            BEAR,
                            EARLY,
                            0.4,
                            f"{label} ends in about {days} days",
                            {"listing_date": str(listed), "expiry": str(expiry), "window": label},
                            "The expiry passes without unusual volume",
                            price_at=snap.close(listing["isin"]),
                        )
                    )
        deals = {d["isin"]: d for d in snap.deals}
        for isin, history in snap.ownership.items():
            if len(history) < 2 or history[0]["promoter_pct"] is None or history[1]["promoter_pct"] is None:
                continue
            drop = history[1]["promoter_pct"] - history[0]["promoter_pct"]
            deal = deals.get(isin)
            if drop >= 2.0 and deal and deal["sell_value"] > deal["buy_value"] * 2:
                out.append(
                    Signal(
                        isin,
                        history[0]["symbol"],
                        "PROMOTER_SUPPLY",
                        BEAR,
                        EMERGING,
                        round(min(1.0, drop / 10), 4),
                        f"Promoters down {drop:.1f} points with net deal selling of ₹{(deal['sell_value'] - deal['buy_value']) / 1e7:,.0f} cr",
                        {
                            "promoter_drop_points": round(drop, 2),
                            "deal_sell_value": deal["sell_value"],
                            "deal_buy_value": deal["buy_value"],
                        },
                        "Promoter stake stabilises in the next filing",
                        price_at=snap.close(isin),
                    )
                )
        return out
