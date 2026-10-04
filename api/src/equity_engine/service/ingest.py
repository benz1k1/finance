"""
The ingestion pipeline (spec §83): cache → parse → validate → load, one source and one date at
a time, each in its own transaction so a long backfill keeps what it has finished.

The cache is consulted first and the network last. ``fetcher=None`` is offline mode: nothing is
requested, and a file that is not on disk is simply not ingested. That is how a rebuilt schema
is refilled.

Downloading can run in parallel (``download_prices``); parsing and loading stay sequential,
because delivery and market cap are written onto the price rows of the same date.
"""

import xml.etree.ElementTree as ElementTree
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from loguru import logger

from equity_engine.config import INGEST_ABSENT_AFTER_DAYS
from equity_engine.db import execute, execute_many, row, rows, transaction
from equity_engine.ids import new_id
from equity_engine.parsers import filings, nse
from equity_engine.parsers.models import BrsrFilingRow
from equity_engine.service import load
from equity_engine.sources import bronze
from equity_engine.sources.http import Fetcher, SourceBlocked
from equity_engine.sources.registry import (
    BY_ID,
    HISTORY_FIRST_DATE,
    MONTHLY_SOURCES,
    SNAPSHOT_SOURCES,
    Source,
    month_end,
    price_source_for,
)
from equity_engine.universe import in_universe

IST = ZoneInfo("Asia/Kolkata")

Parser = Callable[[bytes, date], Any]  # a list of records, or one composite record (the daily bundle)
Loader = Callable[[Any, Any, str, date], int]

# parser key -> (parse, load). Index sources share one pair; see _steps().
_STEPS: dict[str, tuple[Parser, Loader]] = {
    "nse_bhav_udiff": (nse.bhav_udiff, load.prices),
    "nse_bhav_legacy": (nse.bhav_legacy, load.prices),
    "nse_delivery_mto": (nse.delivery_mto, load.delivery),
    "nse_market_cap": (nse.daily_reports, load.daily_reports),
    "nse_equity_master": (nse.equity_master, load.securities),
    "nse_sme_master": (nse.sme_master, load.securities),
    "nse_price_band": (nse.price_band, load.bands),
    "nse_bulk_deal": (nse.bulk_deal, load.deals),
    "nse_block_deal": (nse.block_deal, load.deals),
    "nse_surveillance_asm": (nse.surveillance_asm, load.surveillance),
    "nse_surveillance_gsm": (nse.surveillance_gsm, load.surveillance),
    "nse_surveillance_esm": (nse.surveillance_esm, load.surveillance),
    "nse_bulk_deal_history": (filings.bulk_deal_history, load.deals),
    "nse_block_deal_history": (filings.block_deal_history, load.deals),
    "nse_shareholding_filings": (filings.shareholding_filings, load.shareholding_filings),
    "nse_results_filings": (filings.results_filings, load.fin_filings),
    "nse_integrated_filings": (filings.integrated_filings, load.fin_filings),
    "nse_announcements": (filings.announcements, load.documents),
    "nse_board_meetings": (filings.board_meetings, load.board_meetings),
    "nse_credit_ratings": (filings.credit_ratings, load.credit_ratings),
    "nse_fo_bhav": (nse.fo_bhav, load.derivatives),
}
# The BRSR filing list is parsed for its links only; it has no table of its own.
_LISTING_ONLY = frozenset({"nse_brsr_filings"})


@dataclass(frozen=True)
class Outcome:
    source_id: str
    day: date
    status: str  # OK | NO_DATA | SKIPPED | NOT_CACHED | NOT_PUBLISHED
    rows: int = 0
    from_cache: bool = True
    recorded: str | None = None  # for SKIPPED: what the earlier run recorded (OK | NO_DATA)


def today_ist() -> date:
    return datetime.now(IST).date()


