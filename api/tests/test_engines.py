"""Engines, the stance function and the signal pages (spec §85, §118). The stance tests are pure;
the rest drive the running app and expect at least one engine run (python ingest.py signals)."""

import csv
from pathlib import Path

import httpx
import pytest

from equity_engine.db import rows, transaction
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
    assert by_key["alternative_data"]["status"] == "BLOCKED" and by_key["alternative_data"]["missing"] == [
        "alt_data"
    ]
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
    page = client.get(f"/equities/{gate['symbol']}", headers=HTML)
    assert page.status_code == 200 and 'id="stance-gate"' in page.text and "Avoid" in page.text


def test_stance_page_shows_every_engine_with_a_reason(client: httpx.Client, run: dict):
    page = client.get("/equities/RELIANCE", headers=HTML)
    assert page.status_code == 200
    assert 'id="stance-panel"' in page.text and 'id="engine-grid"' in page.text
    assert "no data: " in page.text  # unbuilt engines are listed with what they wait for
    assert (
        'id="toggle-silent-engines"' in page.text and "without a signal" in page.text
    )  # hidden by default, one click to show
    assert 'id="header-price"' in page.text and 'id="header-pe"' in page.text
    from equity_engine.service import fundamentals as fundamentals_service

    with transaction() as connection:
        sector = fundamentals_service.industry_pe(connection, "INE002A01018")  # Reliance's industry
    if sector:
        assert sector["members"] >= 5 and sector["median_pe"] > 0
        assert 'id="header-sector-pe"' in page.text and f"at sector P/E {sector['median_pe']}" in page.text
    assert "bg-success/15" in page.text or "bg-error/15" in page.text  # fired engines are tinted by direction
    body = client.get("/api/stance/RELIANCE").json()
    assert body["stance"]["version"] == stance.VERSION
    assert body["stance"]["stance"] in ("LONG", "LEAN_LONG", "NEUTRAL", "LEAN_SHORT", "SHORT", "AVOID")
    # the stance is a deterministic function of the signals shown beside it
    recomputed = stance.compute(body["signals"])
    assert (
        recomputed.stance == body["stance"]["stance"]
        and recomputed.conviction == body["stance"]["conviction"]
    )


def test_screener_rows_are_sortable(client: httpx.Client, run: dict):
    page = client.get("/screen", headers=HTML).text
    assert (
        "@click=\"sort('net', true, true)\"" in page
        and 'data-row data-symbol="' in page
        and 'data-stance="' in page
    )
    rows_ = client.get(
        "/screen", params={"stance": "LONG", "min_mcap": ""}, headers={"HX-Request": "true"}
    ).text
    assert rows_.count("<tr data-row") > 0 and rows_.count('data-stance="0"') == rows_.count("<tr data-row")


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
    listing = client.get("/equities", params={"q": "RELI"}, headers={**HTML, "HX-Request": "true"}).text
    assert "badge" in listing  # the stance column


def test_glossary_explains_every_term_with_an_example_and_valid_engine_links(client: httpx.Client):
    from equity_engine.pages.glossary import GROUPS, TERMS

    assert len(TERMS) >= 60 and len({t.term for t in TERMS}) == len(TERMS)
    for t in TERMS:
        assert t.group in GROUPS and len(t.meaning) > 60 and len(t.example) > 20, t.term
        for key in t.engines:
            assert key in IMPLEMENTED, (t.term, key)
    page = client.get("/glossary", headers=HTML)
    assert page.status_code == 200
    assert "Interest cover" in page.text and 'href="/engine/credit_distress"' in page.text
    assert page.text.count("data-term=") == len(TERMS)
    # the filter script hooks the header's search box by id and hides non-matching cards
    assert (
        'id="glossary-search"' in page.text
        and "getElementById('glossary-search')" in page.text
        and 'id="glossary-count"' in page.text
    )


