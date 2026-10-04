"""Engines on document text and its structured reading (spec §32, §33, §56, §71). They fire only
for companies whose documents have been fetched and, for the first three, read by the LLM."""

from difflib import SequenceMatcher
from typing import Any

from equity_engine.engines.base import BEAR, BULL, CONFIRMED, EARLY, EMERGING, Signal, Snapshot

_SNIPPET = 40_000


def _ttm_growth(history: list[dict[str, Any]]) -> float | None:
    if len(history) < 8 or any(q.get("q_pat") is None for q in history[:8]):
        return None
    now = sum(float(q["q_pat"]) for q in history[:4])
    then = sum(float(q["q_pat"]) for q in history[4:8])
    return round((now / then - 1) * 100, 1) if then > 0 else None


class ManagementCommentary:
    """§32. Tone and guidance from the newest investor presentation or press release read by the
    LLM: positive tone with raised guidance is bullish, negative tone or withdrawn guidance bearish."""

    key = "management_commentary"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        for isin, readings in snap.extractions.items():
            newest = readings[0]
            if isin not in snap.price_by_isin:
                continue
            up = sum(1 for g in newest["guidance"] if g.get("direction") == "UP")
            down = sum(1 for g in newest["guidance"] if g.get("direction") in ("DOWN", "WITHDRAWN"))
            evidence = {
                "document": newest["document_id"],
                "tone": newest["tone"],
                "guidance_up": up,
                "guidance_down": down,
                "summary": newest["summary"],
                "filed": str(newest["broadcast_at"].date()),
            }
            symbol = snap.price_by_isin[isin]["symbol"]
            if newest["tone"] == "POSITIVE" and up > down:
                out.append(
                    Signal(
                        isin,
                        symbol,
                        "GUIDANCE_RAISED",
                        BULL,
                        EMERGING if up >= 2 else EARLY,
                        min(1.0, 0.4 + 0.2 * up),
                        f"Positive tone with {up} guidance item{'s' if up != 1 else ''} raised",
                        evidence,
                        "The next presentation cuts guidance",
                        price_at=snap.close(isin),
                    )
                )
            elif newest["tone"] == "NEGATIVE" or down > up:
                out.append(
                    Signal(
                        isin,
                        symbol,
                        "GUIDANCE_CUT",
                        BEAR,
                        EMERGING if down >= 2 else EARLY,
                        min(1.0, 0.4 + 0.2 * down),
                        f"{newest['tone'].title()} tone with {down} guidance item{'s' if down != 1 else ''} cut or withdrawn",
                        evidence,
                        "Guidance is restored",
                        price_at=snap.close(isin),
                    )
                )
        return out


class NarrativeVsNumbers:
    """§33. Management says one thing, the filings show another: positive tone and raised guidance
    while TTM profit fell, or a negative read while profit grew strongly (the rarer, bullish case)."""

    key = "narrative_vs_numbers"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        for isin, readings in snap.extractions.items():
            history = snap.fundamentals.get(isin)
            if not history or isin not in snap.price_by_isin:
                continue
            growth = _ttm_growth(history)
            if growth is None:
                continue
            newest = readings[0]
            symbol = snap.price_by_isin[isin]["symbol"]
            evidence = {
                "document": newest["document_id"],
                "tone": newest["tone"],
                "ttm_pat_growth_pct": growth,
                "summary": newest["summary"],
            }
            if newest["tone"] == "POSITIVE" and growth <= -15:
                out.append(
                    Signal(
                        isin,
                        symbol,
                        "NARRATIVE_AHEAD_OF_NUMBERS",
                        BEAR,
                        EMERGING,
                        min(1.0, -growth / 50),
                        f"Positive management tone while TTM PAT is {growth:+.0f}%",
                        evidence,
                        "Profit growth turns positive",
                        price_at=snap.close(isin),
                    )
                )
            elif newest["tone"] == "NEGATIVE" and growth >= 25:
                out.append(
                    Signal(
                        isin,
                        symbol,
                        "NUMBERS_AHEAD_OF_NARRATIVE",
                        BULL,
                        EARLY,
                        min(1.0, growth / 100),
                        f"Cautious management tone while TTM PAT is {growth:+.0f}%",
                        evidence,
                        "Profit growth slows below 10%",
                        price_at=snap.close(isin),
                    )
                )
        return out


