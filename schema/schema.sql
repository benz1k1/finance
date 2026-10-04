-- Equity Engine — the DATA schema: exchange files parsed into tables. Created once by
-- `python ingest.py bootstrap` (CREATE SCHEMA only when it does not exist — nothing here is ever
-- dropped by a script). Changes after a database exists go in schema/migrations/NNN_name.sql,
-- applied by `python ingest.py migrate`.
--
-- Application tables (rules, engines, the signal ledger, stances) are a separate schema,
-- schema/app_schema.sql, managed by load_data.py, so they can change without touching this one.

CREATE SCHEMA equity_engine;
SET search_path = equity_engine, public;

CREATE TABLE schema_migration (
    name        text PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------ sources and bronze

-- One row per source (spec §82): written by load_data.py from sources/registry.py.
CREATE TABLE source_registry (
    source_id        text PRIMARY KEY,
    name             text    NOT NULL,
    kind             text    NOT NULL CHECK (kind IN ('daily', 'snapshot', 'monthly', 'document', 'per_symbol')),
    host_group       text    NOT NULL,
    url_template     text    NOT NULL,
    parser           text    NOT NULL,
    owner            text    NOT NULL,
    licence          text    NOT NULL,
    cadence          text    NOT NULL,
    staleness_hours  integer NOT NULL,
    first_date       date,
    last_date        date
);

-- One row per cached file. The file on disk is the truth; this row is its index entry and is
-- rebuilt from disk whenever the schema is recreated.
CREATE TABLE raw_file (
    raw_id        text PRIMARY KEY,
    source_id     text        NOT NULL REFERENCES source_registry (source_id),
    logical_date  date        NOT NULL,
    path          text        NOT NULL,
    sha256        text        NOT NULL,
    size_bytes    bigint      NOT NULL,
    fetched_at    timestamptz NOT NULL,
    UNIQUE (path)
);
CREATE INDEX raw_file_source_idx ON raw_file (source_id, logical_date);

-- One row per (source, date) attempt outcome. OK and NO_DATA rows are what a later run skips.
CREATE TABLE ingest_run (
    run_id        text PRIMARY KEY,
    source_id     text        NOT NULL REFERENCES source_registry (source_id),
    logical_date  date        NOT NULL,
    raw_id        text REFERENCES raw_file (raw_id),
    status        text        NOT NULL CHECK (status IN ('OK', 'NO_DATA')),
    rows_parsed   integer     NOT NULL,
    rows_loaded   integer     NOT NULL,
    finished_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id, logical_date)
);

-- ------------------------------------------------------------------ master

-- Identity is the ISIN. The NSE symbol is a current attribute, not a key: symbols get renamed.
CREATE TABLE security (
    isin           text PRIMARY KEY,
    nse_symbol     text    NOT NULL,
    name           text    NOT NULL,
    series         text    NOT NULL,
    segment        text    NOT NULL CHECK (segment IN ('MAIN', 'SME')),
    listing_date   date,
    face_value     numeric(12, 2),
    paid_up_value  numeric(12, 2),
    master_date    date    NOT NULL,   -- the snapshot this row was last seen in
    raw_id         text    NOT NULL REFERENCES raw_file (raw_id)
);
CREATE INDEX security_symbol_idx ON security (nse_symbol);

-- ------------------------------------------------------------------ prices

-- One row per ISIN per trade date per series. Prices are raw (unadjusted); adjustment is
-- computed from corporate actions as of a date, never stored (spec §84).
CREATE TABLE price_daily (
    isin             text           NOT NULL,
    trade_date       date           NOT NULL,
    series           text           NOT NULL,
    symbol           text           NOT NULL,   -- the symbol on that day
    open             numeric(14, 4) NOT NULL,
    high             numeric(14, 4) NOT NULL,
    low              numeric(14, 4) NOT NULL,
    close            numeric(14, 4) NOT NULL,
    last             numeric(14, 4) NOT NULL,
    prev_close       numeric(14, 4) NOT NULL,
    volume           bigint         NOT NULL,
    turnover         numeric(20, 2) NOT NULL,   -- rupees
    trades           integer        NOT NULL,
    -- Filled from the delivery file. deliv_pct is the exchange's own figure and is relative to
    -- deliv_traded_qty, which is NOT always `volume`: on 2026-09-11 (the session before the
    -- 14-Sep market holiday) the delivery file reports a smaller traded quantity than the price
    -- file for 2,862 securities.
    deliv_traded_qty bigint,
    deliv_qty        bigint,
    deliv_pct        numeric(6, 2),
    -- Filled from the daily reports bundle; NULL for dates before NSE published the file.
    issue_size       bigint,                    -- shares outstanding
    market_cap       numeric(22, 2),            -- rupees
    raw_id           text           NOT NULL REFERENCES raw_file (raw_id),
    delivery_raw_id  text REFERENCES raw_file (raw_id),
    reports_raw_id   text REFERENCES raw_file (raw_id),
    PRIMARY KEY (isin, trade_date, series)
);
CREATE INDEX price_daily_date_idx ON price_daily (trade_date);
CREATE INDEX price_daily_symbol_idx ON price_daily (symbol, trade_date);

