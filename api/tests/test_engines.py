"""Engines, the stance function and the signal pages (spec §85, §118). The stance tests are pure;
the rest drive the running app and expect at least one engine run (python ingest.py signals)."""

import csv
from pathlib import Path

import httpx
import pytest

from equity_engine.engines import IMPLEMENTED
from equity_engine.engines.base import BEAR, BULL, CONFIRMED, EARLY, EMERGING, GATE
from equity_engine.service import stance

HTML = {"Accept": "text/html"}
SEED = Path(__file__).resolve().parents[2] / "resources" / "seed" / "engine.csv"


def _signal(direction: str, stage: str, strength: float = 1.0, engine: str = "x", kind: str = "T") -> dict:
    return {
        "direction": direction,
        "stage": stage,
        "strength": strength,
        "engine_key": engine,
        "signal_type": kind,
        "headline": f"{engine} {kind}",
    }


# ------------------------------------------------------------------ stance: pure


def test_stance_no_signals_is_neutral_with_no_conviction():
    result = stance.compute([])
    assert (result.stance, result.conviction) == ("NEUTRAL", "NONE")
    assert result.bull_score == result.bear_score == 0


def test_stance_gate_wins_and_names_the_reason():
    result = stance.compute(
        [
            _signal(BULL, CONFIRMED),
            _signal(BULL, CONFIRMED),
            _signal(GATE, CONFIRMED, engine="investability", kind="ILLIQUID"),
        ]
    )
    assert result.stance == "AVOID" and result.conviction == "NONE"
    assert result.gate == "investability ILLIQUID" and result.inputs["gate_engine"] == "investability"
    assert result.bull_count == 2  # the tally is still reported, greyed out on the page


def test_stance_one_confirmed_signal_is_lean_long_medium_at_most():
    result = stance.compute([_signal(BULL, CONFIRMED)])
    assert (result.stance, result.conviction) == ("LEAN_LONG", "MEDIUM")


def test_stance_three_confirmed_unopposed_is_long_high():
    result = stance.compute([_signal(BULL, CONFIRMED, engine=e) for e in "abc"])
    assert (result.stance, result.conviction) == ("LONG", "HIGH")


def test_stance_confirmed_contradiction_caps_conviction():
    result = stance.compute(
        [_signal(BULL, CONFIRMED, engine=e) for e in "abc"] + [_signal(BEAR, CONFIRMED, 0.4, engine="d")]
    )
    assert result.stance == "LONG" and result.conviction == "MEDIUM"


def test_stance_is_symmetric_for_short():
    result = stance.compute([_signal(BEAR, CONFIRMED, engine=e) for e in "abc"])
    assert (result.stance, result.conviction) == ("SHORT", "HIGH")


def test_stance_early_signals_only_hint():
    result = stance.compute([_signal(BULL, EARLY), _signal(BULL, EARLY, engine="b")])
    assert result.stance == "LEAN_LONG" and result.conviction == "LOW"
    assert stance.compute([_signal(BULL, EARLY)]).stance == "NEUTRAL"


def test_stance_weights_are_recorded_for_the_ledger():
    result = stance.compute([_signal(BULL, EMERGING, 0.5, engine="rs", kind="RS_LEADER")])
    assert result.inputs["weights"] == {"rs:RS_LEADER": 0.3}
    assert result.version == stance.VERSION


# ------------------------------------------------------------------ registry


def test_every_implemented_engine_is_in_the_seed_csv_with_matching_keys():
    with open(SEED, encoding="utf-8", newline="") as handle:
        seeded = {line["engine_key"]: line for line in csv.DictReader(handle)}
    assert set(IMPLEMENTED) <= set(seeded)
    for key, engine in IMPLEMENTED.items():
        assert engine.key == key and engine.version
    assert len(seeded) >= 50 and len({line["spec_section"] for line in seeded.values()}) == len(seeded)


# ------------------------------------------------------------------ live: ledger + pages


@pytest.fixture(scope="module")
def run(client: httpx.Client) -> dict:
    body = client.get("/api/radar").json()
    if not body.get("success"):
        pytest.fail("No engine run in the ledger. Run: python ingest.py signals")
    return body


