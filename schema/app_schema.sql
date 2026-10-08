-- Equity Engine — the APP schema: rules, the engine registry, the signal ledger and stances.
-- Separate from the data schema (schema.sql) so the application can change its own tables
-- without touching exchange data. Managed by `python load_data.py`, which creates what is missing
-- (every statement is IF NOT EXISTS), applies schema/app_migrations/, and seeds from
-- resources/seed/*.csv. Nothing in the data schema is ever read-modified by that script.
--
-- The schema name is derived: <database.schema>_app (config.DATABASE_APP_SCHEMA). load_data.py
-- substitutes it for __APP_SCHEMA__ before executing this file.

CREATE SCHEMA IF NOT EXISTS __APP_SCHEMA__;
SET search_path = __APP_SCHEMA__, public;

CREATE TABLE IF NOT EXISTS schema_migration (
    name        text PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------ rules

-- Hard exclusions (spec §69.1). Dated, so a backtest applies the list in force on each date.
-- Seeded from resources/seed/exclusion_rule.csv.
CREATE TABLE IF NOT EXISTS exclusion_rule (
    rule_id     text PRIMARY KEY,
    kind        text NOT NULL CHECK (kind IN ('NSE_SERIES', 'NSE_SURVEILLANCE')),
    value       text NOT NULL,
    reason      text NOT NULL,
    valid_from  date NOT NULL,
    valid_to    date,
    UNIQUE (kind, value, valid_from)
);

-- ------------------------------------------------------------------ engines (spec §85, §118)

-- The engine catalogue: one row per engine in the spec, seeded from resources/seed/engine.csv.
-- `requires` names the data tables the engine needs; the catalogue page derives the engine's
-- status from whether those tables hold rows and whether an implementation is registered in
-- code (equity_engine.engines.IMPLEMENTED).
CREATE TABLE IF NOT EXISTS engine (
    engine_key   text PRIMARY KEY,                -- snake_case, the code's registry key
    name         text NOT NULL,
    spec_section text NOT NULL,                   -- "6", "69.2"
    phase        smallint NOT NULL,               -- spec §90 roadmap phase, 0–6
    "group"      text NOT NULL CHECK ("group" IN ('FUNDAMENTALS', 'VALUATION', 'OWNERSHIP_FLOWS',
                                                  'PRICE', 'EVENTS_DOCUMENTS', 'RISK_GATES', 'FRAMEWORK')),
    radar        text NOT NULL CHECK (radar IN ('OPPORTUNITY', 'RISK', 'GATE', 'NONE')),
    requires     text[] NOT NULL,                 -- data tables; empty for framework entries
    description  text NOT NULL
);

-- One row per evaluation of the whole engine set as of a date. Re-running the same date adds
-- a run; readers take the newest run per as_of. Nothing is edited or deleted (§72).
CREATE TABLE IF NOT EXISTS engine_run (
    run_id       text PRIMARY KEY,
    as_of        date NOT NULL,
    started_at   timestamptz NOT NULL,
    finished_at  timestamptz,
    engines      text[] NOT NULL,                 -- engine keys evaluated, with versions: key@version
    signals      integer,
    stances      integer,
    kind         text NOT NULL DEFAULT 'LIVE' CHECK (kind IN ('LIVE', 'BACKTEST'))
);
CREATE INDEX IF NOT EXISTS engine_run_as_of_idx ON engine_run (as_of, started_at);

-- The signal ledger (§72): append-only. One row per (run, engine, security) that fired.
CREATE TABLE IF NOT EXISTS signal (
    signal_id      text PRIMARY KEY,
    run_id         text NOT NULL REFERENCES engine_run (run_id),
    as_of          date NOT NULL,
    isin           text NOT NULL,
    symbol         text NOT NULL,
    engine_key     text NOT NULL REFERENCES engine (engine_key),
    engine_version text NOT NULL,
    signal_type    text NOT NULL,                 -- engine-specific label, e.g. RS_LEADER
    direction      text NOT NULL CHECK (direction IN ('BULL', 'BEAR', 'GATE')),
    stage          text NOT NULL CHECK (stage IN ('EARLY', 'EMERGING', 'CONFIRMED', 'MATURE', 'REVERSING')),
    strength       numeric(6, 4) NOT NULL,        -- 0–1
    percentile     numeric(6, 2),                 -- how unusual, against the universe/history (0–100)
    headline       text NOT NULL,                 -- the one-line fact that fired it
    evidence       jsonb NOT NULL,                -- the measured values, keyed
    invalidation   text NOT NULL,                 -- what would end it
    price_at       numeric(14, 4),                -- close on as_of, for outcome marking
    emitted_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS signal_run_idx ON signal (run_id, engine_key);
CREATE INDEX IF NOT EXISTS signal_isin_idx ON signal (isin, as_of);
CREATE INDEX IF NOT EXISTS signal_as_of_idx ON signal (as_of, engine_key, stage);

-- The company stance (§118): a versioned, deterministic summary of that run's signals for one
-- security. Written for every security in the universe on every run, not only those with signals.
CREATE TABLE IF NOT EXISTS stance (
    stance_id    text PRIMARY KEY,
    run_id       text NOT NULL REFERENCES engine_run (run_id),
    as_of        date NOT NULL,
    isin         text NOT NULL,
    symbol       text NOT NULL,
    stance       text NOT NULL CHECK (stance IN ('LONG', 'LEAN_LONG', 'NEUTRAL', 'LEAN_SHORT', 'SHORT', 'AVOID')),
    conviction   text NOT NULL CHECK (conviction IN ('NONE', 'LOW', 'MEDIUM', 'HIGH')),
    version      text NOT NULL,
    bull_score   numeric(8, 4) NOT NULL,
    bear_score   numeric(8, 4) NOT NULL,
    bull_count   smallint NOT NULL,
    bear_count   smallint NOT NULL,
    gate         text,                            -- the gate's headline when stance = AVOID
    inputs       jsonb NOT NULL,                  -- signal ids and their weights
    price_at     numeric(14, 4)
);
CREATE INDEX IF NOT EXISTS stance_run_idx ON stance (run_id, stance, conviction);
CREATE INDEX IF NOT EXISTS stance_isin_idx ON stance (isin, as_of);

-- One row per engine run: the market regime the run was computed in (spec §29).
CREATE TABLE IF NOT EXISTS market_regime (
    run_id               text PRIMARY KEY REFERENCES engine_run (run_id),
    as_of                date NOT NULL,
    regime               text NOT NULL CHECK (regime IN ('RISK_ON', 'MIXED', 'RISK_OFF', 'UNKNOWN')),
    universe             integer NOT NULL,
    above_200dma_pct     numeric(5, 1),
    median_return_3m_pct numeric(7, 2),
    advancing_1m_pct     numeric(5, 1),
    with_200dma          integer,                      -- securities with >= 200 sessions: the pct's denominator
    above_200dma         integer,
    advancing_1m         integer,
    global_3m_pct        numeric(7, 2),                 -- median 3-month return of the five global indexes
    global_stress        boolean,                       -- the world is in a drawdown (spec §120)
    global_indexes       jsonb,                         -- per index: last close, 1m / 3m returns, above 200-day
    sectors              jsonb NOT NULL                 -- industry: relative 3m / 6m return, members
);
CREATE INDEX IF NOT EXISTS market_regime_as_of_idx ON market_regime (as_of);

-- ------------------------------------------------------------------ outcomes (spec §72)
-- Each signal and stance is marked at fixed horizons after its as-of date once prices for that
-- horizon exist: absolute return, excess return over the priced universe's median return for the
-- same window, maximum drawdown inside the window. Append-only; a (signal, horizon) is marked once.
CREATE TABLE IF NOT EXISTS signal_outcome (
    signal_id        text NOT NULL REFERENCES signal (signal_id),
    horizon_days     smallint NOT NULL CHECK (horizon_days IN (21, 63, 126, 252, 504)),
    as_of            date NOT NULL,
    end_date         date NOT NULL,
    price_at         numeric(14, 4) NOT NULL,
    price_end        numeric(14, 4) NOT NULL,
    return_pct       numeric(10, 4) NOT NULL,
    excess_pct       numeric(10, 4) NOT NULL,
    max_drawdown_pct numeric(10, 4) NOT NULL,
    marked_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (signal_id, horizon_days)
);
CREATE INDEX IF NOT EXISTS signal_outcome_horizon_idx ON signal_outcome (horizon_days);

CREATE TABLE IF NOT EXISTS stance_outcome (
    stance_id        text NOT NULL REFERENCES stance (stance_id),
    horizon_days     smallint NOT NULL CHECK (horizon_days IN (21, 63, 126, 252, 504)),
    as_of            date NOT NULL,
    end_date         date NOT NULL,
    return_pct       numeric(10, 4) NOT NULL,
    excess_pct       numeric(10, 4) NOT NULL,
    max_drawdown_pct numeric(10, 4) NOT NULL,
    marked_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (stance_id, horizon_days)
);

-- ------------------------------------------------------------------ deal counterparties (spec §65)
-- Public metadata looked up once online and cached; found = false records a search with no result.
CREATE TABLE IF NOT EXISTS client_meta (
    client_name   text PRIMARY KEY,
    found         boolean NOT NULL,
    title         text,
    description   text,
    extract       text,
    url           text,
    source        text NOT NULL,
    query         text NOT NULL,
    looked_up_at  timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------ government ownership (seeded from psu.csv)
CREATE TABLE IF NOT EXISTS psu (
    symbol    text PRIMARY KEY,
    name      text NOT NULL,
    owner     text NOT NULL CHECK (owner IN ('central', 'state', 'psu-promoted')),
    category  text NOT NULL,
    parent    text,
    note      text
);