-- ------------------------------------------------------------------ current-only files, snapshotted daily
-- NSE publishes these with no history (spec §82.1), so each day's copy is kept.

CREATE TABLE series_band_snapshot (
    snapshot_date  date NOT NULL,
    symbol         text NOT NULL,
    series         text NOT NULL,
    band           text NOT NULL,   -- '2' | '5' | '10' | '20' | '40' | 'No Band'
    remarks        text NOT NULL,
    raw_id         text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (snapshot_date, symbol, series)
);

CREATE TABLE surveillance_snapshot (
    snapshot_date  date NOT NULL,
    list_code      text NOT NULL CHECK (list_code IN ('ASM_LT', 'ASM_ST', 'GSM', 'ESM')),
    isin           text NOT NULL,
    symbol         text NOT NULL,
    company_name   text NOT NULL,
    stage          text NOT NULL,
    surv_code      text NOT NULL,
    surv_desc      text NOT NULL,
    raw_id         text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (snapshot_date, list_code, isin)
);

CREATE TABLE index_constituent_snapshot (
    snapshot_date  date NOT NULL,
    index_code     text NOT NULL,
    isin           text NOT NULL,
    symbol         text NOT NULL,
    company_name   text NOT NULL,
    industry       text NOT NULL,
    raw_id         text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (snapshot_date, index_code, isin)
);

-- Bulk and block deals. `seq` is the row's position among that date's rows in the file: two
-- identical deals on one day are legitimate, so no natural key exists.
CREATE TABLE deal (
    kind           text           NOT NULL CHECK (kind IN ('BULK', 'BLOCK')),
    deal_date      date           NOT NULL,
    seq            integer        NOT NULL,
    symbol         text           NOT NULL,
    security_name  text           NOT NULL,
    client_name    text           NOT NULL,
    side           text           NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity       bigint         NOT NULL,
    price          numeric(14, 4) NOT NULL,
    remarks        text           NOT NULL,
    raw_id         text           NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (kind, deal_date, seq)
);
CREATE INDEX deal_symbol_idx ON deal (symbol, deal_date);
CREATE INDEX deal_client_idx ON deal (client_name);

-- ------------------------------------------------------------------ ownership (spec §117)

-- One row per shareholding-pattern filing, from NSE's filing list. A company can file more than
-- once for a quarter (revisions); every filing is kept and `broadcast_at` says when the market
-- could know it.
CREATE TABLE shareholding_filing (
    record_id      text PRIMARY KEY,           -- NSE's id for the filing
    symbol         text        NOT NULL,
    isin           text,
    company_name   text        NOT NULL,
    period_end     date        NOT NULL,
    promoter_pct   numeric(7, 4),
    public_pct     numeric(7, 4),
    broadcast_at   timestamptz NOT NULL,
    revised        boolean     NOT NULL,
    xbrl_url       text,                       -- NULL when the filing has no XBRL
    raw_id         text        NOT NULL REFERENCES raw_file (raw_id)
);
CREATE INDEX shareholding_filing_symbol_idx ON shareholding_filing (symbol, period_end);

