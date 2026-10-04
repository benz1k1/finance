"""Ownership (promoter / FII / DII), company profile and deal history (spec §117): the parsers
against slices of real filings, then the pages and endpoints against the running app."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from equity_engine.parsers import filings
from equity_engine.service.company import website_url
from equity_engine.sources.registry import BY_ID, month_end

HTML = {"Accept": "text/html"}


# ------------------------------------------------------------------ parsers


def test_shareholding_filing_list(fixtures: Path):
    rows = {
        row.symbol: row
        for row in filings.shareholding_filings(
            (fixtures / "shareholding_filings.json").read_bytes(), date(2026, 7, 1)
        )
    }
    tcs = rows["TCS"]
    assert (tcs.period_end, tcs.promoter_pct, tcs.public_pct) == (
        date(2026, 6, 30),
        Decimal("71.77"),
        Decimal("28.23"),
    )
    assert tcs.broadcast_at.utcoffset().total_seconds() == 5.5 * 3600  # the feed's times are IST
    assert tcs.xbrl_url.endswith("_WEB.xml") and not tcs.revised
    assert rows["RELIANCE"].isin is None  # NSE's list simply omits it for some companies
    assert rows["ASAHIINDIA"].isin == "INE 439A0401"  # malformed as typed by the company: kept, not a key
    assert rows["TIINDIA"].xbrl_url is None and rows["TIINDIA"].revised  # link ends in "/-"


def test_shareholding_xbrl_gives_the_fii_and_dii_split(fixtures: Path):
    pattern = filings.shareholding_pattern((fixtures / "SHP_RELIANCE.xml").read_bytes())
    assert (pattern.symbol, pattern.period_end) == ("RELIANCE", date(2026, 6, 30))
    assert (pattern.promoter_pct, pattern.public_pct) == (Decimal("50.48"), Decimal("49.52"))
    assert (pattern.fii_pct, pattern.dii_pct) == (Decimal("17.20"), Decimal("21.19"))
    assert pattern.fpi_pct == Decimal("17.06")  # category I 16.52 + category II 0.54
    assert (pattern.mutual_fund_pct, pattern.insurance_pct) == (Decimal("10.11"), Decimal("9.20"))
    assert pattern.total_shares == 13_532_538_722 and pattern.total_shareholders == 4_651_863
    # The institutional totals contain their parts.
    assert pattern.dii_pct >= pattern.mutual_fund_pct + pattern.insurance_pct
    assert pattern.fii_pct >= pattern.fpi_pct


def test_a_category_missing_from_the_filing_is_none_not_zero(fixtures: Path):
    content = (
        (fixtures / "SHP_RELIANCE.xml")
        .read_bytes()
        .replace(b"InstitutionsDomestic_ContextI", b"SomethingElse_ContextI")
    )
    assert filings.shareholding_pattern(content).dii_pct is None


def test_a_company_with_no_promoter_group_loads_with_promoter_none(fixtures: Path):
    content = (fixtures / "SHP_RELIANCE.xml").read_bytes()
    content = content.replace(b"ShareholdingOfPromoterAndPromoterGroup_ContextI", b"Absent_ContextI")
    pattern = filings.shareholding_pattern(content)
    assert pattern.promoter_pct is None and pattern.public_pct == Decimal("49.52")


def test_brsr_filing_list_keeps_only_filings_with_xbrl(fixtures: Path):
    rows = filings.brsr_filings((fixtures / "brsr_filings.json").read_bytes(), date(2026, 10, 1))
    assert {row.symbol for row in rows} >= {"RELIANCE"}
    assert all(row.xbrl_url.endswith(".xml") and row.fy_to == 2026 for row in rows)


def test_company_profile_from_the_sustainability_report(fixtures: Path):
    profile = filings.company_profile((fixtures / "BRSR_RELIANCE.xml").read_bytes())
    assert profile.company_name == "Reliance Industries Limited"
    assert profile.website == "www.ril.com" and profile.cin == "L17110MH1973PLC019786"
    assert profile.incorporated_on == date(1973, 5, 8)
    assert (profile.states_served, profile.countries_served, profile.employees) == (35, 112, 38314)
    assert [activity.seq for activity in profile.activities] == [1, 2]
    assert profile.activities[0].main_activity == "Oil to chemicals (Products)"
    assert profile.activities[0].turnover_pct == Decimal("92.37")
    assert len(profile.products) == 12
    first = profile.products[0]
    assert (
        first.nic_code == "192001" and first.turnover_pct == Decimal("65.22") and "petroleum" in first.product
    )


def test_deal_history_csv(fixtures: Path):
    rows = filings.bulk_deal_history((fixtures / "bulk_deals_2026-08.csv").read_bytes(), date(2026, 8, 1))
    first = rows[0]
    assert (first.kind, first.deal_date, first.seq, first.side) == ("BULK", date(2026, 8, 3), 1, "BUY")
    assert first.quantity == 235306  # "2,35,306" in the file
    assert [row.seq for row in rows if row.deal_date == date(2026, 8, 3)] == [1, 2, 3]
    assert {row.symbol for row in rows} >= {"63MOONS", "ZEEL"}


def test_website_gets_a_scheme():
    assert website_url("www.ril.com") == "https://www.ril.com"
    assert website_url("https://www.tcs.com") == "https://www.tcs.com"
    assert website_url(None) is None and website_url("") is None


def test_monthly_sources_ask_for_whole_months():
    source = BY_ID["nse_bulk_deal_history"]
    url = source.url(date(2026, 2, 1))
    assert (
        "from=01-02-2026&to=28-02-2026" in url and "optionType=bulk_deals" in url and url.endswith("csv=true")
    )
    assert source.filename(date(2026, 2, 1)) == "bulk_deals_2026-02.csv"
    assert month_end(date(2024, 2, 10)) == date(2024, 2, 29)
    assert BY_ID["nse_shareholding_filings"].covers(date(2021, 10, 1))
    assert not BY_ID["nse_shareholding_filings"].covers(date(2021, 9, 1))


# ------------------------------------------------------------------ live app


@pytest.fixture(scope="module")
def reliance(client: httpx.Client) -> dict:
    body = client.get("/api/ownership/RELIANCE").json()
    if not body["ownership"]:
        pytest.fail(
            "No shareholding filings ingested. Run: python ingest.py ownership --from 2026-07 --to 2026-09"
        )
    return body


def test_ownership_endpoint(reliance: dict):
    assert reliance["success"] is True and reliance["symbol"] == "RELIANCE"
    newest = reliance["ownership"][0]
    assert float(newest["promoter_pct"]) + float(newest["public_pct"]) == pytest.approx(100, abs=1.0)
    assert 0 < float(newest["fii_pct"]) < 60 and 0 < float(newest["dii_pct"]) < 60
    quarters = [quarter["period_end"] for quarter in reliance["ownership"]]
    assert quarters == sorted(quarters, reverse=True) and len(set(quarters)) == len(quarters)


def test_ownership_parts_never_exceed_the_whole(connection):
    bad = connection.exec_driver_sql(
        "SELECT count(*) FROM shareholding_pattern WHERE coalesce(promoter_pct, 0) + public_pct > 100.5 "
        "OR coalesce(fii_pct, 0) + coalesce(dii_pct, 0) > public_pct + 0.5 "
        "OR coalesce(mutual_fund_pct, 0) > coalesce(dii_pct, 100) + 0.01"
    ).scalar()
    assert bad == 0


def test_company_endpoint_and_page(client: httpx.Client, reliance: dict):
    body = client.get("/api/company/RELIANCE").json()
    if body["profile"] is None:
        pytest.fail("No company profiles ingested. Run: python ingest.py profiles")
    profile = body["profile"]
    assert profile["website_url"].startswith("https://") and "ril.com" in profile["website_url"]
    assert profile["activities"] and profile["products"]
    shares = [
        float(product["turnover_pct"])
        for product in profile["products"]
        if product["turnover_pct"] is not None
    ]
    assert shares == sorted(shares, reverse=True) and sum(shares) <= 100.5
    page = client.get("/security/RELIANCE", headers=HTML)
    assert page.status_code == 200
    for marker in (
        'id="ownership-card"',
        'id="company-website"',
        'id="product-table"',
        'id="ownership-history"',
    ):
        assert marker in page.text, marker


def test_a_company_without_a_sustainability_report_says_so(client: httpx.Client, connection):
    symbol = connection.exec_driver_sql(
        "SELECT s.nse_symbol FROM security s "
        "WHERE NOT EXISTS (SELECT 1 FROM company_profile p WHERE p.symbol = s.nse_symbol) ORDER BY 1 LIMIT 1"
    ).scalar()
    assert client.get(f"/api/company/{symbol}").json() == {"success": True, "symbol": symbol, "profile": None}
    page = client.get(f"/security/{symbol}", headers=HTML)
    assert page.status_code == 200 and "has not filed a sustainability report" in page.text


def test_deal_endpoint(client: httpx.Client, connection):
    symbol = connection.exec_driver_sql(
        "SELECT symbol FROM deal GROUP BY symbol ORDER BY count(*) DESC LIMIT 1"
    ).scalar()
    if symbol is None:
        pytest.fail("No deals ingested. Run: python ingest.py deals --from 2026-08 --to 2026-09")
    security = client.get("/api/security", params={"q": symbol, "all": "true"}).json()["securities"]
    if not any(item["nse_symbol"] == symbol for item in security):
        pytest.fail(f"Most-dealt symbol {symbol} is not in the master")
    deals = client.get(f"/api/deal/{symbol}", params={"limit": 20}).json()["deals"]
    assert 1 <= len(deals) <= 20
    dates = [deal["deal_date"] for deal in deals]
    assert dates == sorted(dates, reverse=True)
    assert all(deal["side"] in ("BUY", "SELL") and deal["quantity"] > 0 for deal in deals)


def test_ownership_screen_sorts_by_the_chosen_column(client: httpx.Client, reliance: dict):
    page = client.get("/ownership", params={"sort": "dii_pct"}, headers=HTML)
    assert page.status_code == 200 and 'id="ownership-table"' in page.text and "/security/" in page.text
    assert client.get("/ownership", params={"sort": "drop table"}, headers=HTML).status_code == 422
    assert client.get("/api/ownership/NOSUCHSYMBOL").status_code == 404
