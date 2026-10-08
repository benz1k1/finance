-- Global context on each regime row (spec §120): per-index returns and whether the world is in a
-- drawdown, so Indian weakness can be read against it.
ALTER TABLE market_regime ADD COLUMN IF NOT EXISTS global_3m_pct  numeric(7, 2);
ALTER TABLE market_regime ADD COLUMN IF NOT EXISTS global_stress  boolean;
ALTER TABLE market_regime ADD COLUMN IF NOT EXISTS global_indexes jsonb;
