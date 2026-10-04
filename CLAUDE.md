# CLAUDE.md

Equity Engine — Indian equity research and opportunity detection. Single-user tool. Granian +
FastAPI + server-rendered htmx pages, Postgres, no build step.
`indian_equity_ai_ml_opportunity_engine_spec.md` is the design (start at its index; read only the
section a change touches — it is 4,000+ lines) and `TODO.md` is the running state. Update both
when a decision changes. Same shape as `../learn_mba`, with Postgres instead of SQLite.

## Commands

```bash
cd api && uv sync                        # venv at api/.venv; uv only, never pip or poetry
python start.py                          # granian --reload on http://127.0.0.1:5018
python start.py --load-data              # create/seed the APP schema first (never the data schema)
python start.py --stop

python load_data.py                      # app schema: create what is missing, migrate, seed from resources/seed/*.csv
python load_data.py --seed-only          # reload the CSVs (engine catalogue, exclusion rules) only
python load_data.py --drop-app           # drop the app schema (loses the signal ledger; asks to confirm)
python load_data.py --ensure-role        # once; needs EQUITY_ENGINE_ADMIN_DB_URL (superuser URL)

python ingest.py bootstrap               # create the DATA schema if absent (never drops); seeds source_registry
python ingest.py migrate                 # apply schema/migrations/*.sql to the data schema
python ingest.py reports --from 2019-01-01 --to 2026-10-03   # re-read cached daily bundles: corporate actions, band hits
python ingest.py results --from 2019-01 --to 2026-09 --workers 5 --interval 0.35   # universe only; --index all for every company
                                         # results filing lists (both NSE feeds) + XBRL behind each, newest first,
                                         # in batches of 400 so recent quarters are usable at once; resumable
python ingest.py events --from 2019-01 --to 2026-09          # announcements (document), board meetings, credit ratings
python ingest.py derivatives --from 2024-07-06 --to 2026-10-03 --interval 0.5   # F&O bhavcopy -> derivative_oi
python ingest.py documents --kind INVESTOR_MEET --limit 200  # announcement PDFs -> document_text (+ --extract with LLM)
python ingest.py signals                 # run every implemented engine as of the newest trade date -> ledger
python ingest.py outcomes                # mark signals/stances at 1/3/6/12/24 months against the universe median
python ingest.py backtest --from 2019-07-01 --to 2026-09-01 --step 5   # replay engines over history, then mark

python ingest.py daily                   # today's snapshots + last 7 days of prices
python ingest.py prices --from 2026-09-01 --to 2026-09-30
python ingest.py download --from 2019-01-01 --to 2019-12-31 --workers 5 --interval 0.35
                                         # fill the cache only, in parallel; ingest after with `prices`
python ingest.py deals --from 2019-01 --to 2026-09          # bulk/block deals, a month per request
python ingest.py ownership --from 2026-07 --to 2026-09 --workers 5 --interval 0.35
python ingest.py profiles --workers 5 --interval 0.35       # website, activities, products (BRSR)
python ingest.py rebuild                 # ingest everything on disk; no network
python ingest.py retune                  # the stance's engine weights against the backtest ledger (train < 2025, held out after)
python ingest.py status

cd api && uv run ruff check --fix . && uv run ruff format . && uv run mypy src/
cd api && uv run ruff check --config pyproject.toml --fix ../start.py ../load_data.py ../ingest.py
cd api && EQUITY_ENGINE_ENV=dev uv run pytest -q      # needs the app running on 5018
```

`load_data.py` and `ingest.py` re-exec themselves under `api/.venv`, so plain `python` works.

## The cache rule — do not break it