def calendar_days(first: date, last: date) -> Iterator[date]:
    """Every date in the range, weekends included: NSE holds special sessions on some Saturdays
    and Sundays (20-Jan-2024, Diwali Muhurat trading). A day with no session costs one request,
    once; it is then remembered as absent."""
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


def _steps(source: Source) -> tuple[Parser, Loader]:
    if source.parser == "nse_index":
        index_code = source.source_id.removeprefix("nse_index_")
        return (lambda content, day: nse.index_constituents(content, index_code)), load.index_constituents
    return _STEPS[source.parser]


def _record(source: Source, day: date, status: str, raw_id: str | None, parsed: int, loaded: int) -> None:
    with transaction() as connection:
        execute(
            connection,
            """
            INSERT INTO ingest_run (run_id, source_id, logical_date, raw_id, status, rows_parsed, rows_loaded)
            VALUES (:run_id, :source_id, :day, :raw_id, :status, :parsed, :loaded)
            ON CONFLICT (source_id, logical_date) DO UPDATE SET
                raw_id = EXCLUDED.raw_id, status = EXCLUDED.status, rows_parsed = EXCLUDED.rows_parsed,
                rows_loaded = EXCLUDED.rows_loaded, finished_at = now()
            """,
            {
                "run_id": new_id(),
                "source_id": source.source_id,
                "day": day,
                "raw_id": raw_id,
                "status": status,
                "parsed": parsed,
                "loaded": loaded,
            },
        )


def fetch_to_cache(source: Source, day: date, fetcher: Fetcher | None) -> str:
    """Make sure the file for (source, day) is on disk, asking the network only if it is neither
    cached nor known to be absent. Returns CACHED | FETCHED | NO_DATA | NOT_PUBLISHED.
    Safe to call from several threads for different files."""
    if bronze.cached(source, day) is not None:
        return "CACHED"
    if bronze.is_absent(source, day):
        return "NO_DATA"
    if fetcher is None:
        raise ValueError(f"{source.source_id} {day} is not cached and no fetcher was given")
    if source.kind == "monthly" and month_end(day) >= today_ist():
        # A month still in progress would be cached half-full and never refreshed.
        return "NOT_PUBLISHED"
    if source.kind == "snapshot" and day != today_ist():
        raise ValueError(
            f"{source.source_id} is a current-only file: it can be fetched for today "
            f"({today_ist()}) but not for {day}, and there is no cached copy for that date."
        )
    fetched = fetcher.get(source, source.url(day))
    if not fetched.found:
        if source.kind == "snapshot":
            raise ValueError(f"{source.source_id}: {source.url(day)} answered 404")
        if (today_ist() - day).days <= INGEST_ABSENT_AFTER_DAYS:
            return "NOT_PUBLISHED"
        # A weekday with no file this long after the fact is a market holiday.
        bronze.mark_absent(source, day)
        return "NO_DATA"
    bronze.store(source, day, fetched.content)
    return "FETCHED"


def download_prices(days: Sequence[date], fetcher: Fetcher, workers: int) -> Counter[str]:
    """Fill the cache for a range of trade dates with ``workers`` concurrent downloads. Nothing
    is parsed or loaded here; ``ingest_prices`` then finds every file on disk.

    Two passes, so a market holiday costs one request rather than three: the price files first,
    then delivery and the reports bundle only for the dates that turned out to have prices.
    The first denial stops everything (see ``Fetcher``) and is raised after the pool drains."""
    tally: Counter[str] = Counter()

    def fetch_all(jobs: list[tuple[Source, date]]) -> None:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            states = list(pool.map(lambda job: _fetch_or_blocked(job[0], job[1], fetcher), jobs))
        tally.update(states)
        if "BLOCKED" in states:
            raise SourceBlocked(f"{states.count('BLOCKED')} downloads were not attempted after a denial")

    fetch_all([(price_source_for(day), day) for day in days])
    traded = [day for day in days if bronze.cached(price_source_for(day), day) is not None]
    fetch_all([(BY_ID[name], day) for day in traded for name in ("nse_delivery_mto", "nse_daily_reports")])
    return tally