def test_every_catalogue_engine_has_an_example_shown_on_its_page(client: httpx.Client, run: dict):
    from equity_engine.pages.engine_examples import EXAMPLES

    keys = {e["engine_key"] for e in client.get("/api/engine").json()["engines"]}
    assert keys <= set(EXAMPLES), f"engines without an example: {sorted(keys - set(EXAMPLES))}"
    assert set(EXAMPLES) <= keys, f"examples for unknown engines: {sorted(set(EXAMPLES) - keys)}"
    page = client.get("/engine/turnaround", headers=HTML)
    assert 'id="engine-example"' in page.text and "two profitable quarters" in page.text
    assert "What it detects" in client.get("/engine", headers=HTML).text


def test_screener_accepts_the_form_as_the_browser_sends_it(client: httpx.Client, run: dict):
    """Every chip click submits the empty market-cap box too; that must filter, not 422."""
    browser = {"HX-Request": "true"}
    full = client.get("/screen", params={"min_mcap": "", "index": ""}, headers=browser)
    assert full.status_code == 200
    longs = client.get("/screen", params={"stance": "LONG", "min_mcap": "", "index": ""}, headers=browser)
    assert longs.status_code == 200 and 0 < longs.text.count("<tr") < full.text.count("<tr")
    floored = client.get(
        "/screen", params={"stance": "LONG", "min_mcap": "1,00,000", "index": ""}, headers=browser
    )
    assert floored.status_code == 200 and floored.text.count("<tr") <= longs.text.count("<tr")
    assert client.get("/screen", params={"min_mcap": "abc"}, headers=browser).status_code == 422
    api = client.get("/api/screen", params={"stance": "LONG", "min_mcap": ""}).json()
    assert api["success"] and all(r["stance"] == "LONG" for r in api["rows"])
    page = client.get("/screen", params={"stance": "LONG"}, headers=HTML).text
    assert 'x-data="{ on: true }"' in page  # the chosen chip renders lit


def test_radar_breadth_states_both_halves_of_the_same_denominator(
    client: httpx.Client, run: dict, connection
):
    regime = rows(
        connection,
        "SELECT m.* FROM market_regime m JOIN engine_run r USING (run_id) WHERE r.kind = 'LIVE' ORDER BY r.started_at DESC LIMIT 1",
    )[0]
    assert regime["with_200dma"] is not None and regime["with_200dma"] <= regime["universe"]
    assert float(regime["above_200dma_pct"]) == round(100 * regime["above_200dma"] / regime["with_200dma"], 1)
    page = client.get("/", headers=HTML).text
    assert 'id="breadth-200dma"' in page
    assert f"<strong>{regime['above_200dma']}</strong> above" in page
    assert f"<strong>{regime['with_200dma'] - regime['above_200dma']}</strong> below" in page
    assert f"of {regime['with_200dma']} with a 200-day history" in page


def test_line_chart_scales_series_and_marks_zero():
    from datetime import date

    from equity_engine.pages.charts import donut_dasharray, line_chart

    chart = line_chart(
        {
            "a": [(date(2025, 1, 1), -5.0), (date(2025, 7, 1), 5.0)],
            "b": [(date(2025, 1, 1), 2.0), (date(2025, 12, 31), 8.0)],
        },
        unit=" pts",
    )
    assert [s.name for s in chart.series] == ["a", "b"] and chart.series[0].color != chart.series[1].color
    assert chart.series[0].path.startswith("M") and chart.series[0].path.count("L") == 1
    assert chart.zero_y is not None and chart.plot["y0"] < chart.zero_y < chart.plot["y1"]
    assert chart.series[1].end_x == chart.plot["x1"]  # the latest date sits at the right edge
    assert chart.y_ticks[0][1].endswith(" pts") and abs(chart.series[1].end_y - chart.series[0].end_y) >= 12
    assert line_chart({}).series == []
    curved = line_chart(
        {"a": [(date(2025, m, 1), float(v)) for m, v in ((1, 1), (2, 4), (3, 2), (4, 5))]}, smooth=True
    )
    straight = line_chart({"a": curved.series[0].points})
    assert curved.series[0].path.count("C") == 3 and curved.series[0].path.startswith("M")
    assert (
        curved.series[0].path.split()[-1] == straight.series[0].path.split()[-1][1:]
    )  # the curve ends on the last point
    dash = donut_dasharray([0.5, 0.5])
    assert len(dash) == 2 and dash[0][0].startswith("48.50") and dash[1][1] == -25.75


