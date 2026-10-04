"""
Configuration (spec §80).

The env file is nested **YAML**, not dotenv, loaded once at import. Required keys are read
through :func:`_require`, which raises when the key is missing or empty: there is no code
default for any of them and nothing re-reads a configured value from ``os.environ``. The
database password inside ``database.url`` is a Fernet token under ``fernet.key``.

Only genuinely optional *tuning* carries a default: pool size, request pacing, log level.
"""

import os
from pathlib import Path
from typing import Any

from lr_lib.env_yaml import load_yaml_settings_file, nested_get
from lr_lib.fernet_str import try_fernet_decrypt_password
from lr_lib.sqlalchemy_url import url_with_decrypted_password

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_env_file() -> Path:
    explicit = (os.getenv("EQUITY_ENGINE_ENV_YAML") or "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.is_file():
            raise ValueError(f"EQUITY_ENGINE_ENV_YAML file not found: {path}")
        return path
    profile = (os.getenv("EQUITY_ENGINE_ENV") or "").strip()
    if not profile:
        raise ValueError(
            "Neither EQUITY_ENGINE_ENV_YAML nor EQUITY_ENGINE_ENV is set. Export EQUITY_ENGINE_ENV=dev, "
            "or EQUITY_ENGINE_ENV_YAML=/absolute/path/to/.env.yaml."
        )
    path = _REPO_ROOT / "resources" / "env" / profile / ".env.yaml"
    if not path.is_file():
        raise ValueError(
            f"EQUITY_ENGINE_ENV={profile} resolves to {path}, which does not exist. "
            f"Copy resources/env/dev/.env.yaml.example to it."
        )
    return path


ENV_FILE = _resolve_env_file()
SETTINGS: dict[str, Any] = load_yaml_settings_file(ENV_FILE)


def _scalar_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip()


def _require(*keys: str) -> str:
    value = _scalar_str(nested_get(SETTINGS, *keys))
    if not value:
        raise ValueError(f"Missing required config: {'.'.join(keys)}. Set it in {ENV_FILE}.")
    return value


def _opt_str(*keys: str, default: str) -> str:
    return _scalar_str(nested_get(SETTINGS, *keys, default=None)) or default


def _opt_float(*keys: str, default: float) -> float:
    value = _scalar_str(nested_get(SETTINGS, *keys, default=None))
    return float(value) if value else default


def _opt_int(*keys: str, default: int) -> int:
    value = _scalar_str(nested_get(SETTINGS, *keys, default=None))
    return int(value) if value else default


# ------------------------------------------------------------------ required
FERNET_KEY = _require("fernet", "key")

APP_HOST = _require("app", "host")
APP_PORT = int(_require("app", "port"))

DATABASE_URL = url_with_decrypted_password(_require("database", "url"), FERNET_KEY)
DATABASE_SCHEMA = _require("database", "schema")
# The application's own tables (rules, engine registry, signal ledger, stances) live apart from the
# exchange data so they can change without touching it. The name is derived, not configured.
DATABASE_APP_SCHEMA = f"{DATABASE_SCHEMA}_app"

# Bronze. Every downloaded file lives here for good: it is read from disk on every later run,
# never fetched a second time and never deleted by the application.
RAW_DIR = Path(_require("paths", "raw_dir"))
LOG_DIR = Path(_require("paths", "log_dir"))

# The exchanges refuse requests without a browser-like agent; which one is a deployment choice.
INGEST_USER_AGENT = _require("ingest", "user_agent")

# ------------------------------------------------------------------ optional tuning
DATABASE_POOL_SIZE = max(2, _opt_int("database", "pool_size", default=5))
DATABASE_STATEMENT_TIMEOUT_MS = _opt_int("database", "statement_timeout_ms", default=120000)

# Seconds between two requests to the same host. Both exchanges answered "Access Denied" after
# about sixty quick requests (spec §82.1), so this is deliberately slow.
INGEST_MIN_INTERVAL_SECONDS = _opt_float("ingest", "min_interval_seconds", default=3.0)
INGEST_TIMEOUT_SECONDS = _opt_float("ingest", "timeout_seconds", default=45.0)
# A 404 for a trading-day file this recent may only mean "not published yet", so it is not cached.
INGEST_ABSENT_AFTER_DAYS = _opt_int("ingest", "absent_after_days", default=5)

LOG_LEVEL = _opt_str("logging", "level", default="INFO").upper()

# ------------------------------------------------------------------ optional feature: LLM extraction (Phase 3)
# Off unless the YAML says so. When on, the key is required (Fernet token under fernet.key) and
# the model is read from the YAML; nothing here has a code default for a secret.
LLM_ENABLED = _opt_str("llm", "enabled", default="false").lower() == "true"
LLM_API_KEY = try_fernet_decrypt_password(_require("llm", "api_key"), FERNET_KEY) if LLM_ENABLED else ""
LLM_MODEL = _require("llm", "model") if LLM_ENABLED else ""