-- The category breakdown read from a filing's XBRL. Percentages are of total shares, 0–100.
-- A category the filing's format does not report is NULL, never 0.
CREATE TABLE shareholding_pattern (
    record_id            text PRIMARY KEY REFERENCES shareholding_filing (record_id),
    symbol               text   NOT NULL,   -- from the filing list (NSE-assigned), the join key
    period_end           date   NOT NULL,
    total_shares         bigint NOT NULL,
    total_shareholders   integer NOT NULL,
    promoter_pct         numeric(7, 4),            -- NULL: the company has no promoter group
    public_pct           numeric(7, 4) NOT NULL,
    fii_pct              numeric(7, 4),   -- foreign institutions in total
    fpi_pct              numeric(7, 4),   -- of which foreign portfolio investors (categories I + II)
    dii_pct              numeric(7, 4),   -- domestic institutions in total
    mutual_fund_pct      numeric(7, 4),
    insurance_pct        numeric(7, 4),
    pension_fund_pct     numeric(7, 4),
    aif_pct              numeric(7, 4),
    bank_pct             numeric(7, 4),
    government_pct       numeric(7, 4),
    retail_pct           numeric(7, 4),   -- resident individuals, nominal capital up to Rs 2 lakh
    hni_pct              numeric(7, 4),   -- resident individuals above Rs 2 lakh
    nri_pct              numeric(7, 4),
    bodies_corporate_pct numeric(7, 4),
    raw_id               text   NOT NULL REFERENCES raw_file (raw_id)
);
CREATE INDEX shareholding_pattern_symbol_idx ON shareholding_pattern (symbol, period_end);

-- ------------------------------------------------------------------ company profile (spec §117)

-- From the Business Responsibility and Sustainability Report XBRL, which the largest listed
-- companies must file each year. One row per company per financial year.
CREATE TABLE company_profile (
    symbol              text    NOT NULL,
    fy_to               integer NOT NULL,      -- the year the financial year ends in
    company_name        text    NOT NULL,
    cin                 text,
    incorporated_on     date,
    website             text,
    email               text,
    registered_address  text,
    states_served       integer,
    countries_served    integer,
    employees           integer,
    workers             integer,
    turnover            numeric(22, 2),        -- rupees
    net_worth           numeric(22, 2),
    annual_report_url   text,
    submitted_on        date    NOT NULL,
    raw_id              text    NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (symbol, fy_to)
);

-- "Business activities accounting for 90 per cent of turnover" and "products/services sold", as filed.
CREATE TABLE company_activity (
    symbol        text    NOT NULL,
    fy_to         integer NOT NULL,
    seq           integer NOT NULL,
    main_activity text    NOT NULL,
    description   text    NOT NULL,
    turnover_pct  numeric(7, 4),
    PRIMARY KEY (symbol, fy_to, seq),
    FOREIGN KEY (symbol, fy_to) REFERENCES company_profile (symbol, fy_to) ON DELETE CASCADE
);

CREATE TABLE company_product (
    symbol        text    NOT NULL,
    fy_to         integer NOT NULL,
    seq           integer NOT NULL,
    product       text    NOT NULL,
    nic_code      text,
    turnover_pct  numeric(7, 4),
    PRIMARY KEY (symbol, fy_to, seq),
    FOREIGN KEY (symbol, fy_to) REFERENCES company_profile (symbol, fy_to) ON DELETE CASCADE
);

-- ------------------------------------------------------------------ corporate actions and band hits

-- One row per announced action, first seen in the bundle of `first_seen`. The same action is
-- listed in every bundle from announcement to ex-date, so the key is the action, not the day.
CREATE TABLE corporate_action (
    symbol         text NOT NULL,
    series         text NOT NULL,
    ex_date        date NOT NULL,
    purpose        text NOT NULL,                  -- as printed, e.g. "BONUS 1:1", "FVSPLT FRM RS 10 TO RE 1"
    security_name  text NOT NULL,
    record_date    date,
    bc_start       date,
    bc_end         date,
    nd_start       date,
    nd_end         date,
    kind           text NOT NULL CHECK (kind IN ('DIVIDEND', 'BONUS', 'SPLIT', 'CONSOLIDATION', 'RIGHTS',
                                                 'BUYBACK', 'DEMERGER', 'MERGER', 'MEETING', 'OTHER')),
    amount         numeric(14, 4),                 -- dividend per share when the text gives one
    adjust_factor  numeric(14, 8),                 -- old shares / new shares for bonus, split, consolidation
    first_seen     date NOT NULL,
    last_seen      date NOT NULL,
    raw_id         text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (symbol, series, ex_date, purpose)
);
CREATE INDEX corporate_action_ex_idx ON corporate_action (ex_date, kind);
CREATE INDEX corporate_action_symbol_idx ON corporate_action (symbol, ex_date);

