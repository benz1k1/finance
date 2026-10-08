-- Public metadata about deal counterparties, looked up once online (Wikipedia) and cached: what the
-- entity is, in its own words, with the source. Never overwritten by a later lookup; a row with
-- found = false records that the search was done and nothing relevant exists.
CREATE TABLE IF NOT EXISTS client_meta (
    client_name   text PRIMARY KEY,
    found         boolean NOT NULL,
    title         text,
    description   text,                 -- Wikipedia's short description, e.g. "Central bank of Norway"
    extract       text,                 -- the lead paragraph
    url           text,
    source        text NOT NULL,        -- 'wikipedia'
    query         text NOT NULL,        -- the search string used
    looked_up_at  timestamptz NOT NULL DEFAULT now()
);