**Every downloaded file is kept under `raw/` for good. Never re-download one, never delete one.** The only time this was overridden was the one-time Nifty 500 clean-up of 2026-10-03 (`ingest.py prune`, run once at the user's instruction); it is not a standing exception.
NSE's filing-feed host answered "Access Denied" after about sixty quick requests (spec §82.1).

**NSE only. No BSE feed of any kind** (decided 2026-10-01): market cap and shares outstanding
come from the `mcap*.csv` member of NSE's daily reports bundle (`nse_daily_reports`).

- `sources/bronze.py` checks the **disk** before any request — not the database. Dropping the
  schema therefore costs no network: `load_data.py` refills from disk.
- `bronze.store` refuses to overwrite and refuses a response that does not start with the
  source's `magic` bytes (so an HTML error page is never cached as data).
- A weekday with no file is a market holiday, remembered as `<file>.absent` once it is more than
  `ingest.absent_after_days` old. Newer than that, a 404 may only mean "not published yet".
- `raw/_reference/` holds files downloaded during research with no parser yet (index history,
  BSE price files, NSE filing-feed samples). Keep them; later phases use them.
- Do not probe the exchanges with ad-hoc `curl` loops. Add a source to `sources/registry.py` and
  fetch through `Fetcher`, which spaces request starts per host (thread-safe, shared by parallel
  workers) and stops the whole run on a 401/403/429. The archive host tolerated 5 workers at
  ~3 requests/s; the filing-feed host (`nseindia.com/api`) did not tolerate ~1/s for long.
- To re-parse after a parser fix use `--reload` or `ingest.py rebuild --reload` — still no download.
- A truncated document is refused at `store_document` (it would otherwise be cached broken for
  good). `raw/_quarantine/` holds one such file from before that check existed.
- The database is fully loaded (1,923 trade dates from 2019) and **no script drops the data
  schema**. `ingest.py bootstrap` only creates it when absent; schema changes go in
  `schema/migrations/` and are applied with `ingest.py migrate`. A full refill from cache
  (`ingest.py rebuild`) takes about 30 minutes.

## The universe is the Nifty 500

Decided 2026-10-03: every engine, stance, list page, results download and document fetch is
restricted to the newest Nifty 500 constituent list (`equity_engine/universe.py`,
`in_universe(...)` is the SQL predicate). Market-wide files (prices, deals, announcements,
bundles) are still ingested whole because they cost nothing extra; `/security?all=1` shows
the rest. Constituent history is not loaded, so backtests see today's list (survivorship leak,
TODO.md). `ingest.py results` defaults to `--index nifty500`; `--index all` widens it.

## Two schemas — data and app

Exchange data (`equity_engine`, `schema/schema.sql`) and the application's own tables
(`equity_engine_app`, `schema/app_schema.sql`: `exclusion_rule`, `engine`, `engine_run`, `signal`,
`stance`) are separate Postgres schemas, so app tables can change without touching the data.
The app schema name is derived, `<database.schema>_app` (`config.DATABASE_APP_SCHEMA`), and both
are on the connection's `search_path`, so SQL names tables unqualified.

- `load_data.py` owns the **app** schema only: every statement in `app_schema.sql` is
  `IF NOT EXISTS`, migrations live in `schema/app_migrations/`, and the seed is the usual CSV
  files in `resources/seed/` (`engine.csv` is the engine catalogue, `exclusion_rule.csv` the hard
  exclusions). It never reads or writes the data schema. One exception, run once: an
  `exclusion_rule` table found in the data schema is *moved* (`ALTER TABLE … SET SCHEMA`), rows kept.
- `ingest.py bootstrap` / `migrate` own the **data** schema and never drop it.
- The signal ledger (`signal`, `stance`, `engine_run`) is append-only (spec §72): re-running
  `ingest.py signals` for the same date adds a run; pages read the newest finished run.

## Data loads that run for hours

`results` (~130k XBRL files), `events` (96 monthly announcement lists of ~15 MB) and `derivatives`
run in the background with `setsid nohup … &` and are **resumable**: every file is cached, every
loader is an upsert, and the XBRL loop skips filings already loaded. Kill by pid (`pgrep -af
ingest.py`), never `pkill -f` from a shell that matches itself. Check progress with
`grep -c "fetched nse_results_xbrl" logs/ingest.log` and `fin_quarter` counts.

## Engines and the signal pages (spec §118)

`engines/` holds the implemented engines (`IMPLEMENTED` in `engines/__init__.py`), each a pure
function of a shared `Snapshot` (`engines/base.py`) that loads price features, ownership, deals,
exclusions and ASM once per run. `service/signals.run_all` evaluates them, writes the ledger and
a `stance` row per security (`service/stance.compute`, versioned — bump `VERSION` when the
weights change). Engine families: `engines/price.py` (RS, trend, volume), `flows.py` (ownership, deals),
`gates.py` (investability, manipulation), `events.py` (corporate actions, IPO, lock-ins),
`market.py` (sector rotation, regime), `fundamentals.py` (19 engines on `fin_quarter`),
`documents.py` (catalyst, governance, rating actions, derivatives), `narrative.py` (document
text and LLM extraction). The catalogue page says which of the 55 are live. Adding one: a class with `key`, `version`, `evaluate(snap)`; add it to
`IMPLEMENTED` and make sure its key is a row in `resources/seed/engine.csv` (`load_data.py`
refuses an implemented engine missing from the CSV).