-- A security that closed at its upper (H) or lower (L) price band on the day.
CREATE TABLE circuit_hit (
    symbol      text NOT NULL,
    series      text NOT NULL,
    trade_date  date NOT NULL,
    side        text NOT NULL CHECK (side IN ('H', 'L')),
    raw_id      text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (symbol, series, trade_date)
);
CREATE INDEX circuit_hit_date_idx ON circuit_hit (trade_date);

-- ------------------------------------------------------------------ financial results (spec §5, §84)

CREATE TABLE fin_filing (
    filing_id      text PRIMARY KEY,              -- feed prefix + NSE sequence number
    feed           text NOT NULL CHECK (feed IN ('RESULTS', 'INTEGRATED')),
    symbol         text NOT NULL,
    isin           text,
    company_name   text NOT NULL,
    period_end     date NOT NULL,
    period_start   date,                          -- NULL on the integrated feed, which gives only the quarter end
    consolidated   boolean NOT NULL,
    audited        boolean NOT NULL,
    bank           text NOT NULL CHECK (bank IN ('N', 'B', 'F', '?')),   -- company / bank / NBFC / not stated
    broadcast_at   timestamptz NOT NULL,          -- when the market could know it (point in time)
    revised        boolean NOT NULL,
    xbrl_url       text,
    raw_id         text NOT NULL REFERENCES raw_file (raw_id)
);
CREATE INDEX fin_filing_symbol_idx ON fin_filing (symbol, period_end, consolidated);
CREATE INDEX fin_filing_broadcast_idx ON fin_filing (broadcast_at);

CREATE TABLE fin_fact (
    filing_id    text NOT NULL REFERENCES fin_filing (filing_id),
    item         text NOT NULL,                   -- the XBRL element's local name, as filed
    period_kind  text NOT NULL CHECK (period_kind IN ('Q', 'YTD', 'INSTANT')),
    value        numeric(26, 4) NOT NULL,
    unit         text NOT NULL,                   -- INR, INRPerShare, pure, shares
    taxonomy     text NOT NULL,                   -- INDAS, NBFC, BANKING, NONINDAS, CAPMKT
    raw_id       text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (filing_id, item, period_kind)
);

-- Canonical line items per results filing (spec §5, §57), derived from fin_fact at load time by
-- service/fundamentals.canonical() so the engines read one narrow row per filing instead of
-- pivoting facts on every run. Rupees. NULL where the taxonomy or the filing has no such item.
-- Quarter columns (q_*) are the reporting quarter; ytd_* the financial year to date; bs_* the
-- balance sheet at period end (only in half-year and annual filings for most companies).
CREATE TABLE fin_quarter (
    filing_id         text PRIMARY KEY REFERENCES fin_filing (filing_id),
    symbol            text NOT NULL,
    period_end        date NOT NULL,
    consolidated      boolean NOT NULL,
    broadcast_at      timestamptz NOT NULL,
    taxonomy          text NOT NULL,
    is_bank           boolean NOT NULL,            -- BANKING taxonomy: revenue is interest earned, no EBITDA
    is_lender         boolean NOT NULL,            -- NBFC or bank: finance costs are operating, not leverage
    q_revenue         numeric(26, 4),
    q_other_income    numeric(26, 4),
    q_total_income    numeric(26, 4),
    q_expenses        numeric(26, 4),
    q_employee_cost   numeric(26, 4),
    q_material_cost   numeric(26, 4),              -- materials + stock-in-trade + inventory change
    q_finance_costs   numeric(26, 4),
    q_depreciation    numeric(26, 4),
    q_exceptional     numeric(26, 4),
    q_pbt             numeric(26, 4),
    q_tax             numeric(26, 4),
    q_pat             numeric(26, 4),
    q_pat_owners      numeric(26, 4),
    q_eps_basic       numeric(14, 4),
    q_eps_diluted     numeric(14, 4),
    q_interest_earned numeric(26, 4),              -- lenders
    q_interest_expended numeric(26, 4),            -- banks
    q_operating_profit numeric(26, 4),             -- banks: before provisions
    q_provisions      numeric(26, 4),              -- banks
    q_gnpa_pct        numeric(8, 4),               -- banks, as a fraction (0.0373)
    ytd_revenue       numeric(26, 4),
    ytd_pat           numeric(26, 4),
    ytd_cfo           numeric(26, 4),
    ytd_capex         numeric(26, 4),
    ytd_dividends_paid numeric(26, 4),
    ytd_buyback       numeric(26, 4),
    ytd_interest_paid numeric(26, 4),
    bs_equity         numeric(26, 4),
    bs_share_capital  numeric(26, 4),
    bs_borrowings     numeric(26, 4),
    bs_cash           numeric(26, 4),
    bs_total_assets   numeric(26, 4),
    bs_current_assets numeric(26, 4),
    bs_current_liabilities numeric(26, 4),
    bs_inventories    numeric(26, 4),
    bs_receivables    numeric(26, 4),
    bs_deposits       numeric(26, 4),              -- banks
    bs_advances       numeric(26, 4),              -- banks
    face_value        numeric(10, 2),
    raw_id            text NOT NULL REFERENCES raw_file (raw_id)
);
CREATE INDEX fin_quarter_symbol_idx ON fin_quarter (symbol, period_end, consolidated);
CREATE INDEX fin_quarter_broadcast_idx ON fin_quarter (broadcast_at);