def test_market_history_page_and_radar_charts(client: httpx.Client, run: dict):
    page = client.get("/market", headers=HTML)
    assert page.status_code == 200
    for chart_id in ("rotation-chart", "breadth-chart", "median-chart"):
        assert f'id="{chart_id}"' in page.text, chart_id
    assert (
        page.text.count('name="industry"') >= 10
        and 'name="range" value="1y" class="hidden" checked' in page.text
    )
    # the range control is inside the swapped partial, so changing an industry keeps the range
    swapped = client.get(
        "/market", params={"range": "all", "industry": "Healthcare"}, headers={"HX-Request": "true"}
    ).text
    assert 'name="range" value="all" class="hidden" checked' in swapped and 'id="range-toggle"' in swapped
    smooth = client.get(
        "/market", params={"range": "1y", "smooth": "true"}, headers={"HX-Request": "true"}
    ).text
    rotation = smooth.split('id="rotation-chart"')[1].split("</svg>")[0]
    assert 'name="smooth" value="true" class="hidden" checked' in smooth and " C" in rotation
    assert (
        rotation.count('<g class="series"') == rotation.count('class="line"') >= 2
    )  # hover groups wrap every line
    partial = client.get(
        "/market",
        params={"range": "3y", "industry": ["Healthcare", "Construction"]},
        headers={"HX-Request": "true"},
    )
    assert partial.status_code == 200 and "<html" not in partial.text and "Healthcare" in partial.text
    assert client.get("/market", params={"range": "10y"}, headers=HTML).status_code == 422
    radar = client.get("/", headers=HTML).text
    for element in (
        "breadth-200dma",
        "breadth-advancing",
        "median-bar",
        "stance-donut",
        "sector-chart",
        "sector-history-link",
        "regime-meaning",
    ):
        assert f'id="{element}"' in radar, element


def test_pct_filter_keeps_a_decimal_only_under_one_percent():
    from equity_engine.pages.templating import pct

    assert pct(37.7) == "38" and pct(0.14, sign=True) == "+0.1" and pct(-0.5) == "-0.5"
    assert pct(0) == "0" and pct(None) == "—" and pct(-7.9, sign=True) == "-8" and pct(99.96) == "100"


def test_old_security_urls_redirect_to_equities_and_the_page_has_tabs(client: httpx.Client, run: dict):
    moved = client.get("/security/RELIANCE", headers=HTML)
    assert moved.status_code == 301 and moved.headers["location"] == "/equities/RELIANCE"
    assert client.get("/security", params={"q": "rel"}, headers=HTML).headers["location"] == "/equities?q=rel"
    page = client.get("/equities/RELIANCE", headers=HTML).text
    for tab in ("overview", "ownership", "financials", "deals", "prices"):
        assert f'id="tab-{tab}"' in page, tab
    assert 'id="equity-tabs"' in page and "/equities/RELIANCE/timeline" in page


def test_price_sparkline_spans_the_series_and_shows_on_the_equity_page(client: httpx.Client, run: dict):
    from datetime import date

    from equity_engine.pages.charts import sparkline

    pts = [
        (date(2026, 1, 1), 100.0),
        (date(2026, 2, 1), 80.0),
        (date(2026, 3, 1), 130.0),
        (date(2026, 4, 1), 120.0),
    ]
    spark = sparkline(pts)
    assert (
        spark is not None
        and spark.first == 100.0
        and spark.last == 120.0
        and spark.low == 80.0
        and spark.high == 130.0
    )
    assert spark.change_pct == 20.0 and spark.up and spark.path.count("L") == 3 and spark.area.endswith("Z")
    assert spark.high_y < spark.low_y  # the high sits above the low on the canvas
    assert (
        len(spark.points) == 4 and spark.points[1][2] == "2026-02-01" and spark.points[1][3] == 80.0
    )  # hover data
    assert sparkline(pts[:1]) is None
    page = client.get("/equities/RELIANCE", headers=HTML).text
    assert (
        'id="price-chart"' in page
        and 'id="chart-range"' in page
        and "/equities/RELIANCE/chart?range=5y" in page
    )
    for key, floor in (("ytd", 100), ("3y", 700), ("all", 1500)):
        fragment = client.get(
            "/equities/RELIANCE/chart", params={"range": key}, headers={"HX-Request": "true"}
        )
        assert (
            fragment.status_code == 200 and "<html" not in fragment.text and f"range={key}" in fragment.text
        )
        sessions = int(fragment.text.split(" sessions")[0].split()[-1].replace(",", ""))
        assert sessions >= floor, (key, sessions)
    assert client.get("/equities/RELIANCE/chart", params={"range": "9y"}).status_code == 422