def _fetch_or_blocked(source: Source, day: date, fetcher: Fetcher) -> str:
    # The boundary where a denial is turned into a status, so one refused request does not
    # throw away the results of the downloads already finished in the same pool.
    try:
        return fetch_to_cache(source, day, fetcher)
    except SourceBlocked as blocked:
        logger.error(f"blocked at {source.source_id} {day}: {blocked}")
        return "BLOCKED"
    except httpx.TransportError as failed:
        logger.warning(f"{source.source_id} {day} failed in transit: {failed!r}")
        return "FAILED"


def ingest_one(source: Source, day: date, fetcher: Fetcher | None, *, reload: bool = False) -> Outcome:
    if not source.covers(day):
        raise ValueError(f"{source.source_id} does not cover {day}")
    if not reload:
        with transaction() as connection:
            done = row(
                connection,
                "SELECT status, rows_loaded FROM ingest_run WHERE source_id = :s AND logical_date = :d",
                {"s": source.source_id, "d": day},
            )
        if done is not None:
            return Outcome(source.source_id, day, "SKIPPED", done["rows_loaded"], recorded=done["status"])

    path = bronze.cached(source, day)
    from_cache = path is not None
    if path is None:
        if fetcher is None and not bronze.is_absent(source, day):
            return Outcome(source.source_id, day, "NOT_CACHED")
        state = fetch_to_cache(source, day, fetcher)
        if state == "NO_DATA":
            _record(source, day, "NO_DATA", None, 0, 0)
        if state != "FETCHED":
            return Outcome(source.source_id, day, state, from_cache=False)
        path = bronze.path_for(source, day)

    if source.parser in _LISTING_ONLY:
        with transaction() as connection:
            raw = bronze.register(connection, source, day, path)
        _record(source, day, "OK", raw["raw_id"], 0, 0)
        return Outcome(source.source_id, day, "OK", 0, from_cache)
    parse, loader = _steps(source)
    records = parse(path.read_bytes(), day)
    with transaction() as connection:
        raw = bronze.register(connection, source, day, path)
        loaded = loader(connection, records, raw["raw_id"], day)
    _record(source, day, "OK", raw["raw_id"], len(records), loaded)
    logger.info(f"ingested {source.source_id} {day}: {len(records)} parsed, {loaded} loaded")
    return Outcome(source.source_id, day, "OK", loaded, from_cache)


def ingest_prices(day: date, fetcher: Fetcher | None, *, reload: bool = False) -> list[Outcome]:
    """One trade date: the price file, then delivery and market cap onto it. Neither without prices."""
    price = ingest_one(price_source_for(day), day, fetcher, reload=reload)
    has_prices = price.status == "OK" or (price.status == "SKIPPED" and price.recorded == "OK")
    if not has_prices:
        return [price]
    return [
        price,
        ingest_one(BY_ID["nse_delivery_mto"], day, fetcher, reload=reload),
        ingest_one(BY_ID["nse_daily_reports"], day, fetcher, reload=reload),
    ]


def months(first: date, last: date) -> Iterator[date]:
    """First-of-month dates from the month of ``first`` to the month of ``last``."""
    month = first.replace(day=1)
    while month <= last:
        yield month
        month = (month_end(month) + timedelta(days=1)).replace(day=1)


def ingest_months(
    source: Source, first: date, last: date, fetcher: Fetcher | None, *, reload: bool = False
) -> list[Outcome]:
    """A monthly source over a range of months, oldest first. Months the source does not cover
    are passed over; the month still in progress is reported as NOT_PUBLISHED."""
    return [
        ingest_one(source, month, fetcher, reload=reload)
        for month in months(first, last)
        if source.covers(month)
    ]


# ------------------------------------------------------------------ documents (XBRL behind a filing)


