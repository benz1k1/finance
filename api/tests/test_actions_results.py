"""Corporate actions from the daily bundle and the results XBRL parsers (pure, on cached files)."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from equity_engine.parsers import filings, nse
from equity_engine.service import fundamentals

RAW = Path(__file__).resolve().parents[2] / "raw"
SAMPLES = RAW / "_reference" / "nse_api_probe_reliance"


@pytest.mark.parametrize(
    ("purpose", "kind", "amount", "factor"),
    [
        ("BONUS 1:1", "BONUS", None, Decimal("0.5")),
        ("BONUS 1:4", "BONUS", None, Decimal("0.8")),
        ("FVSPLT FRM RS 10 TO RE 1", "SPLIT", None, Decimal("0.1")),
        ("FV SPLT FRM RS 10 TO 2", "SPLIT", None, Decimal("0.2")),
        ("CAP RED RS 10 TO RS 2", "OTHER", None, None),
        ("RIGHTS 19:100 @ PRM RS 45", "RIGHTS", None, None),
        ("AGM/DIV - 13.5 RS PER SH", "DIVIDEND", Decimal("13.5"), None),
        ("INT DIV - RE 0.25 PER SH", "DIVIDEND", Decimal("0.25"), None),
        ("DIV-RS 7/- PER SHARE", "DIVIDEND", Decimal("7"), None),
        ("INTERIM DIVIDEND", "DIVIDEND", None, None),
        ("BUY BACK", "BUYBACK", None, None),
        ("ANNUAL GENERAL MEETING", "MEETING", None, None),
        ("DEMERGER", "DEMERGER", None, None),
    ],
)
def test_classify_action(purpose, kind, amount, factor):
    assert nse.classify_action(purpose) == (kind, amount, factor)


def test_daily_reports_bundle_old_and_new_layouts():
    old = nse.daily_reports((RAW / "nse_daily_reports/2019/PR010119.zip").read_bytes(), date(2019, 1, 1))
    assert old.market_caps == [] and old.actions and old.hits  # 2019 bundles have no mcap member
    assert {a.series for a in old.actions} <= nse.ACTION_SERIES
    new = nse.daily_reports((RAW / "nse_daily_reports/2026/PR310826.zip").read_bytes(), date(2026, 8, 31))
    assert len(new.market_caps) > 2500 and len(new.actions) > 50 and len(new.hits) > 100
    assert all(h.side in ("H", "L") for h in new.hits)
    assert len(new) == len(new.market_caps) + len(new.actions) + len(new.hits)


def test_results_xbrl_quarter_ytd_and_balance_sheet():
    annual = filings.financial_facts(
        (SAMPLES / "x_Fourth_Quarter_Consolidated_Audited.xml").read_bytes(), "INDAS_x.xml"
    )
    kinds = {f.period_kind for f in annual.facts}
    assert (
        kinds == {"Q", "YTD", "INSTANT"}
        and annual.taxonomy == "INDAS"
        and annual.period_end == date(2024, 3, 31)
    )
    by = {(f.item, f.period_kind): f for f in annual.facts}
    assert by[("RevenueFromOperations", "Q")].unit == "INR"
    assert by[("Assets", "INSTANT")].value > 0
    assert (
        by[("CashFlowsFromUsedInOperatingActivities", "YTD")].value
        > by[("RevenueFromOperations", "Q")].value / 10
    )
    quarter = filings.financial_facts(
        (SAMPLES / "x_First_Quarter_Consolidated_Un_Audited.xml").read_bytes(), "INDAS_y.xml"
    )
    assert {f.period_kind for f in quarter.facts} == {"Q", "INSTANT"}  # Q1: no cash flow, segment assets only
    row = fundamentals.canonical(annual)
    assert (
        row["q_revenue"] == Decimal("2407150000000.00")
        and row["bs_equity"] is not None
        and row["ytd_cfo"] is not None
    )
    assert not row["is_bank"] and fundamentals.ebitda(row) > float(row["q_pbt"])


def test_taxonomy_from_filename():
    assert filings.taxonomy_of("INTEGRATED_FILING_INDAS_1_2_WEB.xml") == "CAPMKT"
    assert filings.taxonomy_of("NBFC_INDAS_1.xml") == "NBFC"
    assert filings.taxonomy_of("BANKING_1.xml") == "BANKING"
    assert filings.taxonomy_of("NONINDAS_1.xml") == "NONINDAS"
    assert filings.taxonomy_of("INDAS_1.xml") == "INDAS"
    with pytest.raises(ValueError):
        filings.taxonomy_of("OTHER_1.xml")


def test_results_feed_listing_parses():
    listing = filings.results_filings(
        (RAW / "nse_results_filings/2024/results_filings_2024-10.json").read_bytes(), date(2024, 10, 1)
    )
    assert len(listing) > 1000
    first = listing[0]
    assert (
        first.filing_id.startswith("R") and first.feed == "RESULTS" and first.period_end == date(2024, 9, 30)
    )
    assert sum(1 for f in listing if f.xbrl_url) > len(listing) * 0.9
