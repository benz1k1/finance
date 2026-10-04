# TODO — Equity Engine

Running state of the build. The design is `indian_equity_ai_ml_opportunity_engine_spec.md`;
section numbers (§) refer to it. Phases are the spec's §90 roadmap. Update this file when an
item is finished or a decision changes.

Decisions already taken (spec §82.1, §69.1, §80):

- NSE is the only exchange source. No BSE feed at all (decided 2026-10-01; the BSE scrip list
  was removed the same day). Market cap and shares outstanding come from NSE's daily reports
  bundle.
- History starts in 2019. Results from the Dec-2018 quarter, shareholding from Sep-2021, no
  delisted companies, no paid fundamentals vendor.
- No approver and no maker-checker anywhere.
- Downloaded files are cached under `raw/` for good: never re-downloaded, never deleted.
- Stack: Granian + FastAPI + htmx/Alpine/Tailwind/daisyUI + Postgres, uv, the usual conventions.

## Phase 0 — Foundation

Done (2026-10-01):

- [x] Project scaffold: `start.py` (Granian, port 5018), `load_data.py`, `ingest.py`, env YAML
      with `_require`, Postgres database `equity_engine_dev`, schema `equity_engine`
- [x] Source registry: 20 NSE sources (§82), written to `source_registry`
- [x] Bronze cache (`sources/bronze.py`): disk checked before any request, no overwrite, no
      delete, holiday markers, error pages refused; schema rebuild refills from disk, no network
- [x] Paced HTTP client; a 401/403 stops the run
- [x] Parsers + Pydantic models: UDiFF and legacy bhavcopy, MTO delivery, both masters, price
      bands, bulk/block deals, 8 index lists, ASM/GSM/ESM, market cap from the daily reports bundle
- [x] Loaders (idempotent upserts) and the ingest pipeline, one transaction per file
- [x] Hard exclusions (§69.1): dated NSE rules in `exclusion_rule`, 433 securities excluded today
- [x] Pages: data health, securities (search), security detail, exclusions; JSON API
- [x] Tests: 57 passing (parsers, cache rules, live API, company page, data integrity)
- [x] Parallel download (`ingest.py download --workers N --interval S`); thread-safe pacing
- [x] **Full history loaded (2026-10-01):** 1,923 trade dates, 1 Jan 2019 → 1 Oct 2026, 4.28
      million price rows, delivery on every date, 9 weekend special sessions included. Market cap
      and shares outstanding from 1 Feb 2024 (the first bundle that carries them). Cache is
      2.6 GB / 9,741 files; database 2.7 GB. A full rebuild from cache takes about 30 minutes

Company profile (§117), added 2026-10-01:

- [x] Sources: shareholding filing list (monthly), shareholding XBRL, BRSR filing list, BRSR XBRL,
      bulk and block deal history (monthly CSV). New source kinds `monthly` and `document`
- [x] Parsers and tables: `shareholding_filing`, `shareholding_pattern` (promoter / FII / DII /
      mutual funds / insurance / retail …), `company_profile`, `company_activity`, `company_product`
- [x] Company page: ownership bar + breakdown, ownership by quarter, website, activities, products,
      deals. Ownership screen (`/ownership`), sortable. `/api/ownership|company|deal/{symbol}`
- [ ] **Brands.** Not in any structured filing. Extract from annual-report PDFs (the BRSR filing
      list links them) with the documents pipeline (Phase 3): brand name, page, quoted span
- [x] Loaded 2026-10-01: 2,494 shareholding filings (2,349 companies, FII/DII split on about
      2,150), 1,267 company profiles with website (2,721 products, 1,868 business lines),
      136,881 bulk and block deals from 2019
- [ ] Ownership history: only the filings broadcast Jul–Sep 2026 are loaded. Earlier quarters are
      `python ingest.py ownership --from 2021-10 --to 2026-06 --workers 5 --interval 0.35`
      (about 2,300 XBRL files and ~0.7 GB per quarter). Older filings use an earlier XBRL
      format; expect the FII/DII split to be NULL or the parser to need a second context map
