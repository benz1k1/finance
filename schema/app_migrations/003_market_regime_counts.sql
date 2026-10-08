-- The breadth figures as counts, not only percentages, so the Radar can show above, below and the
-- short-history remainder of the same universe (the percentage's denominator is the securities
-- with at least 200 sessions of history, which the old label mis-stated as the whole universe).
ALTER TABLE market_regime ADD COLUMN IF NOT EXISTS with_200dma   integer;
ALTER TABLE market_regime ADD COLUMN IF NOT EXISTS above_200dma  integer;
ALTER TABLE market_regime ADD COLUMN IF NOT EXISTS advancing_1m  integer;