def test_catalogue_derives_status_from_data(client: httpx.Client, run: dict):
    body = client.get("/api/engine").json()
    by_key = {e["engine_key"]: e for e in body["engines"]}
    assert len(by_key) >= 50
    assert by_key["relative_strength"]["status"] == "LIVE" and by_key["relative_strength"]["signals"] > 0
    assert by_key["alternative_data"]["status"] == "BLOCKED" and by_key["alternative_data"]["missing"] == ["alt_data"]
    assert by_key["profitability_inflection"]["implemented"]
    assert by_key["stance"]["status"] == "FRAMEWORK"
    assert client.get("/api/engine/nope").status_code == 404


def test_radar_has_regime_and_tiles_for_both_directions(run: dict):
    assert 400 < run["regime"]["universe"] <= 520 and 0 <= run["regime"]["above_200dma_pct"] <= 100
    directions = {t["direction"] for t in run["tiles"]}
    assert {"BULL", "BEAR", "GATE"} <= directions
    for tile in run["tiles"]:
        assert tile["total"] == sum(tile["by_stage"].values()) > 0


def test_signal_feed_filters(client: httpx.Client, run: dict):
    body = client.get(
        "/api/signal", params={"engine": "relative_strength", "stage": "CONFIRMED", "limit": 20}
    ).json()
    assert body["success"] and body["signals"]
    for s in body["signals"]:
        assert s["engine_key"] == "relative_strength" and s["stage"] == "CONFIRMED"
        assert s["evidence"]["percentile_6m"] >= 80 or s["evidence"]["percentile_6m"] <= 20
        assert s["invalidation"] and s["headline"] and s["price_at"] is not None
    assert client.get("/signal", params={"stage": "BOGUS"}, headers=HTML).status_code == 422


def test_gated_security_is_avoid_with_the_gate_named(client: httpx.Client, run: dict):
    gate = client.get("/api/signal", params={"direction": "GATE", "limit": 1}).json()["signals"][0]
    body = client.get(f"/api/stance/{gate['symbol']}").json()
    assert body["stance"]["stance"] == "AVOID" and body["stance"]["gate"]
    assert any(s["direction"] == "GATE" for s in body["signals"])
    page = client.get(f"/security/{gate['symbol']}", headers=HTML)
    assert page.status_code == 200 and 'id="stance-gate"' in page.text and "Avoid" in page.text


def test_stance_page_shows_every_engine_with_a_reason(client: httpx.Client, run: dict):
    page = client.get("/security/RELIANCE", headers=HTML)
    assert page.status_code == 200
    assert 'id="stance-panel"' in page.text and 'id="engine-grid"' in page.text
    assert "no data: " in page.text  # unbuilt engines are listed with what they wait for
    body = client.get("/api/stance/RELIANCE").json()
    assert body["stance"]["version"] == stance.VERSION
    assert body["stance"]["stance"] in ("LONG", "LEAN_LONG", "NEUTRAL", "LEAN_SHORT", "SHORT", "AVOID")
    # the stance is a deterministic function of the signals shown beside it
    recomputed = stance.compute(body["signals"])
    assert (
        recomputed.stance == body["stance"]["stance"]
        and recomputed.conviction == body["stance"]["conviction"]
    )


def test_screener_chips(client: httpx.Client, run: dict):
    body = client.get(
        "/api/screen",
        params={
            "stance": ["LONG", "LEAN_LONG"],
            "has": "technical_price",
            "confirmed_only": "true",
            "limit": 50,
        },
    ).json()
    assert body["success"]
    for r in body["rows"]:
        assert r["stance"] in ("LONG", "LEAN_LONG") and "technical_price" in r["engines"]
    excluded = client.get("/api/screen", params={"has_not": "technical_price", "limit": 50}).json()
    assert all("technical_price" not in r["engines"] for r in excluded["rows"])
    assert client.get("/screen", params={"stance": "SIDEWAYS"}, headers=HTML).status_code == 422


def test_pages_render(client: httpx.Client, run: dict):
    for path in (
        "/",
        "/signal",
        "/engine",
        "/engine/relative_strength",
        "/engine/valuation",
        "/screen",
        "/health",
    ):
        page = client.get(path, headers=HTML)
        assert page.status_code == 200, path
    assert "Opportunity radar" in client.get("/", headers=HTML).text
    listing = client.get("/security", params={"q": "RELI"}, headers={**HTML, "HX-Request": "true"}).text
    assert "badge" in listing  # the stance column
