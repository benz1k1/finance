-- Phase 3 (spec §83, §32, §33, §56, §71, §117 brands): the text of announcement PDFs and the
-- structured reading of it.
CREATE TABLE IF NOT EXISTS document_text (
    document_id   text PRIMARY KEY REFERENCES document (document_id),
    pages         integer NOT NULL,
    characters    integer NOT NULL,
    text          text NOT NULL,                  -- pypdf text, pages joined with form feeds
    extracted_at  timestamptz NOT NULL DEFAULT now(),
    raw_id        text NOT NULL REFERENCES raw_file (raw_id)
);

-- One structured reading per document, by model and prompt version. Only database-sourced
-- figures are ever shown; the reading is evidence, with page references where the model gives them.
CREATE TABLE IF NOT EXISTS document_extraction (
    document_id    text PRIMARY KEY REFERENCES document (document_id),
    model          text NOT NULL,
    prompt_version text NOT NULL,
    tone           text NOT NULL CHECK (tone IN ('POSITIVE', 'NEUTRAL', 'NEGATIVE', 'MIXED')),
    guidance       jsonb NOT NULL,                -- [{metric, direction, horizon, quote}]
    kpis           jsonb NOT NULL,                -- [{name, value, unit, period, quote}]
    risks          jsonb NOT NULL,                -- [{risk, new_or_changed, quote}]
    brands         jsonb NOT NULL,                -- [{brand, category}]
    summary        text NOT NULL,
    extracted_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS company_brand (
    symbol       text NOT NULL,
    brand        text NOT NULL,
    category     text,
    document_id  text NOT NULL REFERENCES document (document_id),
    PRIMARY KEY (symbol, brand)
);
