-- Corporate actions and price-band hits from the daily reports bundle (bc*.csv and bh*.csv),
-- which is already cached for every trade date. Re-ingest with: python ingest.py reports

-- One row per announced action, first seen in the bundle of `first_seen`. The same action is
-- listed in every bundle from announcement to ex-date, so the key is the action, not the day.
CREATE TABLE IF NOT EXISTS corporate_action (
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
CREATE INDEX IF NOT EXISTS corporate_action_ex_idx ON corporate_action (ex_date, kind);
CREATE INDEX IF NOT EXISTS corporate_action_symbol_idx ON corporate_action (symbol, ex_date);

-- A security that closed at its upper (H) or lower (L) price band on the day.
CREATE TABLE IF NOT EXISTS circuit_hit (
    symbol      text NOT NULL,
    series      text NOT NULL,
    trade_date  date NOT NULL,
    side        text NOT NULL CHECK (side IN ('H', 'L')),
    raw_id      text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (symbol, series, trade_date)
);
CREATE INDEX IF NOT EXISTS circuit_hit_date_idx ON circuit_hit (trade_date);