- [ ] Website for companies that file no BRSR (about 1,900 of them): no NSE source found yet
- [ ] Quarter-on-quarter change in FII / DII / promoter holding as a signal (§22–§24)
- [ ] Deal counterparties: normalise client names; repeat-counterparty network (§69.2)

Next, in order:

- [ ] **First live snapshot run.** Today's snapshot files came from the probe downloads, so
      `Fetcher` has not yet fetched an NSE API feed (the session-cookie path used by the three
      surveillance lists). Tomorrow's `python ingest.py daily` is the first real test.
- [ ] Schedule `ingest.py daily` (systemd timer or Celery beat, after ~19:00 IST)
- [ ] Corporate actions: parse the `bc*.csv` member of the daily reports bundle (already
      cached for every trade date; has ex-date and a free-text purpose such as "INT DIV - RS 5
      PER SH", splits, bonuses) into a `corporate_action` table. No API needed.
- [ ] Circuit hits: parse the `bh*.csv` member of the same bundle (price-band hits per day);
      needed by the scam detector (§69.2)
- [ ] Market cap before 1 Feb 2024 is NULL (the bundle has no `mcap*.csv` earlier). Derive it
      from shares outstanding in the shareholding XBRL once ownership history is loaded
- [ ] Adjustment factors computed as of a date (§84); adjusted price series; reconcile against
      the bonus/split dates of 5 known stocks
- [ ] Symbol history: derive `security_symbol_history` from price files (same ISIN, new symbol)
- [ ] Trading calendar table from the price files' dates and the `.absent` markers
- [ ] `AsOf(t)` gateway for prices and universe (§84); leak tests (§89)
- [ ] Index membership history (§82.2): parse `raw/_reference/index_history/` — event workbook
      to Sep-2020, monthly constituent PDFs to 2022, press releases after; find the month the
      monthly zip dropped Nifty 500
- [ ] CSRF middleware (pure ASGI, as in learn_mba) before the first POST route exists
- [ ] Re-fetch policy for corrected files: the cache never re-downloads, so a file NSE republishes
      with corrections is not picked up. Decide whether that matters; if so, add a versioned
      `--refetch` that keeps the old file

## Engines on the UI (spec §118, decided 2026-10-03)

Built 2026-10-03, all five surfaces, for review and trimming:

- [x] **App schema** `equity_engine_app`, separate from the data schema: `exclusion_rule` (moved),
      `engine`, `engine_run`, `signal`, `stance`. `load_data.py` now manages only this schema and
      seeds it from `resources/seed/*.csv`; nothing drops the data schema any more
      (`ingest.py bootstrap` / `migrate` create and change it)
- [x] Engine framework (`engines/`): `Snapshot` + `Signal`, nine engines on the data loaded —
      investability (exclusions, ₹1 cr liquidity floor, ASM warning), manipulation risk, relative
      strength, trend, volume/delivery, institutional accumulation, promoter activity, smart-money
      divergence, bulk/block deal flow. `python ingest.py signals`; `daily` runs it after prices
- [x] Signal ledger (append-only) and the stance ledger, one run per invocation
- [x] Engine catalogue `/engine` with derived status, 54 engines from `engine.csv`; `/engine/{key}`
- [x] Radar `/` (landing), regime strip, opportunity / risk / gate tiles, stance changes between runs
- [x] Signal feed `/signal` with engine / stage / direction / symbol filters
- [x] Screener `/screen`: stance, conviction, has / has-not engine chips, confirmed-only, market
      cap floor, index
- [x] Company stance panel on every security page: stance + conviction, tally bar, strongest for /
      against, "what would change this", all-engines grid with the blocking table named; stance
      column on `/security` and `/ownership`
- [x] **Outcome marking** (§72) — built under Phase 4 below (`signal_outcome` / `stance_outcome`,
      1/3/6/12/24 months, hit rates on every engine page). Invalidation firing is not marked yet
- [x] **Stance v2 (2026-10-04):** per-engine weights on top of stage × strength, derived from the
      backtest at the 12-month horizon on runs before 2025 and held out on 2025–2026
      (`python ingest.py retune` reprints the table and both evaluations). Held out: long stances
      50.8% → 54.2% hit, +5.5% → +11.3% mean excess; short 52.9% → 55.5%. Weights 0 for
      capital_allocation / corporate_event / cash_flow_inflection longs and credit_distress shorts
      (its DISTRESS gate still applies), 1.5 for turnaround and profitability_inflection longs and
      deleveraging / supply_overhang / insider_deal_flow / manipulation_risk shorts, 0.5 for the
      price-trend and most quarterly-change longs. Live run re-emitted at v2 the same day
- [ ] Stance v1 had no hit-rate edge in the backtest (382 runs, 2019–2026, marked 2026-10-03):
      LONG/HIGH 50.0% hit at 12m, +7.0% mean excess; SHORT/MEDIUM 49.9%, *+9.5%* excess (shorts rose
      with the market). Among engines, deleveraging (67% hit, +39% excess, 419 marked) and
      undervalued growth (54%) stand out; capital allocation is inverted (37%, −6%). Caveats: the
      universe for past dates is survivor-biased (prices of dropped members were pruned) which
      inflates long returns and punishes bear engines (distressed names that *stayed* in the index
      recovered by definition), and the ownership engines were absent from these runs. The v2
      weights above were tuned on this ledger, so they inherit the bias. **Decision pending (user):**
      re-ingest the pruned members' prices (`ingest.py rebuild --reload`, market-wide files are
      cached, ~30 min) and re-run the backtest, which reverses part of the 2026-10-03 prune, or
      accept the bias. The ownership engines are now in the ledger for a second backtest either way
