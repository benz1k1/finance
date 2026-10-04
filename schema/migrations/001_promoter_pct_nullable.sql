-- A company with no promoter group files no promoter category; that is NULL, not a failed row.
ALTER TABLE shareholding_pattern ALTER COLUMN promoter_pct DROP NOT NULL;