class OperatingKpi:
    """§56. Operating KPIs the LLM read from presentations, compared with the same KPI in the
    company's previous reading: a named metric improving or deteriorating by at least 10%."""

    key = "operating_kpi"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        for isin, readings in snap.extractions.items():
            if len(readings) < 2 or isin not in snap.price_by_isin:
                continue
            newest, previous = readings[0], readings[1]
            older = {
                k["name"].strip().lower(): k
                for k in previous["kpis"]
                if isinstance(k.get("value"), (int, float))
            }
            improving: list[dict[str, Any]] = []
            worsening: list[dict[str, Any]] = []
            for kpi in newest["kpis"]:
                match = older.get(str(kpi.get("name", "")).strip().lower())
                if not match or not isinstance(kpi.get("value"), (int, float)) or not match["value"]:
                    continue
                change = (kpi["value"] / match["value"] - 1) * 100
                if abs(change) < 10:
                    continue
                (improving if change > 0 else worsening).append(
                    {
                        "kpi": kpi["name"],
                        "now": kpi["value"],
                        "before": match["value"],
                        "change_pct": round(change, 1),
                    }
                )
            symbol = snap.price_by_isin[isin]["symbol"]
            if improving and len(improving) > len(worsening):
                out.append(
                    Signal(
                        isin,
                        symbol,
                        "KPIS_IMPROVING",
                        BULL,
                        EMERGING if len(improving) >= 3 else EARLY,
                        min(1.0, 0.3 + 0.2 * len(improving)),
                        f"{len(improving)} operating KPIs up ≥10% vs the previous disclosure: "
                        + ", ".join(i["kpi"] for i in improving[:3]),
                        {"improving": improving[:8], "worsening": worsening[:8]},
                        "The next disclosure reverses them",
                        price_at=snap.close(isin),
                    )
                )
            elif worsening and len(worsening) > len(improving):
                out.append(
                    Signal(
                        isin,
                        symbol,
                        "KPIS_DETERIORATING",
                        BEAR,
                        EMERGING if len(worsening) >= 3 else EARLY,
                        min(1.0, 0.3 + 0.2 * len(worsening)),
                        f"{len(worsening)} operating KPIs down ≥10%: "
                        + ", ".join(w["kpi"] for w in worsening[:3]),
                        {"improving": improving[:8], "worsening": worsening[:8]},
                        "The next disclosure reverses them",
                        price_at=snap.close(isin),
                    )
                )
        return out


class DocumentDiff:
    """§71. How much the language of a company's newest long document changed against the
    previous one of the same kind, measured on the text itself (no LLM). A large change in a
    document that is usually boilerplate (annual report, results note) is worth a look; the
    LLM's risk list, when present, says what changed."""

    key = "document_diff"
    version = "1"

    def evaluate(self, snap: Snapshot) -> list[Signal]:
        out: list[Signal] = []
        for isin, texts in snap.document_texts.items():
            if len(texts) < 2 or isin not in snap.price_by_isin:
                continue
            newest, previous = texts[0], texts[1]
            ratio = SequenceMatcher(
                None, previous["text"][:_SNIPPET], newest["text"][:_SNIPPET], autojunk=True
            ).quick_ratio()
            changed = round((1 - ratio) * 100, 1)
            if changed < 35:
                continue
            new_risks = [
                r
                for r in (snap.extraction_for(newest["document_id"]) or {}).get("risks", [])
                if r.get("new_or_changed")
            ]
            symbol = snap.price_by_isin[isin]["symbol"]
            out.append(
                Signal(
                    isin,
                    symbol,
                    "LANGUAGE_CHANGED",
                    BEAR if new_risks else EARLY and BULL,
                    CONFIRMED if changed >= 60 else EMERGING,
                    min(1.0, changed / 100),
                    f"{changed:.0f}% of the text changed against the previous {newest['event_kind'].lower().replace('_', ' ')}"
                    + (f"; {len(new_risks)} new or worsening risks named" if new_risks else ""),
                    {
                        "document": newest["document_id"],
                        "previous": previous["document_id"],
                        "changed_pct": changed,
                        "new_risks": [r.get("risk") for r in new_risks][:5],
                    },
                    "The next document returns to its usual language",
                    price_at=snap.close(isin),
                )
            )
        return out