-- ------------------------------------------------------------------ documents, events, ratings, derivatives

-- One row per exchange announcement. The attachment is a PDF on NSE's archive; `category` is
-- NSE's own subject line, `event_kind` a rule-based reading of it (see parsers/filings.py).
CREATE TABLE document (
    document_id    text PRIMARY KEY,              -- NSE seq_id
    symbol         text NOT NULL,
    isin           text,
    company_name   text NOT NULL,
    broadcast_at   timestamptz NOT NULL,
    category       text NOT NULL,                 -- NSE "desc", e.g. "Acquisition", "Press Release"
    event_kind     text NOT NULL,                 -- RESULTS, BOARD_MEETING, ACQUISITION, ORDER_WIN, FUND_RAISE, BUYBACK,
                                                  -- DIVIDEND, RATING, PLEDGE, INSIDER, INVESTOR_MEET, PRESS_RELEASE,
                                                  -- REGULATORY, GOVERNANCE, OTHER
    summary        text NOT NULL,                 -- NSE's one-line text
    attachment_url text,
    attachment_kb  numeric(10, 2),
    has_xbrl       boolean NOT NULL,
    industry       text,
    raw_id         text NOT NULL REFERENCES raw_file (raw_id)
);
CREATE INDEX document_symbol_idx ON document (symbol, broadcast_at);
CREATE INDEX document_kind_idx ON document (event_kind, broadcast_at);

-- Scheduled corporate events from the event calendar: board meetings and their purpose.
CREATE TABLE board_meeting (
    symbol       text NOT NULL,
    meeting_date date NOT NULL,
    purpose      text NOT NULL,
    company_name text NOT NULL,
    description  text NOT NULL,
    raw_id       text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (symbol, meeting_date, purpose)
);
CREATE INDEX board_meeting_date_idx ON board_meeting (meeting_date);

-- Credit rating actions as disclosed to the exchange.
CREATE TABLE credit_rating (
    rating_id      text PRIMARY KEY,              -- NSE AppID
    symbol         text,                          -- NULL / 'NA' for unlisted issuers
    isin           text,
    company_name   text NOT NULL,
    agency         text NOT NULL,
    rating         text NOT NULL,
    outlook        text,
    action         text NOT NULL,                 -- Reaffirm, Upgrade, Downgrade, Assigned, Withdrawn ...
    rating_earlier text,
    rated_on       date,
    broadcast_at   timestamptz NOT NULL,
    raw_id         text NOT NULL REFERENCES raw_file (raw_id)
);
CREATE INDEX credit_rating_symbol_idx ON credit_rating (symbol, broadcast_at);

-- One row per underlying per trade date from the F&O bhavcopy: futures open interest across
-- expiries, its change, the near-month basis, and the options put-call ratio by OI.
CREATE TABLE derivative_oi (
    symbol             text NOT NULL,
    trade_date         date NOT NULL,
    futures_oi         bigint NOT NULL,
    futures_oi_change  bigint NOT NULL,
    futures_volume     bigint NOT NULL,
    near_expiry        date,
    near_close         numeric(14, 4),
    underlying_close   numeric(14, 4),
    basis_pct          numeric(8, 4),             -- near future over underlying, percent
    call_oi            bigint NOT NULL,
    put_oi             bigint NOT NULL,
    pcr_oi             numeric(8, 4),
    raw_id             text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (symbol, trade_date)
);
CREATE INDEX derivative_oi_date_idx ON derivative_oi (trade_date);

