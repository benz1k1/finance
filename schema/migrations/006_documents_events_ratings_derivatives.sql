-- Announcements (the `document` table, spec §83), the board-meeting / event calendar (§30, §37),
-- credit-rating disclosures (§68) and the daily derivatives position per underlying (§70).

-- One row per exchange announcement. The attachment is a PDF on NSE's archive; `category` is
-- NSE's own subject line, `event_kind` a rule-based reading of it (see parsers/filings.py).
CREATE TABLE IF NOT EXISTS document (
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
CREATE INDEX IF NOT EXISTS document_symbol_idx ON document (symbol, broadcast_at);
CREATE INDEX IF NOT EXISTS document_kind_idx ON document (event_kind, broadcast_at);

-- Scheduled corporate events from the event calendar: board meetings and their purpose.
CREATE TABLE IF NOT EXISTS board_meeting (
    symbol       text NOT NULL,
    meeting_date date NOT NULL,
    purpose      text NOT NULL,
    company_name text NOT NULL,
    description  text NOT NULL,
    raw_id       text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (symbol, meeting_date, purpose)
);
CREATE INDEX IF NOT EXISTS board_meeting_date_idx ON board_meeting (meeting_date);

-- Credit rating actions as disclosed to the exchange.
CREATE TABLE IF NOT EXISTS credit_rating (
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
CREATE INDEX IF NOT EXISTS credit_rating_symbol_idx ON credit_rating (symbol, broadcast_at);

-- One row per underlying per trade date from the F&O bhavcopy: futures open interest across
-- expiries, its change, the near-month basis, and the options put-call ratio by OI.
CREATE TABLE IF NOT EXISTS derivative_oi (
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
CREATE INDEX IF NOT EXISTS derivative_oi_date_idx ON derivative_oi (trade_date);
