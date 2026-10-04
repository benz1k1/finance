-- Index membership history (spec §82.2): one row per constituent per dated snapshot. Yearly
-- snapshots to Mar-2022 come from NSE's constituent PDFs in raw/_reference/index_history; the
-- newest comes from the daily constituent file. The universe as of a past date is the newest
-- snapshot on or before it (service/universe), which is what makes backtests survivorship-free
-- to the yearly grain the source allows.
CREATE TABLE IF NOT EXISTS index_membership (
    index_code  text NOT NULL,
    as_of       date NOT NULL,
    symbol      text NOT NULL,                 -- as printed at the time
    isin        text,                          -- resolved through the master; NULL when the symbol is gone
    source      text NOT NULL,                 -- file the snapshot was read from
    PRIMARY KEY (index_code, as_of, symbol)
);
CREATE INDEX IF NOT EXISTS index_membership_isin_idx ON index_membership (index_code, isin, as_of);