def _fetch_document(source: Source, path: Path, url: str, fetcher: Fetcher) -> str:
    # Same boundary as _fetch_or_blocked: a denial becomes a status so finished downloads count.
    if path.is_file():
        return "CACHED"
    try:
        fetched = fetcher.get(source, url)
    except SourceBlocked as blocked:
        logger.error(f"blocked at {source.source_id} {url}: {blocked}")
        return "BLOCKED"
    except httpx.TransportError as failed:
        # A timeout or dropped connection on one file. Nothing is cached, so the next run asks
        # for it again; the other downloads in this run are unaffected.
        logger.warning(f"{source.source_id}: {url} failed in transit: {failed!r}")
        return "FAILED"
    if not fetched.found:
        logger.warning(f"{source.source_id}: {url} answered 404")
        return "MISSING"
    if path.is_file():
        # Another job running at the same time cached it while this request was in flight.
        return "CACHED"
    try:
        bronze.store_document(source, path, fetched.content)
    except bronze.IncompleteDocument as truncated:
        logger.warning(str(truncated))
        return "FAILED"
    return "FETCHED"


def _download_documents(
    source: Source, jobs: list[tuple[Path, str]], fetcher: Fetcher, workers: int
) -> Counter[str]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        states = list(pool.map(lambda job: _fetch_document(source, job[0], job[1], fetcher), jobs))
    tally = Counter(states)
    if tally["BLOCKED"]:
        raise SourceBlocked(f"{tally['BLOCKED']} downloads were not attempted after a denial")
    return tally


def ingest_shareholding_patterns(
    fetcher: Fetcher | None, workers: int = 1, *, limit: int | None = None
) -> Counter[str]:
    """Read the XBRL behind every listed filing that has no breakdown yet. Downloads the missing
    files first (in parallel, when a fetcher is given), then parses and loads from disk. A file
    that does not parse is logged and counted, and the rest carry on: one company's malformed
    filing must not hold back two thousand others."""
    source = BY_ID["nse_shareholding_xbrl"]
    with transaction() as connection:
        pending = rows(
            connection,
            """
            SELECT f.record_id, f.symbol, f.period_end, f.xbrl_url FROM shareholding_filing f
             WHERE f.xbrl_url IS NOT NULL
               AND EXISTS (SELECT 1 FROM security s WHERE s.nse_symbol = f.symbol AND """
            + in_universe("s.isin")
            + """)
               AND NOT EXISTS (SELECT 1 FROM shareholding_pattern p WHERE p.record_id = f.record_id)
             ORDER BY f.period_end DESC, f.symbol
            """
            + (" LIMIT :limit" if limit else ""),
            {"limit": limit} if limit else {},
        )
    jobs = [
        (bronze.document_path(source, item["period_end"].year, item["xbrl_url"]), item) for item in pending
    ]
    tally: Counter[str] = Counter()
    if fetcher is not None:
        tally += _download_documents(
            source, [(path, item["xbrl_url"]) for path, item in jobs], fetcher, workers
        )
    for path, item in jobs:
        if not path.is_file():
            tally["NOT_CACHED"] += 1
            continue
        try:
            record = filings.shareholding_pattern(path.read_bytes())
        except (KeyError, ValueError, ElementTree.ParseError) as invalid:
            logger.warning(f"shareholding XBRL {path.name} ({item['symbol']}) not loaded: {invalid!r}")
            tally["INVALID"] += 1
            continue
        with transaction() as connection:
            raw = bronze.register(connection, source, item["period_end"], path)
            load.shareholding_pattern(connection, record, raw["raw_id"], item["record_id"], item["symbol"])
        tally["LOADED"] += 1
    return tally


