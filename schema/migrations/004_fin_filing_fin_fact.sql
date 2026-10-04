-- Financial results (spec §5, §84): the filing list from NSE's two results feeds and every
-- numeric fact in the XBRL behind each filing. Facts are stored as filed (long format), in
-- rupees; canonical line items are derived in code (service/fundamentals.py), not stored.

CREATE TABLE IF NOT EXISTS fin_filing (
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
CREATE INDEX IF NOT EXISTS fin_filing_symbol_idx ON fin_filing (symbol, period_end, consolidated);
CREATE INDEX IF NOT EXISTS fin_filing_broadcast_idx ON fin_filing (broadcast_at);

CREATE TABLE IF NOT EXISTS fin_fact (
    filing_id    text NOT NULL REFERENCES fin_filing (filing_id),
    item         text NOT NULL,                   -- the XBRL element's local name, as filed
    period_kind  text NOT NULL CHECK (period_kind IN ('Q', 'YTD', 'INSTANT')),
    value        numeric(26, 4) NOT NULL,
    unit         text NOT NULL,                   -- INR, INRPerShare, pure, shares
    taxonomy     text NOT NULL,                   -- INDAS, NBFC, BANKING, NONINDAS, CAPMKT
    raw_id       text NOT NULL REFERENCES raw_file (raw_id),
    PRIMARY KEY (filing_id, item, period_kind)
);
