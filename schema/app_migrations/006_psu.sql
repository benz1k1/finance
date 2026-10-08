-- Government ownership tags, seeded from resources/seed/psu.csv (the filings name promoters only as
-- "promoter", so a PSU parent such as ONGC is invisible there). DPE categories: Maharatna,
-- Navratna, Miniratna I/II; banks and insurers are tagged by sector; state PSUs and PSU-promoted
-- joint ventures are kept apart because the government does not control the latter.
CREATE TABLE IF NOT EXISTS psu (
    symbol    text PRIMARY KEY,
    name      text NOT NULL,
    owner     text NOT NULL CHECK (owner IN ('central', 'state', 'psu-promoted')),
    category  text NOT NULL,
    parent    text,
    note      text
);
