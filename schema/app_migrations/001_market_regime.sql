-- One row per engine run: the market regime the run was computed in (spec §29).
CREATE TABLE IF NOT EXISTS market_regime (
    run_id               text PRIMARY KEY REFERENCES engine_run (run_id),
    as_of                date NOT NULL,
    regime               text NOT NULL CHECK (regime IN ('RISK_ON', 'MIXED', 'RISK_OFF', 'UNKNOWN')),
    universe             integer NOT NULL,
    above_200dma_pct     numeric(5, 1),
    median_return_3m_pct numeric(7, 2),
    advancing_1m_pct     numeric(5, 1),
    sectors              jsonb NOT NULL                 -- industry: relative 3m / 6m return, members
);
CREATE INDEX IF NOT EXISTS market_regime_as_of_idx ON market_regime (as_of);