- [x] Relative strength and trend use adjusted closes (corporate-action adjustment landed with
      Phase 0's remainder, below)
- [x] Ownership engines cover the universe since the Oct-2021 → Jun-2026 shareholding history
      loaded on 2026-10-03
- [x] `ingest.py daily` runs the engines; scheduled as a user systemd timer (below)
- [ ] Market regime (§29) is computed on the Radar, not an engine; sector rotation (§28) not built

## Engine outputs checked against the data (2026-10-04)

The UI showed the same output on many securities. Some of that is by design (`sector_rotation`
and `investability` are list-level); the rest were defects, fixed the same day and now guarded by
`api/tests/test_engine_outputs.py`, which recomputes a sample of every run's evidence from the raw
tables with plain SQL (prices, documents, `fin_quarter`, `shareholding_pattern`) and checks the
stored stance of every security against `stance.compute`:

- [x] `catalyst` v2: evidence lists the announcements it counted (date, kind, summary); before, 29
      companies shared the identical evidence `{"ACQUISITION": 2}` with nothing to check
- [x] `sector_rotation` v2: a signal only for the members the industry figures were computed from
      (Oil & Gas had 19 signals on 18 members)
- [x] Ownership percentages rounded (`77.25999999999999` was in the ledger); deep value no longer
      prints "EV/EBITDA None"; technical trend says "at its 52-week low" instead of "+0% from"
- [x] Stance colours: long green, short blue, avoid grey (user rule); stance history collapses to
      one entry per as-of date
- [ ] Headlines still coincide where the rounded numbers do ("+4% from 52-week low" on 11 names);
      that is the data, not a defect. The 52-week-low cluster on 1 Oct 2026 (59 of 478) is real:
      53 on 29 Sep, 40 on 28 Sep
- [ ] `promoter_activity` reports event-based shareholding filings (period_end = the event date,
      e.g. `2026-07-30`) as a "quarter"; label it by period_end kind once the filing list says which

## Universe: Nifty 500 (decided 2026-10-03)

- [x] `universe.py` + `in_universe()`; engines, stances, lists, results and document fetch restricted
- [x] Results XBRL download restricted to the universe: 11,798 filings (consolidated first) instead of 101k
- [x] Nifty 500 membership history (`index_membership`, `ingest.py membership`): yearly snapshots
      Apr-2013 → Mar-2022 from the reference PDFs plus the live list; `in_universe_as_of()` picks the
      newest snapshot on or before the run date. Limits: no snapshot for 2023–2025 (NSE's zips carry
      no Nifty 500 file; Mar-2022 is used), 45–81 symbols per year unresolved (renamed since), and
      the prune removed price history of companies no longer in the index, so past members that
      left cannot be priced — the backtest is free of *future-member* bias, not of *dropped-member*
      bias. Re-ingesting their prices (`ingest.py rebuild`, market-wide files are cached) would fix it
- [x] Shareholding XBRL ingestion restricted to the universe; ownership history Oct-2021 → Jun-2026
      loaded 2026-10-03 (8,800 XBRL files). The pre-2025 layout (`OneD`/`OneI` header, contexts
      without `_Context`, percentages not fractions, institutions unsplit) is parsed too: FII is
      taken as FPI + foreign venture capital, DII as the rest of institutions (`parsers/filings.py`)
- [x] Full backtest 2019-01 → 2026-09 every 5th trade date: 382 runs in 6 parallel shards
      (`ingest.py backtest --shard i/n`), ~8 minutes; outcomes marked after
- [x] Daily run installed as a user systemd timer, Mon–Fri 19:45 IST (`resources/systemd/`)

## Phases 1–6 — built 2026-10-03 in one pass ("implement all the phases"), for review

Everything below exists and runs; coverage grows as the background downloads finish. Items
marked ⏳ depend on data still downloading or on a credential this machine does not have.

Phase 0 remainder
- [x] Corporate actions (`corporate_action`, kind + dividend amount + bonus/split factor parsed from
      the bundle's purpose text) and band hits (`circuit_hit`) from the cached daily bundles,
      1,923 dates. Adjusted closes in the engine snapshot (§84); `ingest.py reports` re-reads
- [ ] Symbol history, trading calendar table, index membership history (§82.2) — not started

Phase 1 — fundamentals
- [x] Sources `nse_results_filings` (to Dec-2024) + `nse_integrated_filings` (from Mar-2025, one
      page per month) + `nse_results_xbrl`; `fin_filing`, `fin_fact` (generic facts), `fin_quarter`
      (canonical per taxonomy: INDAS / CAPMKT / NBFC / BANKING / NONINDAS)
- [x] 19 fundamentals engines (§6–§17, §19, §34, §58 reaction, §59, §60, §68, §104, §14)
- [x] Financial results card + `/api/financials/{symbol}` on the company page
- [x] Results XBRL for the universe loaded 2026-10-03: 23,890 quarters, 495 companies, Dec-2017 →
      Jun-2026; 84 files answer 404 on NSE's archive. NSE's archive host tolerated 30 workers at
      ~11 files/s with no refusal (useful for the daily job). Banks' balance-sheet
      mapping and NBFC borrowings are first guesses — reconcile 5 known companies (§89)
- [ ] Q4 balancing (§57) is not needed (NSE files Q4 directly) but revisions are not yet diffed
- [ ] Segment facts (dimensional contexts) are skipped; §18 SOTP needs them

Phase 2 — breadth and risk
- [x] Scam detector rules incl. serial upper circuits; liquidity floor; sector rotation; market
      regime (`market_regime` table, shown on the Radar); IPO / lock-in; supply overhang
- [x] Credit ratings (`credit_rating`) + rating-action engine; board meetings → catalyst engine
- ⏳ Insider trades and pledge: NSE answers only per symbol (`per_symbol` sources registered, no
      fetch loop yet — ~2,500 requests per pass at 3 s each)
- [ ] SEBI orders source

Phase 3 — documents
- [x] `document` (announcements, rule-classified), company timeline page (§31),
      `document_text` from PDFs (pypdf), `document_extraction` via Claude structured outputs,
      engines: management commentary, narrative vs numbers, operating KPI, document diff
- ⏳ LLM extraction needs `llm.enabled: true` + `llm.api_key` (Fernet) in the env YAML; this
      machine has no Anthropic credential, so extraction is untested end to end
- ⏳ Brands: extracted into `company_brand` by the same pass from annual reports

Phase 4 — history and backtest
- [x] `signal_outcome` / `stance_outcome` marking at 1/3/6/12/24 months vs the universe median;
      `ingest.py backtest` replays runs (kind BACKTEST), resumable; outcomes on every engine page
- ⏳ A 12-run validation backtest (Oct-2025 → Sep-2026, step 21) is marked. The full 2019–2026
      backtest should wait until the XBRL backlog has loaded, or fundamentals engines will be
      silent in early runs
- [ ] Known leak: exclusion/ASM lists exist only from Oct-2026; §41 pattern search not built

Phase 5 — ML: not started (needs the backtest ledger first; spec §85 acceptance rule)
Phase 6 — depth
- [x] Derivatives (`derivative_oi` from the F&O bhavcopy, UDiFF era) + §70 engine
- [ ] §18 SOTP, §61–§64, §74 portfolio layer, §75 workbench extras (compare, watchlists, notes)

## Known data quirks (found while building)

- Old price files switch to a two-digit year in their date column from 13-Jul-2020 (`13-Jul-20`).
- NSE trades on some weekends: 9 sessions between 2019 and 2026 (Muhurat trading, budget days,
  disaster-recovery drills). The puller asks for every calendar date, not only weekdays.
- 22-Jun-2019 (a Saturday) has a delivery file and no price file; delivery is never requested
  for a date without prices.
- Companies with no promoter group (3i Infotech, Shiprocket, most banks) file no promoter
  category; `promoter_pct` is NULL for them, 48 filings in the latest quarter.
- Three BRSR filings cannot be loaded: two XBRL links answer 404 and one file is truncated on
  NSE's server (kept in `raw/_quarantine/`; a truncated download is now refused, not cached).
- Long-running download connections went dead once (every request timing out for 8 minutes
  while a fresh connection worked). `Fetcher` now opens a new client after a timeout and stops
  after ten failures in a row.
- The archive host tolerated three jobs at once at a combined ~4 requests/s. The filing-feed
  host served 185 monthly deal files at one request per 3 s without a refusal.

- `sec_bhavdata_full` does not exist for 2019; delivery comes from the MTO files, which do.
- The delivery file has no ISIN; it is matched by symbol + series within the trade date.
- On 2026-09-11 the delivery file's traded quantity is below the price file's volume for 2,862
  securities, so `deliv_pct` is checked against `deliv_traded_qty`, not `volume`.
- Trade-for-trade series (BE, BZ) are absent from the delivery file; their delivery stays NULL.
- About 350 fund units (ETFs, ISIN prefix INF) trade in the EQ series. They are in `price_daily`
  but not in `security`.
- Index files contain placeholder constituents for unlisted demerged entities ("Dummy HEG Ltd.",
  ISIN `DUM…`). They are kept.
- The market-cap file lists securities that did not trade that day (an earlier last-trade date,
  or the text "Not Traded"); those rows are skipped.
- The 2019 daily reports bundle has no market-cap file; member names also changed case over the
  years (`Bc020119.csv` vs `bc01102026.csv`).
- 14 Sep 2026 has no price file (market holiday); it is remembered with an `.absent` marker.
