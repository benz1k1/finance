"""Engines on announcements, the event calendar, rating disclosures and the derivatives position
(spec §35, §37, §68 ratings, §70). Announcement kinds are the rule-based classification in
parsers/filings.classify_announcement; the LLM pass (Phase 3) refines them later."""

from collections import Counter
from typing import Any

from equity_engine.engines.base import BEAR, BULL, CONFIRMED, EARLY, EMERGING, Signal, Snapshot

_NEGATIVE_RATING_ACTIONS = ("downgrade", "negative", "watch", "default", "withdrawn", "suspended")
_POSITIVE_RATING_ACTIONS = ("upgrade",)


class Catalyst:
    """§37. Dated things that can re-rate a stock: a board meeting for a buyback, fund raise or
    results in the next three weeks, and order wins or acquisitions announced in the last 45
    days. Several in the same window compound."""

    key = "catalyst"
    version = "2"  # v2: evidence lists the announcements counted

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        prices = snap.price_by_isin
        upcoming: dict[str, list[dict]] = {}
        for meeting in snap.meetings:
            upcoming.setdefault(meeting["isin"], []).append(meeting)
        recent: dict[str, Counter[str]] = {}
        announcements: dict[str, list[dict[str, Any]]] = {}
        for document in sorted(snap.documents, key=lambda d: d["broadcast_at"], reverse=True):
            if document["event_kind"] in ("ORDER_WIN", "ACQUISITION", "BUYBACK"):
                recent.setdefault(document["isin"], Counter())[document["event_kind"]] += 1
                announcements.setdefault(document["isin"], []).append(
                    {
                        "date": str(document["broadcast_at"].date()),
                        "kind": document["event_kind"],
                        "summary": document["summary"][:120],
                    }
                )
        for isin in set(upcoming) | set(recent):
            price = prices.get(isin)
            if price is None:
                continue
            meetings = upcoming.get(isin, [])
            kinds = recent.get(isin, Counter())
            purposes = sorted({m["purpose"] for m in meetings})
            special = [
                p
                for p in purposes
                if any(
                    w in p.lower()
                    for w in ("buy", "bonus", "split", "fund", "raising", "dividend", "preferential", "qip")
                )
            ]
            score = (
                len(special) * 0.4
                + kinds["ORDER_WIN"] * 0.2
                + kinds["ACQUISITION"] * 0.3
                + kinds["BUYBACK"] * 0.5
            )
            if score < 0.4:
                continue
            parts = []
            if special:
                parts.append("board meeting on " + ", ".join(special).lower())
            if kinds["ORDER_WIN"]:
                parts.append(f"{kinds['ORDER_WIN']} order win{'s' if kinds['ORDER_WIN'] > 1 else ''}")
            if kinds["ACQUISITION"]:
                parts.append(
                    f"{kinds['ACQUISITION']} acquisition/merger announcement{'s' if kinds['ACQUISITION'] > 1 else ''}"
                )
            if kinds["BUYBACK"]:
                parts.append("buyback announcement")
            stage = CONFIRMED if score >= 1.2 else (EMERGING if score >= 0.7 else EARLY)
            out.append(
                Signal(
                    isin,
                    price["symbol"],
                    "CATALYSTS_AHEAD",
                    BULL,
                    stage,
                    round(min(1.0, score / 1.5), 4),
                    "; ".join(parts).capitalize(),
                    {
                        "upcoming_meetings": [
                            {"date": str(m["meeting_date"]), "purpose": m["purpose"]} for m in meetings
                        ][:5],
                        "recent_announcements": dict(kinds),
                        "announcements": announcements.get(isin, [])[:6],
                        "score": round(score, 2),
                    },
                    "The dated events pass",
                    price_at=snap.close(isin),
                )
            )
        return out


class CorporateGovernance:
    """§35, the part visible in exchange filings: a cluster of governance or regulatory
    announcements (resignations, auditor changes, SEBI orders, show-cause notices) in 45 days,
    and pledge disclosures. Three or more is a signal; five or more confirmed."""

    key = "corporate_governance"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        prices = snap.price_by_isin
        counts: dict[str, Counter[str]] = {}
        samples: dict[str, list[str]] = {}
        for document in snap.documents:
            if document["event_kind"] in ("GOVERNANCE", "REGULATORY", "PLEDGE"):
                counts.setdefault(document["isin"], Counter())[document["event_kind"]] += 1
                samples.setdefault(document["isin"], []).append(
                    f"{document['category']}: {document['summary'][:120]}"
                )
        for isin, kinds in counts.items():
            price = prices.get(isin)
            total = kinds["REGULATORY"] * 2 + kinds["GOVERNANCE"] + kinds["PLEDGE"]
            if price is None or total < 3:
                continue
            stage = CONFIRMED if total >= 6 else EMERGING
            out.append(
                Signal(
                    isin,
                    price["symbol"],
                    "GOVERNANCE_FLAGS",
                    BEAR,
                    stage,
                    round(min(1.0, total / 8), 4),
                    f"{kinds['REGULATORY']} regulatory, {kinds['GOVERNANCE']} governance and {kinds['PLEDGE']} pledge filings in 45 days",
                    {"counts": dict(kinds), "examples": samples[isin][:4]},
                    "No further such filings for a quarter",
                    price_at=snap.close(isin),
                )
            )
        return out