def ingest_results_xbrl(
    fetcher: Fetcher | None,
    workers: int = 1,
    *,
    limit: int | None = None,
    newest_first: bool = True,
    batch: int = 400,
    index_code: str | None = None,
    consolidated_first: bool = True,
) -> Counter[str]:
    """Read the XBRL behind every results filing that has no facts yet (spec §5), in batches:
    download a batch, parse and load it, then take the next, so the newest quarters are usable
    long before the ten-year backlog has finished downloading. Newest filings first by default.
    ``index_code`` restricts the universe to the newest constituent list of that index (e.g.
    ``nifty50``); ``consolidated_first`` leaves a standalone filing for later when the same
    quarter has a consolidated one. Symbols no longer in the security master are never fetched.
    A malformed file is counted, not fatal. ``limit`` caps the total number of filings."""
    source = BY_ID["nse_results_xbrl"]
    tally: Counter[str] = Counter()
    taken = 0
    while True:
        size = batch if limit is None else min(batch, limit - taken)
        if size <= 0:
            break
        with transaction() as connection:
            pending = rows(
                connection,
                """
                SELECT f.filing_id, f.symbol, f.period_end, f.xbrl_url FROM fin_filing f
                 WHERE f.xbrl_url IS NOT NULL
                   AND EXISTS (SELECT 1 FROM security s WHERE s.nse_symbol = f.symbol)
                   AND (CAST(:index_code AS text) IS NULL OR EXISTS (
                        SELECT 1 FROM index_constituent_snapshot c JOIN security s ON s.isin = c.isin
                         WHERE s.nse_symbol = f.symbol AND c.index_code = CAST(:index_code AS text)
                           AND c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot
                                                   WHERE index_code = CAST(:index_code AS text))))
                   AND NOT (CAST(:consolidated_first AS boolean) AND NOT f.consolidated AND EXISTS (
                        SELECT 1 FROM fin_filing o WHERE o.symbol = f.symbol AND o.period_end = f.period_end
                           AND o.consolidated AND o.xbrl_url IS NOT NULL
                           AND NOT EXISTS (SELECT 1 FROM fin_fact x WHERE x.filing_id = o.filing_id)
                           AND NOT EXISTS (SELECT 1 FROM results_xbrl_skip k WHERE k.filing_id = o.filing_id)))
                   AND NOT EXISTS (SELECT 1 FROM fin_fact x WHERE x.filing_id = f.filing_id)
                   AND NOT EXISTS (SELECT 1 FROM results_xbrl_skip k WHERE k.filing_id = f.filing_id)
                 ORDER BY f.period_end """
                + ("DESC" if newest_first else "ASC")
                + ", f.consolidated DESC, f.symbol LIMIT :n",
                {"n": size, "index_code": index_code, "consolidated_first": consolidated_first},
            )
        if not pending:
            break
        jobs = [
            (bronze.document_path(source, item["period_end"].year, item["xbrl_url"]), item)
            for item in pending
        ]
        if fetcher is not None:
            tally += _download_documents(
                source, [(path, item["xbrl_url"]) for path, item in jobs], fetcher, workers
            )
        skipped: list[dict[str, Any]] = []
        for path, item in jobs:
            if not path.is_file():
                tally["NOT_CACHED"] += 1
                skipped.append({"filing_id": item["filing_id"], "reason": "NOT_CACHED"})
                continue
            try:
                parsed = filings.financial_facts(path.read_bytes(), path.name)
            except (KeyError, ValueError, ElementTree.ParseError) as invalid:
                logger.warning(f"results XBRL {path.name} ({item['symbol']}) not loaded: {invalid!r}")
                tally["INVALID"] += 1
                skipped.append({"filing_id": item["filing_id"], "reason": "INVALID"})
                continue
            if not parsed.facts:
                tally["EMPTY"] += 1
                skipped.append({"filing_id": item["filing_id"], "reason": "EMPTY"})
                continue
            with transaction() as connection:
                raw = bronze.register(connection, source, item["period_end"], path)
                load.fin_facts(connection, parsed, raw["raw_id"], item["filing_id"])
            tally["LOADED"] += 1
        # Filings that cannot be loaded this run are remembered for the run, so the next batch
        # moves on instead of re-selecting them. The table is session-scoped: a later run with
        # the network available tries them again.
        with transaction() as connection:
            execute_many(
                connection,
                "INSERT INTO results_xbrl_skip (filing_id, reason) VALUES (:filing_id, :reason) ON CONFLICT DO NOTHING",
                skipped,
            )
        taken += len(pending)
        logger.info(f"results XBRL batch: {dict(tally)}")
        if fetcher is None and all(not path.is_file() for path, _ in jobs):
            break
    return tally


