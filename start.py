#!/usr/bin/env python3
"""
Start the Equity Engine locally.

    python start.py                # granian --reload on 5018 (127.0.0.1)
    python start.py --load-data    # create and seed the app schema first (never the data schema)
    python start.py --no-reload
    python start.py --stop         # stop whatever is on the port
    python start.py --port 5019

Port 5018 is chosen against the workspace map (learn_mba 5016, learn_togaf / oraceuticmd 5014,
loylty_program 5012, clowreed 5000, ten_tail 5002, rocket 5006, media_box 5007, MOS 5008).

Ingestion is not started here; it is a separate command (`python ingest.py daily`).
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
API_DIR = REPO_ROOT / "api"
VENV_PYTHON = API_DIR / ".venv" / "bin" / "python"
LOG_DIR = REPO_ROOT / "logs"
DEFAULT_PORT = 5018


def _python() -> str:
    if not VENV_PYTHON.is_file():
        raise SystemExit(f"No venv at {VENV_PYTHON}. Run: cd api && uv sync")
    return str(VENV_PYTHON)


def _environment(profile: str) -> dict[str, str]:
    environment = dict(os.environ)
    environment["EQUITY_ENGINE_ENV"] = profile
    src = str(API_DIR / "src")
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = f"{src}:{existing}" if existing else src
    return environment


def _pids_on_port(port: int) -> list[int]:
    result = subprocess.run(["lsof", "-t", f"-i:{port}"], capture_output=True, text=True)
    return [int(line) for line in result.stdout.split() if line.strip().isdigit()]


def stop(port: int, wait_seconds: int = 15) -> None:
    for pid in _pids_on_port(port):
        print(f"  killing pid {pid} on port {port}")
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.time() + wait_seconds
    while time.time() < deadline and _pids_on_port(port):
        time.sleep(0.5)
    for pid in _pids_on_port(port):
        os.kill(pid, signal.SIGKILL)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--env",
        default="dev",
        help="EQUITY_ENGINE_ENV profile (resources/env/<profile>/.env.yaml)",
    )
    parser.add_argument(
        "--load-data",
        action="store_true",
        help="create/seed the app schema (rules, engines) first; the data schema is never touched",
    )
    parser.add_argument("--no-reload", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()

    if args.stop:
        stop(args.port)
        return

    environment = _environment(args.env)
    LOG_DIR.mkdir(exist_ok=True)
    if args.load_data:
        subprocess.run(
            [_python(), str(REPO_ROOT / "load_data.py"), "--env", args.env],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
        )
    if _pids_on_port(args.port):
        print(f"port {args.port} is busy; stopping the previous server")
        stop(args.port)
    # Granian (Rust ASGI server). PYTHONPATH already points at api/src via _environment().
    command = [
        _python(),
        "-m",
        "granian",
        "--interface",
        "asgi",
        "equity_engine.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if not args.no_reload:
        # Watches every file under src, so Jinja template edits reload too.
        command += ["--reload", "--reload-paths", str(API_DIR / "src")]
    print(f"Equity Engine on http://{args.host}:{args.port}")
    try:
        subprocess.run(command, cwd=API_DIR, env=environment, check=False)
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