class RatingAction:
    """§68, the rating half: an agency downgrade, negative outlook or watch in the last year is a
    risk signal; an upgrade a mild positive. One signal per company, the newest action per agency."""

    key = "credit_rating_action"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        prices = snap.price_by_isin
        by_isin: dict[str, list[dict]] = {}
        for rating in snap.ratings:
            by_isin.setdefault(rating["isin"], []).append(rating)
        for isin, actions in by_isin.items():
            price = prices.get(isin)
            if price is None:
                continue
            negative = [
                r
                for r in actions
                if any(w in f"{r['action']} {r['outlook'] or ''}".lower() for w in _NEGATIVE_RATING_ACTIONS)
            ]
            positive = [r for r in actions if any(w in r["action"].lower() for w in _POSITIVE_RATING_ACTIONS)]
            evidence = {
                "actions": [
                    {
                        "agency": r["agency"],
                        "rating": r["rating"],
                        "earlier": r["rating_earlier"],
                        "action": r["action"],
                        "outlook": r["outlook"],
                        "on": str(r["broadcast_at"].date()),
                    }
                    for r in actions
                ][:5]
            }
            if negative:
                newest = max(negative, key=lambda r: r["broadcast_at"])
                stage = CONFIRMED if len(negative) >= 2 or "default" in newest["action"].lower() else EMERGING
                out.append(
                    Signal(
                        isin,
                        price["symbol"],
                        "RATING_DOWNGRADE",
                        BEAR,
                        stage,
                        round(min(1.0, 0.5 + 0.25 * len(negative)), 4),
                        f"{newest['agency']}: {newest['action']} to {newest['rating']}"
                        + (f" ({newest['outlook']})" if newest["outlook"] else ""),
                        evidence,
                        "The agency reaffirms or upgrades",
                        price_at=snap.close(isin),
                    )
                )
            elif positive:
                newest = max(positive, key=lambda r: r["broadcast_at"])
                out.append(
                    Signal(
                        isin,
                        price["symbol"],
                        "RATING_UPGRADE",
                        BULL,
                        EARLY,
                        0.4,
                        f"{newest['agency']}: upgrade to {newest['rating']} from {newest['rating_earlier'] or '?'}",
                        evidence,
                        "A later downgrade",
                        price_at=snap.close(isin),
                    )
                )
        return out


class DerivativesSignal:
    """§70. Futures open interest and price together over about a week: long build-up (OI and
    price up) and short covering (OI down, price up) are bullish; short build-up (OI up, price
    down) and long unwinding bearish. Basis and put-call ratio ride along as evidence."""

    key = "derivatives_signal"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        for item in snap.derivatives:
            prior_oi, now_oi = item["futures_oi_prior"], item["futures_oi"]
            if (
                not prior_oi
                or not item["underlying_close_prior"]
                or not item["underlying_close"]
                or item["isin"] not in snap.price_by_isin
            ):
                continue
            oi_change = (now_oi / prior_oi - 1) * 100
            price_change = (item["underlying_close"] / item["underlying_close_prior"] - 1) * 100
            if abs(oi_change) < 5 or abs(price_change) < 2:
                continue
            evidence = {
                "futures_oi": now_oi,
                "oi_change_pct_5d": round(oi_change, 1),
                "price_change_pct_5d": round(price_change, 1),
                "basis_pct": item["basis_pct"],
                "pcr_oi": item["pcr_oi"],
                "as_of_fo_date": str(item["trade_date"]),
            }
            strength = round(min(1.0, (abs(oi_change) / 30 + abs(price_change) / 10) / 2), 4)
            stage = EMERGING if abs(oi_change) >= 15 else EARLY
            if oi_change > 0 and price_change > 0:
                out.append(
                    Signal(
                        item["isin"],
                        item["symbol"],
                        "LONG_BUILDUP",
                        BULL,
                        stage,
                        strength,
                        f"Futures OI +{oi_change:.0f}% with price +{price_change:.1f}% over 5 sessions",
                        evidence,
                        "OI falls while price stalls",
                        price_at=snap.close(item["isin"]),
                    )
                )
            elif oi_change < 0 and price_change > 0:
                out.append(
                    Signal(
                        item["isin"],
                        item["symbol"],
                        "SHORT_COVERING",
                        BULL,
                        EARLY,
                        strength,
                        f"Futures OI {oi_change:.0f}% with price +{price_change:.1f}% over 5 sessions",
                        evidence,
                        "Price gives back the move",
                        price_at=snap.close(item["isin"]),
                    )
                )
            elif oi_change > 0 and price_change < 0:
                out.append(
                    Signal(
                        item["isin"],
                        item["symbol"],
                        "SHORT_BUILDUP",
                        BEAR,
                        stage,
                        strength,
                        f"Futures OI +{oi_change:.0f}% with price {price_change:.1f}% over 5 sessions",
                        evidence,
                        "OI unwinds with price recovering",
                        price_at=snap.close(item["isin"]),
                    )
                )
            else:
                out.append(
                    Signal(
                        item["isin"],
                        item["symbol"],
                        "LONG_UNWINDING",
                        BEAR,
                        EARLY,
                        strength,
                        f"Futures OI {oi_change:.0f}% with price {price_change:.1f}% over 5 sessions",
                        evidence,
                        "Fresh long build-up",
                        price_at=snap.close(item["isin"]),
                    )
                )
        return out
