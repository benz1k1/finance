"""
The DATA schema's lifecycle: create it when it does not exist, migrate it, seed the source
registry. Nothing here drops anything. The app schema is load_data.py's business, not this
module's — the two are kept apart so application tables can change without touching exchange data.
"""

from dataclasses import asdict
from pathlib import Path

from sqlalchemy import text

from equity_engine.config import DATABASE_SCHEMA
from equity_engine.db import engine, execute_many, transaction
from equity_engine.sources.registry import SOURCES

_REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_FILE = _REPO_ROOT / "schema" / "schema.sql"
MIGRATIONS_DIR = _REPO_ROOT / "schema" / "migrations"


def ensure_data_schema() -> None:
    """CREATE the data schema from schema/schema.sql only when it is absent; then seed the registry."""
    with engine.begin() as connection:
        present = connection.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = :s"), {"s": DATABASE_SCHEMA}
        ).first()
        if present:
            print(
                f"  data schema {DATABASE_SCHEMA} already exists; nothing created (use `migrate` for changes)"
            )
        else:
            connection.exec_driver_sql(SCHEMA_FILE.read_text(encoding="utf-8"))
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                connection.execute(text("INSERT INTO schema_migration (name) VALUES (:n)"), {"n": path.name})
            print(f"  data schema {DATABASE_SCHEMA} created from {SCHEMA_FILE.name}")
    seed_source_registry()


def migrate_data() -> None:
    applied_count = 0
    with engine.begin() as connection:
        connection.execute(text(f"SET LOCAL search_path = {DATABASE_SCHEMA}, public"))
        applied = {found[0] for found in connection.execute(text("SELECT name FROM schema_migration"))}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            connection.exec_driver_sql(path.read_text(encoding="utf-8"))
            connection.execute(text("INSERT INTO schema_migration (name) VALUES (:n)"), {"n": path.name})
            print(f"  applied {path.name}")
            applied_count += 1
    print(f"  {applied_count} data migration(s) applied")


def seed_source_registry() -> None:
    """source_registry mirrors sources/registry.py; an upsert, safe to repeat."""
    registry = []
    for source in SOURCES:
        fields = asdict(source)
        fields.pop("magic")
        fields.pop("filename_template")
        registry.append(fields)
    with transaction() as connection:
        execute_many(
            connection,
            """
            INSERT INTO source_registry (source_id, name, kind, host_group, url_template, parser, owner,
                                         licence, cadence, staleness_hours, first_date, last_date)
            VALUES (:source_id, :name, :kind, :host_group, :url_template, :parser, :owner,
                    :licence, :cadence, :staleness_hours, :first_date, :last_date)
            ON CONFLICT (source_id) DO UPDATE SET
                name = EXCLUDED.name, kind = EXCLUDED.kind, host_group = EXCLUDED.host_group,
                url_template = EXCLUDED.url_template, parser = EXCLUDED.parser, owner = EXCLUDED.owner,
                licence = EXCLUDED.licence, cadence = EXCLUDED.cadence,
                staleness_hours = EXCLUDED.staleness_hours, first_date = EXCLUDED.first_date,
                last_date = EXCLUDED.last_date
            """,
            registry,
        )
    print(f"  source registry: {len(registry)} sources")
