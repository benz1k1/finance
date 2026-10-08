#!/usr/bin/env python3
"""
Create and seed the APP schema — rules, the engine catalogue, the signal ledger, stances.

    python load_data.py                    # create what is missing, apply app migrations, seed CSVs
    python load_data.py --seed-only        # reload resources/seed/*.csv into the app tables only
    python load_data.py --drop-app         # DROP the app schema first (loses the signal ledger —
                                           # asks for confirmation; the data schema is untouched)
    python load_data.py --ensure-role      # once: create the app role and database (needs
                                           # EQUITY_ENGINE_ADMIN_DB_URL, a superuser URL)

This script never reads, drops or writes the DATA schema (exchange files parsed into tables).
That schema is created by `python ingest.py bootstrap`, migrated by `python ingest.py migrate` and
filled by `python ingest.py rebuild`. The one exception is a one-time adoption: an `exclusion_rule`
table still sitting in the data schema (from before the split) is MOVED into the app schema with
ALTER TABLE ... SET SCHEMA, so no rows are lost.

Seeds are the usual CSV files under resources/seed/: `engine.csv` (the catalogue, spec §118) and
`exclusion_rule.csv` (spec §69.1). Seeding is an upsert, so it is safe to repeat.

Imports of the application package are inside the functions on purpose — the one place in the
repo where that is allowed: EQUITY_ENGINE_ENV has to be set from ``--env`` *before* ``config``
is imported, because config reads its YAML at import and fails fast.
"""

import argparse
import csv
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = REPO_ROOT / "api" / ".venv" / "bin" / "python"
APP_SCHEMA_FILE = REPO_ROOT / "schema" / "app_schema.sql"
APP_MIGRATIONS_DIR = REPO_ROOT / "schema" / "app_migrations"
SEED_DIR = REPO_ROOT / "resources" / "seed"

if Path(sys.executable) != VENV_PYTHON:
    if not VENV_PYTHON.is_file():
        raise SystemExit(f"No venv at {VENV_PYTHON}. Run: cd api && uv sync")
    os.execv(
        VENV_PYTHON, [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]]
    )
sys.path.insert(0, str(REPO_ROOT / "api" / "src"))


def ensure_role() -> None:
    """Create the non-superuser app role and its database from a superuser connection."""
    from equity_engine.config import DATABASE_URL
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine.url import make_url

    admin_url = (os.getenv("EQUITY_ENGINE_ADMIN_DB_URL") or "").strip()
    if not admin_url:
        raise SystemExit(
            "EQUITY_ENGINE_ADMIN_DB_URL (a superuser URL) is required for --ensure-role"
        )
    app = make_url(DATABASE_URL)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        if not connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": app.username}
        ).first():
            # CREATE ROLE takes no bind parameters; the password is quoted as a literal.
            password = str(app.password).replace("'", "''")
            connection.exec_driver_sql(
                f"CREATE ROLE \"{app.username}\" LOGIN PASSWORD '{password}'"
            )
            print(f"  created role {app.username}")
        if not connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": app.database}
        ).first():
            connection.exec_driver_sql(
                f'CREATE DATABASE "{app.database}" OWNER "{app.username}"'
            )
            print(f"  created database {app.database}")
    print("  role and database ready")


def drop_app() -> None:
    from equity_engine.config import DATABASE_APP_SCHEMA
    from equity_engine.db import engine
    from sqlalchemy import text

    answer = input(
        f"DROP SCHEMA {DATABASE_APP_SCHEMA} — the signal ledger is lost. Type the schema name to confirm: "
    )
    if answer.strip() != DATABASE_APP_SCHEMA:
        raise SystemExit("not confirmed; nothing dropped")
    with engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {DATABASE_APP_SCHEMA} CASCADE"))
    print(f"  dropped {DATABASE_APP_SCHEMA}")


def ensure_app_schema() -> None:
    """Create the app schema and every table that is missing; adopt a pre-split exclusion_rule."""
    from equity_engine.config import DATABASE_APP_SCHEMA, DATABASE_SCHEMA
    from equity_engine.db import engine
    from sqlalchemy import text

    sql = APP_SCHEMA_FILE.read_text(encoding="utf-8").replace(
        "__APP_SCHEMA__", DATABASE_APP_SCHEMA
    )
    with engine.begin() as connection:
        fresh = not connection.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = :s"),
            {"s": DATABASE_APP_SCHEMA},
        ).first()
        legacy_rules = connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = :s AND table_name = 'exclusion_rule'"
            ),
            {"s": DATABASE_SCHEMA},
        ).first()
        if legacy_rules:
            connection.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {DATABASE_APP_SCHEMA}")
            )
            connection.execute(
                text(
                    f"ALTER TABLE {DATABASE_SCHEMA}.exclusion_rule SET SCHEMA {DATABASE_APP_SCHEMA}"
                )
            )
            print(
                f"  moved exclusion_rule from {DATABASE_SCHEMA} to {DATABASE_APP_SCHEMA} (rows kept)"
            )
        connection.exec_driver_sql(sql)
        if fresh:
            # A fresh schema already contains every migration's effect; record them as applied.
            for path in sorted(APP_MIGRATIONS_DIR.glob("*.sql")):
                connection.execute(
                    text(
                        "INSERT INTO schema_migration (name) VALUES (:n) ON CONFLICT DO NOTHING"
                    ),
                    {"n": path.name},
                )
    print(f"  app schema {DATABASE_APP_SCHEMA} {'created' if fresh else 'present'}")


def migrate_app() -> None:
    from equity_engine.config import DATABASE_APP_SCHEMA
    from equity_engine.db import engine
    from sqlalchemy import text

    applied_count = 0
    with engine.begin() as connection:
        connection.execute(
            text(f"SET LOCAL search_path = {DATABASE_APP_SCHEMA}, public")
        )
        applied = {
            found[0]
            for found in connection.execute(text("SELECT name FROM schema_migration"))
        }
        for path in sorted(APP_MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            connection.exec_driver_sql(path.read_text(encoding="utf-8"))
            connection.execute(
                text("INSERT INTO schema_migration (name) VALUES (:n)"),
                {"n": path.name},
            )
            print(f"  applied {path.name}")
            applied_count += 1
    print(f"  {applied_count} app migration(s) applied")


def _csv_rows(name: str) -> list[dict[str, str]]:
    with open(SEED_DIR / name, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def seed() -> None:
    from equity_engine.db import execute_many, transaction
    from equity_engine.engines import IMPLEMENTED
    from equity_engine.ids import new_id

    rules = [line | {"rule_id": new_id()} for line in _csv_rows("exclusion_rule.csv")]
    engines = [
        line | {"requires": [table for table in line["requires"].split("|") if table]}
        for line in _csv_rows("engine.csv")
    ]
    keys = {line["engine_key"] for line in engines}
    orphans = sorted(set(IMPLEMENTED) - keys)
    if orphans:
        raise SystemExit(
            f"engines implemented in code but missing from engine.csv: {orphans}"
        )
    with transaction() as connection:
        execute_many(
            connection,
            """
            INSERT INTO exclusion_rule (rule_id, kind, value, reason, valid_from)
            VALUES (:rule_id, :kind, :value, :reason, CAST(:valid_from AS date))
            ON CONFLICT (kind, value, valid_from) DO UPDATE SET reason = EXCLUDED.reason
            """,
            rules,
        )
        execute_many(
            connection,
            """
            INSERT INTO engine (engine_key, name, spec_section, phase, "group", radar, requires, description)
            VALUES (:engine_key, :name, :spec_section, CAST(:phase AS smallint), :group, :radar, :requires, :description)
            ON CONFLICT (engine_key) DO UPDATE SET
                name = EXCLUDED.name, spec_section = EXCLUDED.spec_section, phase = EXCLUDED.phase,
                "group" = EXCLUDED."group", radar = EXCLUDED.radar, requires = EXCLUDED.requires,
                description = EXCLUDED.description
            """,
            engines,
        )
        psus = [
            line | {"parent": line["parent"] or None, "note": line["note"] or None}
            for line in _csv_rows("psu.csv")
        ]
        execute_many(
            connection,
            """
            INSERT INTO psu (symbol, name, owner, category, parent, note)
            VALUES (:symbol, :name, :owner, :category, :parent, :note)
            ON CONFLICT (symbol) DO UPDATE SET name = EXCLUDED.name, owner = EXCLUDED.owner,
                category = EXCLUDED.category, parent = EXCLUDED.parent, note = EXCLUDED.note
            """,
            psus,
        )
    print(
        f"  seeded {len(engines)} engines ({len(IMPLEMENTED)} implemented), {len(rules)} exclusion rules "
        f"and {len(psus)} government-ownership tags"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Equity Engine app schema + seed (never the data schema)"
    )
    parser.add_argument("--env", default=os.getenv("EQUITY_ENGINE_ENV", "dev"))
    parser.add_argument("--seed-only", action="store_true")
    parser.add_argument("--drop-app", action="store_true")
    parser.add_argument("--ensure-role", action="store_true")
    args = parser.parse_args()
    os.environ["EQUITY_ENGINE_ENV"] = args.env

    if args.ensure_role:
        ensure_role()
        return
    if args.drop_app:
        drop_app()
    if not args.seed_only:
        ensure_app_schema()
        migrate_app()
    seed()
    print("done")


if __name__ == "__main__":
    main()
