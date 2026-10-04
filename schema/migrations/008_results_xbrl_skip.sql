-- Filings whose XBRL could not be loaded in a run (not cached offline, malformed, empty), so a
-- batch loop moves past them. Cleared by `python ingest.py results --retry-skipped`.
CREATE UNLOGGED TABLE IF NOT EXISTS results_xbrl_skip (
    filing_id  text PRIMARY KEY,
    reason     text NOT NULL,
    noted_at   timestamptz NOT NULL DEFAULT now()
);
