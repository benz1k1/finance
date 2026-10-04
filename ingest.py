#!/usr/bin/env python3
"""
Ingest exchange files into the database (spec §83).

    python ingest.py daily                        # today's snapshots + the last 7 days of prices
    python ingest.py prices --from 2026-09-01 --to 2026-09-30   # backfill a range of trade dates
    python ingest.py prices --from 2019-01-01 --to 2019-12-31 --workers 4 --interval 0.5
                                                  # same, downloading 4 files at a time
    python ingest.py download --from 2019-01-01 --to 2019-12-31 --workers 6 --interval 0.3
                                                  # fill the cache only; ingest later with `prices`
    python ingest.py snapshots                    # today's current-only files (masters, bands,
                                                  # surveillance, indices, deals, BSE scrip list)
    python ingest.py snapshots --date 2026-10-01  # a past day, from the cache only
    python ingest.py deals --from 2019-01 --to 2026-09            # bulk and block deals, a month per request
    python ingest.py ownership --from 2026-07 --to 2026-09 --workers 5 --interval 0.35
                                                  # shareholding filings, then the XBRL behind each
                                                  # (promoter / FII / DII split)
    python ingest.py profiles --workers 5 --interval 0.35
                                                  # sustainability-report XBRL: website, activities, products
    python ingest.py rebuild                      # ingest everything on disk; no network at all
    python ingest.py status                       # what is cached and ingested
    python ingest.py bootstrap                    # create the DATA schema if missing (never drops it)
    python ingest.py migrate                      # apply schema/migrations/*.sql to the data schema
    python ingest.py results --from 2019-01 --to 2026-09 --workers 5 --interval 0.35 --index nifty50
                                                  # results filing lists (both NSE feeds), then the XBRL
                                                  # behind each filing, newest quarter first, consolidated
                                                  # before standalone; --index limits the universe; resumable
    python ingest.py documents --kind INVESTOR_MEET --kind PRESS_RELEASE --limit 200 [--symbol X] [--extract]
                                                  # announcement PDFs -> document_text; --extract reads them with
                                                  # Claude (needs llm.enabled in the env YAML)
    python ingest.py events --from 2019-01 --to 2026-09   # announcements, board meetings, credit ratings, a month per request
    python ingest.py derivatives --from 2024-07-06 --to 2026-10-03 --interval 0.35
                                                  # F&O bhavcopy per trade date -> derivative_oi (UDiFF era only)
    python ingest.py membership                   # Nifty 500 membership history from raw/_reference/index_history (no network)
    python ingest.py prune [--yes]                # delete every row for companies outside the universe (Nifty 500),
                                                  # both schemas plus their per-company cache files; asks for confirmation
    python ingest.py reports --from 2019-01-01 --to 2026-10-01
                                                  # re-read the cached daily reports bundles (corporate
                                                  # actions, band hits, market cap); no network
    python ingest.py signals [--as-of 2026-10-01] # run every implemented engine; write the ledger
    python ingest.py outcomes                     # mark every signal/stance whose 1/3/6/12/24-month window has passed
    python ingest.py backtest --from 2019-07-01 --to 2026-09-01 --step 5 --shard 0/6 &   # ... --shard 5/6 &
                                                  # replay the engines every 5th trade date, six processes in
                                                  # parallel (resumable); then `ingest.py outcomes` once
                                                  # (`daily` does this after the day's prices land)

Every downloaded file is cached under raw/ for good. A file already there is read from disk and
never requested again, so re-running any command is free; add ``--reload`` to parse and load a
cached file again after a parser fix (still no download). Requests are paced
(``ingest.min_interval_seconds``); if a host answers "Access Denied" the run stops at once.

Imports of the application package are inside the functions for the reason given in
load_data.py: EQUITY_ENGINE_ENV must be set before ``config`` is imported.
"""

import argparse
import os
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = REPO_ROOT / "api" / ".venv" / "bin" / "python"

