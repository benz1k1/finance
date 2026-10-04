"""
Shared fixtures. The HTTP tests drive the app already running on 127.0.0.1:5018 over httpx —
never FastAPI's TestClient, which bypasses the server and its middleware. An unmet precondition
is a ``pytest.fail``, never a skip.
"""

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

os.environ.setdefault("EQUITY_ENGINE_ENV", "dev")
_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from equity_engine.config import APP_PORT  # noqa: E402
from equity_engine.db import transaction  # noqa: E402

BASE_URL = f"http://127.0.0.1:{APP_PORT}"
FIXTURES = Path(__file__).with_name("fixtures")


@pytest.fixture(scope="session")
def client() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=BASE_URL, timeout=30, follow_redirects=False) as session:
        try:
            session.get("/api/health")
        except httpx.ConnectError:
            pytest.fail(f"The app is not running on {BASE_URL}. Start it: python start.py")
        yield session


@pytest.fixture()
def connection():
    with transaction() as open_connection:
        yield open_connection


@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIXTURES
