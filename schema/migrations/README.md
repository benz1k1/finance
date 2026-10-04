Changes to the **data** schema (`equity_engine`) after it exists go here as `NNN_name.sql`,
applied in order by `python ingest.py migrate` and recorded in `equity_engine.schema_migration`.
Fold each one into `../schema.sql` as well, so a fresh `ingest.py bootstrap` needs no migrations.
App-schema changes go in `../app_migrations/` (applied by `load_data.py`).