-- Filings whose XBRL could not be loaded in a run (not cached offline, malformed, empty), so a
-- batch loop moves past them. Cleared by `python ingest.py results --retry-skipped`.
CREATE UNLOGGED TABLE results_xbrl_skip (
    filing_id  text PRIMARY KEY,
    reason     text NOT NULL,
    noted_at   timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------ document text and extraction (Phase 3)
CREATE TABLE document_text (
    document_id   text PRIMARY KEY REFERENCES document (document_id),
    pages         integer NOT NULL,
    characters    integer NOT NULL,
    text          text NOT NULL,                  -- pypdf text, pages joined with form feeds
    extracted_at  timestamptz NOT NULL DEFAULT now(),
    raw_id        text NOT NULL REFERENCES raw_file (raw_id)
);

-- One structured reading per document, by model and prompt version. Only database-sourced
-- figures are ever shown; the reading is evidence, with page references where the model gives them.
CREATE TABLE document_extraction (
    document_id    text PRIMARY KEY REFERENCES document (document_id),
    model          text NOT NULL,
    prompt_version text NOT NULL,
    tone           text NOT NULL CHECK (tone IN ('POSITIVE', 'NEUTRAL', 'NEGATIVE', 'MIXED')),
    guidance       jsonb NOT NULL,                -- [{metric, direction, horizon, quote}]
    kpis           jsonb NOT NULL,                -- [{name, value, unit, period, quote}]
    risks          jsonb NOT NULL,                -- [{risk, new_or_changed, quote}]
    brands         jsonb NOT NULL,                -- [{brand, category}]
    summary        text NOT NULL,
    extracted_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE company_brand (
    symbol       text NOT NULL,
    brand        text NOT NULL,
    category     text,
    document_id  text NOT NULL REFERENCES document (document_id),
    PRIMARY KEY (symbol, brand)
);

-- ------------------------------------------------------------------ raw_file foreign-key indexes
CREATE INDEX price_daily_raw_idx ON price_daily (raw_id);
CREATE INDEX price_daily_delivery_raw_idx ON price_daily (delivery_raw_id);
CREATE INDEX price_daily_reports_raw_idx ON price_daily (reports_raw_id);
CREATE INDEX deal_raw_idx ON deal (raw_id);
CREATE INDEX document_raw_idx ON document (raw_id);
CREATE INDEX fin_fact_raw_idx ON fin_fact (raw_id);
CREATE INDEX fin_filing_raw_idx ON fin_filing (raw_id);
CREATE INDEX fin_quarter_raw_idx ON fin_quarter (raw_id);
CREATE INDEX circuit_hit_raw_idx ON circuit_hit (raw_id);
CREATE INDEX corporate_action_raw_idx ON corporate_action (raw_id);
CREATE INDEX board_meeting_raw_idx ON board_meeting (raw_id);
CREATE INDEX credit_rating_raw_idx ON credit_rating (raw_id);
CREATE INDEX derivative_oi_raw_idx ON derivative_oi (raw_id);
CREATE INDEX shareholding_filing_raw_idx ON shareholding_filing (raw_id);
CREATE INDEX shareholding_pattern_raw_idx ON shareholding_pattern (raw_id);
CREATE INDEX raw_file_path_idx ON raw_file (path);

-- ------------------------------------------------------------------ index membership history (spec §82.2)
CREATE TABLE index_membership (
    index_code  text NOT NULL,
    as_of       date NOT NULL,
    symbol      text NOT NULL,                 -- as printed at the time
    isin        text,                          -- resolved through the master; NULL when the symbol is gone
    source      text NOT NULL,                 -- file the snapshot was read from
    PRIMARY KEY (index_code, as_of, symbol)
);
CREATE INDEX index_membership_isin_idx ON index_membership (index_code, isin, as_of);

-- Rules (exclusion_rule) and everything the engines write live in the app schema:
-- schema/app_schema.sql. This file holds exchange data only and is never dropped by load_data.py.
