"""The cache rules (sources/bronze.py): a cached file is never fetched again, never overwritten,
and a known-absent date is remembered. Uses a throwaway raw directory, not the real one."""

from datetime import date
from pathlib import Path

import pytest

from equity_engine.service import ingest
from equity_engine.sources import bronze
from equity_engine.sources.http import Fetched
from equity_engine.sources.registry import BY_ID

DAILY = BY_ID["nse_delivery_mto"]
SNAPSHOT = BY_ID["nse_price_band"]
DAY = date(2026, 9, 30)


@pytest.fixture()
def raw_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(bronze, "RAW_DIR", tmp_path)
    return tmp_path


def test_layout(raw_dir: Path):
    assert bronze.path_for(DAILY, DAY) == raw_dir / "nse_delivery_mto" / "2026" / "MTO_30092026.DAT"
    assert bronze.path_for(SNAPSHOT, DAY) == raw_dir / "nse_price_band" / "2026" / "2026-09-30__sec_list.csv"


def test_store_then_cached_and_never_overwritten(raw_dir: Path):
    assert bronze.cached(DAILY, DAY) is None
    content = b"Security Wise Delivery Position - Compulsory Rolling Settlement\n"
    path = bronze.store(DAILY, DAY, content)
    assert bronze.cached(DAILY, DAY) == path and path.read_bytes() == content
    with pytest.raises(FileExistsError):
        bronze.store(DAILY, DAY, content + b"changed")
    assert path.read_bytes() == content
    assert not list(raw_dir.rglob("*.part"))


def test_an_error_page_is_not_cached(raw_dir: Path):
    with pytest.raises(ValueError, match="does not look like the expected file"):
        bronze.store(DAILY, DAY, b"<!DOCTYPE html><html>Access Denied</html>")
    assert bronze.cached(DAILY, DAY) is None


def test_absent_marker(raw_dir: Path):
    assert not bronze.is_absent(DAILY, DAY)
    bronze.mark_absent(DAILY, DAY)
    assert bronze.is_absent(DAILY, DAY) and bronze.cached(DAILY, DAY) is None


def test_snapshot_dates_are_read_from_disk(raw_dir: Path):
    for day in (date(2026, 10, 1), date(2026, 9, 30)):
        bronze.store(SNAPSHOT, day, b"Symbol,Series,Security Name,Band,Remarks\n")
    assert bronze.cached_dates(SNAPSHOT) == [date(2026, 9, 30), date(2026, 10, 1)]


class _CountingFetcher:
    """Stands in for the network; fails the test if asked for anything that is on disk."""

    def __init__(self, found: bool) -> None:
        self.found = found
        self.urls: list[str] = []

    def get(self, source, url):
        self.urls.append(url)
        return Fetched(found=self.found, content=b"")


def test_an_ingested_day_costs_no_request(connection):
    """Re-running over a day that is already ingested answers SKIPPED without asking the network."""
    done = connection.exec_driver_sql(
        "SELECT logical_date FROM ingest_run WHERE source_id = 'nse_delivery_mto' AND status = 'OK' "
        "ORDER BY logical_date DESC LIMIT 1"
    ).scalar()
    if done is None:
        pytest.fail("No delivery file ingested yet. Run: python ingest.py rebuild")
    fetcher = _CountingFetcher(found=True)
    outcome = ingest.ingest_one(DAILY, done, fetcher)  # type: ignore[arg-type]
    assert outcome.status == "SKIPPED" and fetcher.urls == []


def test_an_old_missing_date_is_remembered_as_a_holiday(raw_dir: Path, monkeypatch: pytest.MonkeyPatch):
    recorded: list[tuple] = []
    monkeypatch.setattr(ingest, "_record", lambda *args: recorded.append(args))
    monkeypatch.setattr(ingest, "row", lambda *args, **kwargs: None)
    holiday = date(2019, 1, 26)
    fetcher = _CountingFetcher(found=False)
    first = ingest.ingest_one(DAILY, holiday, fetcher)  # type: ignore[arg-type]
    second = ingest.ingest_one(DAILY, holiday, fetcher)  # type: ignore[arg-type]
    assert (first.status, second.status) == ("NO_DATA", "NO_DATA")
    assert len(fetcher.urls) == 1  # asked once, remembered after
    assert bronze.is_absent(DAILY, holiday)


def test_a_recent_missing_file_is_not_remembered(raw_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ingest, "row", lambda *args, **kwargs: None)
    today = ingest.today_ist()
    fetcher = _CountingFetcher(found=False)
    outcome = ingest.ingest_one(DAILY, today, fetcher)  # type: ignore[arg-type]
    assert outcome.status == "NOT_PUBLISHED" and not bronze.is_absent(DAILY, today)


def test_offline_mode_never_touches_the_network(raw_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ingest, "row", lambda *args, **kwargs: None)
    assert ingest.ingest_one(DAILY, DAY, None).status == "NOT_CACHED"


def test_a_day_without_prices_asks_for_nothing_else(monkeypatch: pytest.MonkeyPatch):
    """A holiday already recorded as NO_DATA must not go on to request delivery or the reports
    bundle for that date (22-Jun-2019 has a stray delivery file and no price file)."""
    asked: list[str] = []

    def fake_ingest_one(source, day, fetcher, *, reload=False):
        asked.append(source.source_id)
        return ingest.Outcome(source.source_id, day, "SKIPPED", recorded="NO_DATA")

    monkeypatch.setattr(ingest, "ingest_one", fake_ingest_one)
    outcomes = ingest.ingest_prices(date(2019, 6, 22), None)
    assert asked == ["nse_bhav_legacy"] and len(outcomes) == 1
