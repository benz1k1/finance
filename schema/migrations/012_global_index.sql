-- Global equity index closes (spec §120), the only non-NSE price data in the project: five
-- headline indexes (US, Japan, Germany, Euro area, China), index levels only, no foreign stocks.
-- Source: Yahoo Finance's chart endpoint, cached under raw/_reference/global_index/ one file per
-- index per fetch day.
CREATE TABLE IF NOT EXISTS global_index_daily (
    index_code  text NOT NULL,            -- SPX, N225, DAX, STOXX50, SSEC
    trade_date  date NOT NULL,
    close       numeric(14, 4) NOT NULL,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (index_code, trade_date)
);
