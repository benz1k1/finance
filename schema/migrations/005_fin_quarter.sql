-- Canonical line items per results filing (spec §5, §57), derived from fin_fact at load time by
-- service/fundamentals.canonical() so the engines read one narrow row per filing instead of
-- pivoting facts on every run. Rupees. NULL where the taxonomy or the filing has no such item.
-- Quarter columns (q_*) are the reporting quarter; ytd_* the financial year to date; bs_* the
-- balance sheet at period end (only in half-year and annual filings for most companies).
CREATE TABLE IF NOT EXISTS fin_quarter (
    filing_id         text PRIMARY KEY REFERENCES fin_filing (filing_id),
    symbol            text NOT NULL,
    period_end        date NOT NULL,
    consolidated      boolean NOT NULL,
    broadcast_at      timestamptz NOT NULL,
    taxonomy          text NOT NULL,
    is_bank           boolean NOT NULL,            -- BANKING taxonomy: revenue is interest earned, no EBITDA
    is_lender         boolean NOT NULL,            -- NBFC or bank: finance costs are operating, not leverage
    q_revenue         numeric(26, 4),
    q_other_income    numeric(26, 4),
    q_total_income    numeric(26, 4),
    q_expenses        numeric(26, 4),
    q_employee_cost   numeric(26, 4),
    q_material_cost   numeric(26, 4),              -- materials + stock-in-trade + inventory change
    q_finance_costs   numeric(26, 4),
    q_depreciation    numeric(26, 4),
    q_exceptional     numeric(26, 4),
    q_pbt             numeric(26, 4),
    q_tax             numeric(26, 4),
    q_pat             numeric(26, 4),
    q_pat_owners      numeric(26, 4),
    q_eps_basic       numeric(14, 4),
    q_eps_diluted     numeric(14, 4),
    q_interest_earned numeric(26, 4),              -- lenders
    q_interest_expended numeric(26, 4),            -- banks
    q_operating_profit numeric(26, 4),             -- banks: before provisions
    q_provisions      numeric(26, 4),              -- banks
    q_gnpa_pct        numeric(8, 4),               -- banks, as a fraction (0.0373)
    ytd_revenue       numeric(26, 4),
    ytd_pat           numeric(26, 4),
    ytd_cfo           numeric(26, 4),
    ytd_capex         numeric(26, 4),
    ytd_dividends_paid numeric(26, 4),
    ytd_buyback       numeric(26, 4),
    ytd_interest_paid numeric(26, 4),
    bs_equity         numeric(26, 4),
    bs_share_capital  numeric(26, 4),
    bs_borrowings     numeric(26, 4),
    bs_cash           numeric(26, 4),
    bs_total_assets   numeric(26, 4),
    bs_current_assets numeric(26, 4),
    bs_current_liabilities numeric(26, 4),
    bs_inventories    numeric(26, 4),
    bs_receivables    numeric(26, 4),
    bs_deposits       numeric(26, 4),              -- banks
    bs_advances       numeric(26, 4),              -- banks
    face_value        numeric(10, 2),
    raw_id            text NOT NULL REFERENCES raw_file (raw_id)
);
CREATE INDEX IF NOT EXISTS fin_quarter_symbol_idx ON fin_quarter (symbol, period_end, consolidated);
CREATE INDEX IF NOT EXISTS fin_quarter_broadcast_idx ON fin_quarter (broadcast_at);