def ingest_company_profiles(
    fetcher: Fetcher | None, workers: int = 1, *, limit: int | None = None
) -> Counter[str]:
    """Read the sustainability-report XBRL of every filing in the newest cached filing list.
    Same shape as ``ingest_shareholding_patterns``."""
    listing_source = BY_ID["nse_brsr_filings"]
    source = BY_ID["nse_brsr_xbrl"]
    cached = bronze.cached_dates(listing_source)
    if not cached:
        raise ValueError("No BRSR filing list is cached. Run: python ingest.py profiles (it fetches one)")
    listing: list[BrsrFilingRow] = filings.brsr_filings(
        bronze.path_for(listing_source, cached[-1]).read_bytes(), cached[-1]
    )
    with transaction() as connection:
        done = {
            (item["symbol"], item["fy_to"]): item["submitted_on"]
            for item in rows(connection, "SELECT symbol, fy_to, submitted_on FROM company_profile")
        }
    pending = [
        filing
        for filing in listing
        if (filing.symbol, filing.fy_to) not in done
        or done[(filing.symbol, filing.fy_to)] < filing.submitted_on
    ][:limit]
    jobs = [(bronze.document_path(source, filing.fy_to, filing.xbrl_url), filing) for filing in pending]
    tally: Counter[str] = Counter()
    if fetcher is not None:
        tally += _download_documents(
            source, [(path, filing.xbrl_url) for path, filing in jobs], fetcher, workers
        )
    for path, filing in jobs:
        if not path.is_file():
            tally["NOT_CACHED"] += 1
            continue
        try:
            record = filings.company_profile(path.read_bytes())
        except (KeyError, ValueError, ElementTree.ParseError) as invalid:
            logger.warning(f"BRSR XBRL {path.name} ({filing.symbol}) not loaded: {invalid!r}")
            tally["INVALID"] += 1
            continue
        with transaction() as connection:
            raw = bronze.register(connection, source, filing.submitted_on, path)
            load.company_profile(connection, record, raw["raw_id"], filing)
        tally["LOADED"] += 1
    return tally


def ingest_snapshots(day: date, fetcher: Fetcher | None, *, reload: bool = False) -> list[Outcome]:
    return [ingest_one(source, day, fetcher, reload=reload) for source in SNAPSHOT_SOURCES]


def rebuild_from_cache(*, reload: bool = False) -> list[Outcome]:
    """Ingest everything that is on disk, with no network at all."""
    outcomes: list[Outcome] = []
    for source in SNAPSHOT_SOURCES:
        for day in bronze.cached_dates(source):
            outcomes.append(ingest_one(source, day, None, reload=reload))
    for source in MONTHLY_SOURCES:
        for month in bronze.cached_months(source):
            outcomes.append(ingest_one(source, month, None, reload=reload))
    for day in calendar_days(HISTORY_FIRST_DATE, today_ist()):
        if bronze.cached(price_source_for(day), day) is not None:
            outcomes.extend(ingest_prices(day, None, reload=reload))
    return outcomes


def rebuild_documents_from_cache() -> dict[str, Counter[str]]:
    """The XBRL-derived tables, from the files on disk. Runs after ``rebuild_from_cache``,
    which restores the filing lists these depend on."""
    result = {"shareholding": ingest_shareholding_patterns(None), "results": ingest_results_xbrl(None)}
    if bronze.cached_dates(BY_ID["nse_brsr_filings"]):
        result["profiles"] = ingest_company_profiles(None)
    return result
