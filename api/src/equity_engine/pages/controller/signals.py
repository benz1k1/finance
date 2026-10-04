"""Radar (the landing page), the signal feed and the screener (spec §44, §72, §75, §118)."""

from typing import Annotated, Any

from fastapi import HTTPException, Query
from starlette.requests import Request

from equity_engine.db import transaction
from equity_engine.engines.base import STAGES
from equity_engine.pages.focus import current as current_focus
from equity_engine.pages.templating import templates
from equity_engine.service import signals

FEED_LIMIT = 200
SCREEN_LIMIT = 200
CHANGES_LIMIT = 50


def radar_page(request: Request):
    with transaction() as connection:
        run = signals.latest_run(connection)
        context: dict[str, Any]
        if run is None:
            context = {"run": None, "catalogue": signals.catalogue(connection, None)}
        else:
            previous = signals.previous_run(connection, run)
            focus = current_focus(request)
            context = {
                "run": run,
                "previous": previous,
                "regime": signals.regime(connection, run),
                "tiles": signals.radar(connection, run, previous, focus),
                "stance_counts": signals.stance_counts(connection, run, focus),
                "changes": signals.stance_changes(connection, run, previous, CHANGES_LIMIT, focus),
                "stages": STAGES,
            }
    return templates.TemplateResponse(request, "radar.html", context)


def feed_page(request: Request, engine: str = "", stage: str = "", direction: str = "", q: str = ""):
    if stage and stage not in STAGES:
        raise HTTPException(status_code=422, detail=f"Unknown stage {stage}")
    if direction and direction not in ("BULL", "BEAR", "GATE"):
        raise HTTPException(status_code=422, detail=f"Unknown direction {direction}")
    with transaction() as connection:
        run = signals.latest_run(connection)
        found = (
            signals.feed(
                connection,
                run,
                engine,
                stage,
                direction,
                q.strip().upper(),
                FEED_LIMIT,
                current_focus(request),
            )
            if run
            else []
        )
        context = {
            "run": run,
            "signals": found,
            "engine": engine,
            "stage": stage,
            "direction": direction,
            "q": q.strip(),
            "engines": [e for e in signals.catalogue(connection, run) if e["implemented"]],
            "stages": STAGES,
            "limit": FEED_LIMIT,
        }
    template = "_signal_rows.html" if request.headers.get("HX-Request") else "signal.html"
    return templates.TemplateResponse(request, template, context)


def screen_page(
    request: Request,
    stance: Annotated[list[str] | None, Query()] = None,
    conviction: Annotated[list[str] | None, Query()] = None,
    has: Annotated[list[str] | None, Query()] = None,
    has_not: Annotated[list[str] | None, Query()] = None,
    confirmed_only: bool = False,
    min_mcap: float | None = None,
    index: str = "",
):
    stance, conviction, has, has_not = stance or [], conviction or [], has or [], has_not or []
    for value in stance:
        if value not in signals.SCREEN_STANCES:
            raise HTTPException(status_code=422, detail=f"Unknown stance {value}")
    for value in conviction:
        if value not in signals.SCREEN_CONVICTIONS:
            raise HTTPException(status_code=422, detail=f"Unknown conviction {value}")
    with transaction() as connection:
        run = signals.latest_run(connection)
        engines = [e for e in signals.catalogue(connection, run) if e["implemented"]]
        rows = (
            signals.screen(
                connection,
                run,
                stance,
                conviction,
                has,
                has_not,
                confirmed_only,
                min_mcap,
                index,
                SCREEN_LIMIT,
                current_focus(request),
            )
            if run
            else []
        )
        context = {
            "run": run,
            "rows": rows,
            "engines": engines,
            "indices": signals.index_codes(connection),
            "sel": {
                "stance": stance,
                "conviction": conviction,
                "has": has,
                "has_not": has_not,
                "confirmed_only": confirmed_only,
                "min_mcap": min_mcap,
                "index": index,
            },
            "stances": signals.SCREEN_STANCES,
            "convictions": signals.SCREEN_CONVICTIONS,
            "limit": SCREEN_LIMIT,
        }
    template = "_screen_rows.html" if request.headers.get("HX-Request") else "screen.html"
    return templates.TemplateResponse(request, template, context)
