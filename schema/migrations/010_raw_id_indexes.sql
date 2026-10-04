-- Indexes on the raw_file foreign keys. Without them a DELETE FROM raw_file scans every
-- referencing table per row (the one-time prune of 2026-10-03 timed out on exactly this).
CREATE INDEX IF NOT EXISTS price_daily_raw_idx ON price_daily (raw_id);
CREATE INDEX IF NOT EXISTS price_daily_delivery_raw_idx ON price_daily (delivery_raw_id);
CREATE INDEX IF NOT EXISTS price_daily_reports_raw_idx ON price_daily (reports_raw_id);
CREATE INDEX IF NOT EXISTS deal_raw_idx ON deal (raw_id);
CREATE INDEX IF NOT EXISTS document_raw_idx ON document (raw_id);
CREATE INDEX IF NOT EXISTS fin_fact_raw_idx ON fin_fact (raw_id);
CREATE INDEX IF NOT EXISTS fin_filing_raw_idx ON fin_filing (raw_id);
CREATE INDEX IF NOT EXISTS fin_quarter_raw_idx ON fin_quarter (raw_id);
CREATE INDEX IF NOT EXISTS circuit_hit_raw_idx ON circuit_hit (raw_id);
CREATE INDEX IF NOT EXISTS corporate_action_raw_idx ON corporate_action (raw_id);
CREATE INDEX IF NOT EXISTS board_meeting_raw_idx ON board_meeting (raw_id);
CREATE INDEX IF NOT EXISTS credit_rating_raw_idx ON credit_rating (raw_id);
CREATE INDEX IF NOT EXISTS derivative_oi_raw_idx ON derivative_oi (raw_id);
CREATE INDEX IF NOT EXISTS shareholding_filing_raw_idx ON shareholding_filing (raw_id);
CREATE INDEX IF NOT EXISTS shareholding_pattern_raw_idx ON shareholding_pattern (raw_id);
CREATE INDEX IF NOT EXISTS raw_file_path_idx ON raw_file (path);
