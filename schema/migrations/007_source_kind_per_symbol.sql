-- A fifth source kind: feeds that answer only for one symbol at a time (insider trades, pledge).
ALTER TABLE source_registry DROP CONSTRAINT IF EXISTS source_registry_kind_check;
ALTER TABLE source_registry ADD CONSTRAINT source_registry_kind_check
    CHECK (kind IN ('daily', 'snapshot', 'monthly', 'document', 'per_symbol'));
