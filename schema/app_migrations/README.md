Changes to the **app** schema (`equity_engine_app`) after it exists go here as `NNN_name.sql`,
applied in order by `python load_data.py` and recorded in `equity_engine_app.schema_migration`.
Fold each one into `../app_schema.sql` as well (every statement there is `IF NOT EXISTS`, so a
fresh database and an existing one converge). Data-schema changes go in `../migrations/`.
