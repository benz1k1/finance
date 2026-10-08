"""The engine catalogue and one engine's page (spec §118, §76)."""

from fastapi import HTTPException
from starlette.requests import Request

from equity_engine.db import transaction
from equity_engine.engines import IMPLEMENTED
from equity_engine.engines.base import STAGES
from equity_engine.pages.engine_examples import EXAMPLES
from equity_engine.pages.templating import templates
from equity_engine.service import signals

SIGNAL_ROWS = 300


def engine_list(request: Request):
    with transaction() as connection:
        run = signals.latest_run(connection)
        catalogue = signals.catalogue(connection, run)
    by_status: dict[str, int] = {}
    for engine in catalogue:
        by_status[engine["status"]] = by_status.get(engine["status"], 0) + 1
        engine["example"] = EXAMPLES.get(engine["engine_key"])
    return templates.TemplateResponse(
        request, "engine_list.html", {"run": run, "engines": catalogue, "by_status": by_status}
    )


def engine_page(request: Request, key: str):
    with transaction() as connection:
        run = signals.latest_run(connection)
        found = next((e for e in signals.catalogue(connection, run) if e["engine_key"] == key), None)
        if found is None:
            raise HTTPException(status_code=404, detail=f"No engine {key}")
        implementation = IMPLEMENTED.get(key)
        context = {
            "run": run,
            "engine": found,
            "example": EXAMPLES.get(key),
            "stages": STAGES,
            "doc": (implementation.__doc__ or "").strip() if implementation else None,
            "signals": signals.engine_signals(connection, run, key, SIGNAL_ROWS)
            if run and found["implemented"]
            else [],
        }
    return templates.TemplateResponse(request, "engine.html", context)