def test_equities_list_shows_pe_against_the_sector_median(client: httpx.Client, run: dict):
    from equity_engine.service import fundamentals as fundamentals_service

    with transaction() as connection:
        table = fundamentals_service.pe_table(connection)
    assert len(table) > 400 and sum(1 for v in table.values() if v["sector_pe"]) > 300
    reliance = table["RELIANCE"]
    assert (
        reliance["pe"]
        and reliance["sector_pe"]
        and reliance["gap_pct"] == round((reliance["sector_pe"] / reliance["pe"] - 1) * 100, 1)
    )
    page = client.get("/equities", params={"q": "reliance"}, headers=HTML).text
    assert (
        "Sector P/E" in page
        and "At sector P/E" in page
        and f">{reliance['sector_pe']:.1f}<" in page.replace(",", "")
    )


def test_radar_sums_who_owns_the_market(client: httpx.Client, run: dict, connection):
    from equity_engine.service import company

    ov = company.ownership_value(connection)
    assert ov["companies"] > 400 and ov["total"] > 1e14  # over ₹100 lakh crore
    shares = {g["key"]: g["share_pct"] for g in ov["groups"]}
    assert abs(sum(shares.values()) - 100) < 0.01 and shares["promoter"] > 40 and shares["fii"] > 10
    page = client.get("/", headers=HTML).text
    assert 'id="ownership-value"' in page and "Who owns the market" in page and "Mutual funds" in page
    donut = page.split('id="ownership-donut"')[1].split("</svg>")[0]
    assert donut.count("<circle") == sum(1 for g in ov["groups"] if g["share_pct"] > 0) >= 7
    assert (
        'id="ownership-legend"' in page
        and page.split('id="ownership-legend"')[1].split("</div>")[0].count("rounded-sm") >= 7
    )


def test_government_ownership_tags_are_seeded_and_shown(client: httpx.Client, run: dict, connection):
    from equity_engine.service import company

    tags = company.psu_tags(connection)
    assert (
        tags["MRPL"]["owner"] == "central"
        and tags["MRPL"]["parent"] == "ONGC"
        and tags["ONGC"]["category"] == "Maharatna"
    )
    assert tags["PETRONET"]["owner"] == "psu-promoted" and tags["GMDCLTD"]["owner"] == "state"
    known = {r["nse_symbol"] for r in rows(connection, "SELECT nse_symbol FROM security")}
    unknown = sorted(set(tags) - known)
    assert unknown == [], f"psu.csv symbols not in the security master: {unknown}"
    page = client.get("/equities/MRPL", headers=HTML).text
    assert "Govt · Miniratna I" in page and "held through ONGC" in page
    listing = client.get("/equities", params={"q": "ONGC"}, headers={"HX-Request": "true"}).text
    assert "Govt · Maharatna" in listing
    govt_only = client.get("/equities", params={"govt": "true"}, headers={"HX-Request": "true"}).text
    shown = govt_only.count("<tr data-row")
    assert 0 < shown <= sum(1 for v in tags.values() if v["owner"] in ("central", "state"))
    assert govt_only.count("mdi-bank-outline") == shown and "PSU-promoted" not in govt_only
    assert 'name="govt"' in client.get("/equities", headers=HTML).text


def test_equities_list_is_sortable(client: httpx.Client, run: dict):
    page = client.get("/equities", headers=HTML).text
    assert "@click=\"sort('mcap', true, true)\"" in page and "@click=\"sort('gap', true, true)\"" in page
    rows_ = client.get("/equities", params={"q": "bank"}, headers={"HX-Request": "true"}).text
    assert rows_.count("<tr data-row") > 0 and rows_.count('data-sector-pe="') == rows_.count("<tr data-row")