if Path(sys.executable) != VENV_PYTHON:
    if not VENV_PYTHON.is_file():
        raise SystemExit(f"No venv at {VENV_PYTHON}. Run: cd api && uv sync")
    os.execv(VENV_PYTHON, [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
sys.path.insert(0, str(REPO_ROOT / "api" / "src"))


def _report(outcomes: list, requests_made: int) -> None:
    tally = Counter(outcome.status for outcome in outcomes)
    loaded = sum(outcome.rows for outcome in outcomes if outcome.status == "OK")
    for outcome in outcomes:
        if outcome.status not in ("SKIPPED", "NO_DATA"):
            origin = "cache" if outcome.from_cache else "fetched"
            print(
                f"  {outcome.status:13} {outcome.source_id:28} {outcome.day}  {outcome.rows:>6} rows  {origin}"
            )
    print(f"{dict(tally)} — {loaded} rows loaded, {requests_made} network requests")


def run(args: argparse.Namespace) -> None:
    from loguru import logger

    from equity_engine import universe
    from equity_engine.config import LOG_DIR
    from equity_engine.db import execute, transaction
    from equity_engine.service import documents as documents_service
    from equity_engine.service import health, schema, signals
    from equity_engine.service import membership as membership_service
    from equity_engine.service import outcomes as outcomes_service
    from equity_engine.service import prune as prune_service
    from equity_engine.service import stance as stance_module
    from equity_engine.service.ingest import (
        calendar_days,
        download_prices,
        ingest_company_profiles,
        ingest_months,
        ingest_one,
        ingest_prices,
        ingest_results_xbrl,
        ingest_shareholding_patterns,
        ingest_snapshots,
        rebuild_documents_from_cache,
        rebuild_from_cache,
        today_ist,
    )
    from equity_engine.sources import bronze
    from equity_engine.sources.http import Fetcher, SourceBlocked
    from equity_engine.sources.registry import BY_ID

    logger.remove()
    logger.add(LOG_DIR / "ingest.log", level="INFO", rotation="10 MB", retention=5)

    if args.command == "bootstrap":
        schema.ensure_data_schema()
        return
    if args.command == "migrate":
        schema.migrate_data()
        return
    if args.command == "reports":
        source = BY_ID["nse_daily_reports"]
        first, last = date.fromisoformat(args.first), date.fromisoformat(args.last)
        done: Counter[str] = Counter()
        for day in calendar_days(first, last):
            if bronze.cached(source, day) is None:
                continue
            done[ingest_one(source, day, None, reload=True).status] += 1
        print(f"daily reports re-read: {dict(done)}")
        return
    if args.command == "membership":
        report = membership_service.load()
        for snap in report["snapshots"]:
            print(f"  {snap['as_of']}  {snap['symbols']:>4} symbols  {snap['unresolved']:>3} unresolved")
        return
    if args.command == "prune":
        with transaction() as connection:
            before = prune_service.counts(connection)
        with transaction() as connection:
            files = prune_service.cache_files_outside(connection)
        total = sum(before.values())
        print(
            f"rows outside the universe ({universe.INDEX}): {total:,}; per-company cache files: {len(files):,}"
        )
        for table, n in before.items():
            if n:
                print(f"  {n:>10,}  {table}")
        if not args.yes:
            answer = input(f"Delete them? Type the index code ({universe.INDEX}) to confirm: ")
            if answer.strip() != universe.INDEX:
                raise SystemExit("not confirmed; nothing deleted")
        deleted = prune_service.prune()
        print(
            f"deleted {sum(v for k, v in deleted.items() if not k.startswith('cache')):,} rows and "
            f"{deleted['cache_files']:,} cached files ({deleted['cache_mb']} MB); vacuuming"
        )
        prune_service.vacuum()
        print("done")
        return
    if args.command == "outcomes":
        print(f"outcomes marked: {dict(outcomes_service.mark())}")
        return
    if args.command == "backtest":
        index, count = (int(part) for part in args.shard.split("/"))
        done = outcomes_service.backtest(
            date.fromisoformat(args.first), date.fromisoformat(args.last), args.step, (index, count)
        )
        print(f"backtest shard {args.shard}: {len(done)} runs")
        if args.mark:
            print(f"outcomes marked: {dict(outcomes_service.mark())}")
        return
    if args.command == "retune":
        report = outcomes_service.stance_retune(args.horizon, date.fromisoformat(args.split))
        print(
            f"horizon {report['horizon']} sessions, split {report['split']}: {report['signals']:,} backtest signals, "
            f"{report['groups']:,} security-runs, {report['marked']:,} marked"
        )
        print("\ntraining period, per engine and direction (weight is the current table's):")
        weights = stance_module.ENGINE_WEIGHT
        for (engine_key, direction), (n, hits, total) in sorted(
            report["table"].items(), key=lambda item: (item[0][1], -item[1][1] / item[1][0])
        ):
            print(
                f"  {engine_key:26s} {direction:4s} n={n:6d} hit={100 * hits / n:5.1f}% "
                f"mean excess={total / n:6.1f}% weight={weights.get((engine_key, direction), 1.0)}"
            )
        for label in ("equal_weights", "current_weights"):
            print(f"\n{label.replace('_', ' ')}:")
            for (period, side, kind), (n, hits, total) in sorted(report[label].items()):
                print(
                    f"  {period:8s} {side:5s} {kind:4s} n={n:6d} hit={100 * hits / n:5.1f}% mean excess={total / n:6.1f}%"
                )
        return
    if args.command == "signals":
        as_of = date.fromisoformat(args.as_of) if args.as_of else None
        summary = signals.run_all(as_of)
        print(
            f"engines as of {summary['as_of']}: {summary['signals']} signals, {summary['stances']} stances, "
            f"run {summary['run_id']}"
        )
        for key, count in summary["per_engine"].items():
            print(f"  {count:>6}  {key}")
        return
    if args.command == "status":
        with transaction() as connection:
            for source in health.sources(connection):
                print(
                    f"  {source['state']:6} {source['source_id']:28} files={source['files'] or 0:<5} "
                    f"{source['first_date'] or '-'} → {source['last_date'] or '-'}  last rows={source['last_rows'] or 0}"
                )
        return
    if args.command == "rebuild":
        _report(rebuild_from_cache(reload=args.reload), 0)
        for name, tally in rebuild_documents_from_cache().items():
            print(f"{name}: {dict(tally)}")
        return

    today = today_ist()
    interval = getattr(args, "interval", None)
    fetcher = Fetcher() if interval is None else Fetcher(archive_interval=interval)
    outcomes: list = []
    try:
        if args.command in ("snapshots", "daily"):
            day = date.fromisoformat(args.date) if getattr(args, "date", None) else today
            outcomes += ingest_snapshots(day, fetcher, reload=args.reload)
        if args.command in ("prices", "daily", "download"):
            if args.command == "daily":
                first, last = today - timedelta(days=7), today
            else:
                first, last = (
                    date.fromisoformat(args.first),
                    date.fromisoformat(args.last),
                )
            days = list(calendar_days(first, last))
            workers = getattr(args, "workers", 1)
            if workers > 1 or args.command == "download":
                started = time.monotonic()
                tally = download_prices(days, fetcher, workers)
                print(
                    f"download: {dict(tally)} in {time.monotonic() - started:.0f}s with {workers} workers, "
                    f"{fetcher.requests_made} requests"
                )
            if args.command != "download":
                for day in days:
                    outcomes += ingest_prices(day, fetcher, reload=args.reload)
        if args.command == "deals":
            first, last = date.fromisoformat(args.first + "-01"), date.fromisoformat(args.last + "-01")
            for name in ("nse_bulk_deal_history", "nse_block_deal_history"):
                outcomes += ingest_months(BY_ID[name], first, last, fetcher, reload=args.reload)
        if args.command == "ownership":
            first, last = date.fromisoformat(args.first + "-01"), date.fromisoformat(args.last + "-01")
            outcomes += ingest_months(
                BY_ID["nse_shareholding_filings"], first, last, fetcher, reload=args.reload
            )
            print(
                f"shareholding XBRL: {dict(ingest_shareholding_patterns(fetcher, args.workers, limit=args.limit))}"
            )
        if args.command == "documents":
            kinds = args.kind or ["INVESTOR_MEET", "PRESS_RELEASE"]
            print(
                f"document text: {dict(documents_service.fetch_texts(fetcher, kinds, args.limit, args.workers, symbol=args.symbol))}"
            )
            if args.extract:
                print(f"LLM extraction: {dict(documents_service.extract(args.limit, kinds))}")
        if args.command == "events":
            first, last = date.fromisoformat(args.first + "-01"), date.fromisoformat(args.last + "-01")
            for name in ("nse_announcements", "nse_board_meetings", "nse_credit_ratings"):
                outcomes += ingest_months(BY_ID[name], first, last, fetcher, reload=args.reload)
        if args.command == "derivatives":
            source = BY_ID["nse_fo_bhav"]
            for day in calendar_days(date.fromisoformat(args.first), date.fromisoformat(args.last)):
                if source.covers(day) and day.weekday() < 5:
                    outcomes.append(ingest_one(source, day, fetcher, reload=args.reload))
        if args.command == "results":
            first, last = date.fromisoformat(args.first + "-01"), date.fromisoformat(args.last + "-01")
            if args.retry_skipped:
                with transaction() as connection:
                    execute(connection, "DELETE FROM results_xbrl_skip")
            for name in ("nse_results_filings", "nse_integrated_filings"):
                outcomes += ingest_months(BY_ID[name], first, last, fetcher, reload=args.reload)
            print(
                "results XBRL: "
                f"{dict(ingest_results_xbrl(fetcher, args.workers, limit=args.limit, index_code=None if args.index == 'all' else args.index, consolidated_first=not args.all_bases))}"
            )
        if args.command == "profiles":
            outcomes.append(ingest_one(BY_ID["nse_brsr_filings"], today, fetcher))
            print(f"BRSR XBRL: {dict(ingest_company_profiles(fetcher, args.workers, limit=args.limit))}")
    except SourceBlocked as blocked:
        # The one failure that is handled rather than raised: what was finished is kept, and
        # the operator needs the reason, not a traceback.
        _report(outcomes, fetcher.requests_made)
        raise SystemExit(f"BLOCKED: {blocked}") from blocked
    finally:
        fetcher.close()
    _report(outcomes, fetcher.requests_made)
    if args.command == "daily":
        summary = signals.run_all(None)
        print(f"engines as of {summary['as_of']}: {summary['signals']} signals, {summary['stances']} stances")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--env", default=os.getenv("EQUITY_ENGINE_ENV", "dev"))
    commands = parser.add_subparsers(dest="command", required=True)
    daily = commands.add_parser("daily")
    prices = commands.add_parser("prices")
    download = commands.add_parser("download")
    for command in (prices, download):
        command.add_argument("--from", dest="first", required=True, help="YYYY-MM-DD")
        command.add_argument("--to", dest="last", required=True, help="YYYY-MM-DD")
        command.add_argument("--workers", type=int, default=1, help="download this many files at once")
        command.add_argument(
            "--interval",
            type=float,
            help="seconds between request starts (default: ingest.min_interval_seconds)",
        )
    snapshots = commands.add_parser("snapshots")
    snapshots.add_argument("--date", help="YYYY-MM-DD; a past date is read from the cache only")
    deals = commands.add_parser("deals")
    ownership = commands.add_parser("ownership")
    for command in (deals, ownership):
        command.add_argument("--from", dest="first", required=True, help="YYYY-MM")
        command.add_argument("--to", dest="last", required=True, help="YYYY-MM")
    documents = commands.add_parser("documents")
    documents.add_argument("--kind", action="append", default=None)
    documents.add_argument("--limit", type=int, default=100)
    documents.add_argument("--workers", type=int, default=2)
    documents.add_argument("--symbol", default=None)
    documents.add_argument("--extract", action="store_true")
    events = commands.add_parser("events")
    events.add_argument("--from", dest="first", required=True, help="YYYY-MM")
    events.add_argument("--to", dest="last", required=True, help="YYYY-MM")
    events.add_argument("--reload", action="store_true")
    derivatives = commands.add_parser("derivatives")
    derivatives.add_argument("--from", dest="first", required=True)
    derivatives.add_argument("--to", dest="last", required=True)
    derivatives.add_argument("--interval", type=float, default=None)
    derivatives.add_argument("--reload", action="store_true")
    results = commands.add_parser("results")
    results.add_argument("--from", dest="first", required=True, help="YYYY-MM")
    results.add_argument("--to", dest="last", required=True, help="YYYY-MM")
    results.add_argument("--workers", type=int, default=1)
    results.add_argument("--interval", type=float, default=None)
    results.add_argument("--limit", type=int, default=None)
    results.add_argument("--reload", action="store_true")
    results.add_argument(
        "--retry-skipped", action="store_true", help="try again the filings a previous run could not load"
    )
    results.add_argument(
        "--index",
        default="nifty500",
        help="constituent list to restrict to (default: the universe, nifty500); 'all' for every company",
    )
    results.add_argument(
        "--all-bases",
        action="store_true",
        help="also fetch standalone filings where a consolidated one exists",
    )
    profiles = commands.add_parser("profiles")
    for command in (ownership, profiles):
        command.add_argument("--workers", type=int, default=1, help="download this many XBRL files at once")
        command.add_argument("--interval", type=float, help="seconds between archive request starts")
        command.add_argument("--limit", type=int, help="read at most this many filings (for a trial run)")
    commands.add_parser("bootstrap", help="create the data schema if it does not exist (never drops)")
    commands.add_parser("migrate", help="apply unapplied schema/migrations/*.sql to the data schema")
    commands.add_parser("membership", help="load Nifty 500 membership history from the reference files")
    prune = commands.add_parser("prune", help="delete rows of companies outside the universe")
    prune.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    commands.add_parser("outcomes", help="mark signal and stance outcomes whose horizon has passed")
    backtest = commands.add_parser("backtest", help="replay the engines over past trade dates")
    backtest.add_argument("--from", dest="first", required=True)
    backtest.add_argument("--to", dest="last", required=True)
    backtest.add_argument("--step", type=int, default=5, help="every Nth trade date")
    backtest.add_argument(
        "--shard",
        default="0/1",
        help="i/n: this process takes every n-th chosen date from i (run n in parallel)",
    )
    backtest.add_argument(
        "--mark", action="store_true", help="mark outcomes when done (run once, after every shard)"
    )
    reports = commands.add_parser("reports", help="re-read cached daily reports bundles for a date range")
    reports.add_argument("--from", dest="first", required=True)
    reports.add_argument("--to", dest="last", required=True)
    retune = commands.add_parser(
        "retune", help="evaluate the stance's engine weights against the backtest ledger"
    )
    retune.add_argument("--horizon", type=int, default=252, choices=(21, 63, 126, 252, 504))
    retune.add_argument(
        "--split",
        default="2025-01-01",
        help="runs before this date trained the weights; the rest are held out",
    )
    signals_cmd = commands.add_parser("signals", help="run every implemented engine and write the ledger")
    signals_cmd.add_argument("--as-of", default=None, help="trade date; default the newest priced date")
    rebuild = commands.add_parser("rebuild")
    commands.add_parser("status")
    for command in (daily, prices, snapshots, rebuild, deals, ownership):
        command.add_argument("--reload", action="store_true", help="parse and load cached files again")
    args = parser.parse_args()
    os.environ["EQUITY_ENGINE_ENV"] = args.env
    run(args)


if __name__ == "__main__":
    main()