Pages: `/` Radar (landing; `/health` is the old data-health page), `/signal` feed, `/engine`
catalogue with derived status (LIVE / READY / BLOCKED on named tables / FRAMEWORK),
`/screen` screener, and the stance panel + all-engines grid at the top of every security page.
Stance badges are also a column on `/security` and `/ownership`. JSON: `/api/engine`,
`/api/radar`, `/api/signal`, `/api/stance/{symbol}`, `/api/screen`.

## Layout

```
api/src/equity_engine/
  config.py  db.py  ids.py  main.py
  sources/registry.py   every source: URL template, cache filename, parser key, magic bytes
  sources/bronze.py     the cache        sources/http.py   the paced client
  parsers/models.py     Pydantic records; a bad row fails the whole file, never skipped
  parsers/nse.py bse.py bytes -> records; no I/O, no database
  service/ingest.py     cache -> parse -> load, one transaction per (source, date)
  service/load.py       idempotent upserts        service/health.py securities.py exclusions.py
  service/schema.py     data-schema lifecycle (create if absent, migrate, seed source_registry)
  engines/              base.py (Signal, Snapshot), price.py, flows.py, gates.py; IMPLEMENTED map
  service/signals.py    run the engines, write and read the ledger, radar, feed, screener
  service/stance.py     the versioned stance function (spec §118)
  pages/urls.py         the route table (one list); pages/controller/, templates/, static/
schema/schema.sql       the DATA schema; schema/migrations/ for changes (ingest.py migrate)
schema/app_schema.sql   the APP schema, all IF NOT EXISTS; schema/app_migrations/ (load_data.py)
resources/seed/engine.csv           the engine catalogue, one row per engine in the spec
resources/seed/exclusion_rule.csv   hard exclusions (spec §69.1), dated
```

- Identity is the **ISIN**; the NSE symbol is a current attribute. Prices are stored raw; the
  engines' `Snapshot` adjusts closes for bonus/split factors from `corporate_action` as of the
  run date (spec §84), so stored rows never change.
- Results: `fin_filing` (both feeds) → `fin_fact` (every numeric XBRL fact in the plain contexts
  OneD = quarter, FourD = year-to-date, OneI = balance sheet) → `fin_quarter` (canonical columns
  per filing, mapped per taxonomy in `service/fundamentals.canonical`). Point in time is
  `broadcast_at`. Banks and NBFCs are flagged; EBITDA/ROCE engines skip lenders.
- `document` is the announcement list (rule-classified `event_kind`); `document_text` the PDF
  text for the kinds fetched; `document_extraction` the LLM reading, present only when
  `llm.enabled` is true in the env YAML.
- Delivery and market cap have no ISIN in their files; they are written onto that date's
  `price_daily` rows by symbol + series, so prices must be loaded first. Downloading is
  parallel; parsing and loading stay sequential for that reason.
- Source kinds: `daily`, `snapshot`, `monthly` (a date-range query asked one finished calendar
  month at a time) and `document` (the XBRL behind a filing; URL comes from a listing row).
- Filings are matched to securities by **NSE symbol**: the ISIN inside a filing is typed by the
  company and is sometimes malformed.
- **Do not edit ingestion modules while an `ingest.py` loop is running.** Each step starts a new
  process and picks up half-made changes (this stopped a backfill on 2026-10-01).
- A `daily` source has the date in its filename and is backfillable; a `snapshot` source is a
  current-only file stored under the day it was fetched.
- Adding a source: a `Source` in `registry.py`, a parser, a model, a loader, a row in
  `service/ingest._STEPS`, a table in `schema.sql`, then `python load_data.py`.
- Routes are tuples in `pages/urls.py`, not decorators. REST paths are singular.
- No POST routes yet; add the pure-ASGI CSRF middleware from `learn_mba` with the first one.

## Conventions

- uv only. Imports at module scope, stdlib → third party → local. The two root scripts import
  the package inside functions on purpose (the env must be set before `config` is imported).
- **No fallbacks.** Required config through `config._require()`; no `os.getenv(...) or "<literal>"`.
  `try/except` only at system boundaries.
- Loguru with f-strings, never `%s`. nanoid ids (`ids.new_id`), never uuid4.
- Tests drive the running app over httpx; never `TestClient`; `pytest.fail`, never skip.
- New static or template directories go in both `MANIFEST.in` and `package-data`.
- No approver or maker-checker flows in this product (decided 2026-10-01).
