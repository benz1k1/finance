"""Announcement classification, the F&O bhavcopy parser (on the cached file) and the timeline."""

from datetime import date
from pathlib import Path

import httpx
import pytest

from equity_engine.parsers import filings, nse

RAW = Path(__file__).resolve().parents[2] / "raw"


@pytest.mark.parametrize(
    ("category", "text", "kind"),
    [
        ("Financial Results", "Unaudited financial results for the quarter", "RESULTS"),
        ("Board Meeting", "Board meeting to consider fund raising", "BOARD_MEETING"),
        ("Acquisition", "Acquisition of 51% stake in XYZ Ltd", "ACQUISITION"),
        ("Updates", "The company has bagged an order worth Rs 120 crore", "ORDER_WIN"),
        ("Buyback", "Record date for buyback of equity shares", "BUYBACK"),
        ("Allotment of Securities", "Allotment of NCDs on private placement", "FUND_RAISE"),
        ("Credit Rating", "ICRA reaffirms rating", "RATING"),
        ("Change in Directors", "Resignation of independent director", "GOVERNANCE"),
        ("Analysts/Institutional Investor Meet", "Schedule of investor meet", "INVESTOR_MEET"),
        ("Shareholders meeting", "Proceedings of Annual General Meeting", "MEETING"),
        ("Something", "lorem ipsum", "OTHER"),
    ],
)
def test_classify_announcement(category, text, kind):
    assert filings.classify_announcement(category, text) == kind


def test_announcements_month_parses():
    path = RAW / "nse_announcements/2026/announcements_2026-08.json"
    if not path.is_file():
        pytest.fail(f"{path} is not cached; run: python ingest.py events --from 2026-08 --to 2026-08")
    docs = filings.announcements(path.read_bytes(), date(2026, 8, 1))
    assert len(docs) > 15000
    kinds = {d.event_kind for d in docs}
    assert {"RESULTS", "INVESTOR_MEET", "ORDER_WIN", "GOVERNANCE"} <= kinds
    assert all(d.broadcast_at.tzinfo is not None for d in docs[:50])


def test_fo_bhav_aggregates_per_underlying():
    path = RAW / "nse_fo_bhav/2026/BhavCopy_NSE_FO_0_0_0_20261001_F_0000.csv.zip"
    if not path.is_file():
        pytest.fail(
            f"{path} is not cached; run: python ingest.py derivatives --from 2026-10-01 --to 2026-10-01"
        )
    rows = nse.fo_bhav(path.read_bytes(), date(2026, 10, 1))
    by_symbol = {r.symbol: r for r in rows}
    assert len(by_symbol) > 150 and "RELIANCE" in by_symbol and "NIFTY" not in by_symbol
    reliance = by_symbol["RELIANCE"]
    assert (
        reliance.futures_oi > 0
        and reliance.near_expiry is not None
        and reliance.near_expiry >= date(2026, 10, 1)
    )
    assert reliance.pcr_oi is not None and 0 < float(reliance.pcr_oi) < 5
    assert reliance.basis_pct is not None and abs(float(reliance.basis_pct)) < 5


def test_timeline_api_and_page(client: httpx.Client):
    body = client.get("/api/timeline/RELIANCE", params={"limit": 50}).json()
    assert body["success"] and body["entries"]
    kinds = {e["kind"] for e in body["entries"]}
    assert kinds <= {"DOCUMENT", "RESULTS", "ACTION", "MEETING", "RATING", "DEAL", "STANCE"}
    ats = [e["at"] for e in body["entries"]]
    assert ats == sorted(ats, reverse=True)
    only_actions = client.get("/api/timeline/RELIANCE", params={"kind": "ACTION", "limit": 20}).json()
    assert all(e["kind"] == "ACTION" for e in only_actions["entries"])
    page = client.get("/equities/RELIANCE/timeline", headers={"Accept": "text/html"})
    assert page.status_code == 200 and 'id="timeline-rows"' in page.text
