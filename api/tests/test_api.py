"""The pages and JSON endpoints, over HTTP against the running app."""

import httpx
import pytest

HTML = {"Accept": "text/html"}


@pytest.fixture(scope="module")
def latest(client: httpx.Client) -> dict:
    summary = client.get("/api/health").json()["summary"]
    if not summary["counts"]["price_daily"]:
        pytest.fail("No prices ingested. Run: python ingest.py rebuild (or: python ingest.py daily)")
    return summary


def test_health(latest: dict):
    assert 450 <= latest["counts"]["security"] <= 520  # the universe is the Nifty 500
    assert latest["latest"]["priced"] > 400
    assert latest["prices"]["first_trade_date"] <= latest["prices"]["last_trade_date"]


def test_sources_are_all_registered_and_none_empty(client: httpx.Client):
    body = client.get("/api/source").json()
    assert body["success"] is True
    by_id = {source["source_id"]: source for source in body["sources"]}
    assert len(by_id) >= 35
    assert {
        "nse_bhav_udiff",
        "nse_delivery_mto",
        "nse_daily_reports",
        "nse_surveillance_esm",
        "nse_results_xbrl",
    } <= set(by_id)
    assert not [name for name in by_id if not name.startswith("nse_")]  # NSE is the only exchange source
    # Sources added later may not have been fetched yet; the Phase 0 ones must have files.
    empty = {name for name, source in by_id.items() if source["state"] == "EMPTY"}
    core = {
        "nse_bhav_udiff",
        "nse_delivery_mto",
        "nse_daily_reports",
        "nse_equity_master",
        "nse_surveillance_esm",
        "nse_bulk_deal_history",
        "nse_shareholding_filings",
        "nse_results_filings",
    }
    assert not (core & empty), core & empty


def test_price_history_is_newest_first_with_delivery(client: httpx.Client):
    body = client.get("/api/price/reliance", params={"limit": 5}).json()  # symbol is case-insensitive
    assert body["success"] is True and body["isin"] == "INE002A01018" and body["symbol"] == "RELIANCE"
    dates = [price["trade_date"] for price in body["prices"]]
    assert dates == sorted(dates, reverse=True) and 1 <= len(dates) <= 5
    first = body["prices"][0]
    assert float(first["low"]) <= float(first["close"]) <= float(first["high"])
    assert first["deliv_qty"] is not None and 0 <= float(first["deliv_pct"]) <= 100


def test_unknown_symbol_is_404_json_for_the_api_and_html_for_the_page(client: httpx.Client):
    api = client.get("/api/price/NOSUCHSYMBOL")
    assert api.status_code == 404 and api.json() == {
        "success": False,
        "error": "No NSE security with symbol NOSUCHSYMBOL",
    }
    page = client.get("/equities/NOSUCHSYMBOL", headers=HTML)
    assert page.status_code == 404 and "text/html" in page.headers["content-type"]
    assert "No NSE security with symbol NOSUCHSYMBOL" in page.text


def test_limit_is_validated(client: httpx.Client):
    response = client.get("/api/price/RELIANCE", params={"limit": 0})
    assert response.status_code == 422 and response.json()["success"] is False


def test_search_by_symbol_name_and_isin(client: httpx.Client):
    def symbols(query: str) -> list[str]:
        return [
            item["nse_symbol"]
            for item in client.get("/api/security", params={"q": query}).json()["securities"]
        ]

    assert "RELIANCE" in symbols("RELI")
    assert "TCS" in symbols("tata consultancy")
    assert symbols("INE002A01018") == ["RELIANCE"]
    assert symbols("zzzznotasecurity") == []


def test_pages_render(client: httpx.Client):
    dashboard = client.get("/health", headers=HTML)
    assert dashboard.status_code == 200 and 'id="source-table"' in dashboard.text
    listing = client.get("/equities", headers=HTML)
    assert listing.status_code == 200 and "<html" in listing.text and "/equities/RELIANCE" in listing.text
    detail = client.get("/equities/RELIANCE", headers=HTML)
    assert detail.status_code == 200 and "INE002A01018" in detail.text and 'id="price-table"' in detail.text
    assert 'id="excluded-banner"' not in detail.text
    # A symbol with an ampersand survives the URL.
    assert client.get("/equities/M%26M", headers=HTML).status_code == 200


def test_search_box_gets_a_fragment_not_a_page(client: httpx.Client):
    fragment = client.get("/equities", params={"q": "RELI"}, headers={**HTML, "HX-Request": "true"})
    assert (
        fragment.status_code == 200 and "<html" not in fragment.text and "/equities/RELIANCE" in fragment.text
    )


def test_static_assets_are_served_from_the_app(client: httpx.Client):
    for asset in (
        "htmx.min.js",
        "alpine.min.js",
        "daisyui.full.min.css",
        "mdi/css/materialdesignicons.min.css",
    ):
        response = client.get(f"/static/{asset}")
        assert response.status_code == 200 and "immutable" in response.headers["cache-control"], asset


def test_market_cap_comes_from_nse(client: httpx.Client):
    body = client.get("/api/security", params={"q": "RELIANCE"}).json()
    reliance = next(item for item in body["securities"] if item["nse_symbol"] == "RELIANCE")
    assert float(reliance["market_cap"]) > 1e12  # rupees
    # No query: the largest companies come first.
    top = client.get("/api/security", params={"limit": 20}).json()["securities"]
    caps = [float(item["market_cap"]) for item in top]
    assert caps == sorted(caps, reverse=True) and "RELIANCE" in {item["nse_symbol"] for item in top}


def test_exclusions(client: httpx.Client):
    body = client.get("/api/exclusion").json()
    assert body["success"] is True and len(body["excluded"]) > 0
    excluded = {item["symbol"]: item for item in body["excluded"]}
    assert "RELIANCE" not in excluded and "TCS" not in excluded
    # Every exclusion names at least one rule that excluded it, and none of them is a BSE rule.
    labels = {label for item in body["excluded"] for label in item["labels"]}
    assert all(item["labels"] for item in body["excluded"]) and not [
        label for label in labels if "BSE" in label
    ]
    # A trade-for-trade security shows the banner on its own page.
    symbol = next(item["symbol"] for item in body["excluded"] if "Series BE" in item["labels"])
    page = client.get(f"/equities/{symbol}", headers=HTML)
    assert page.status_code == 200 and 'id="excluded-banner"' in page.text and "Series BE" in page.text
