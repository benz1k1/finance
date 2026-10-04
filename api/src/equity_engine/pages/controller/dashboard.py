"""Data health: the landing page."""

from starlette.requests import Request

from equity_engine.db import transaction
from equity_engine.pages.templating import templates
from equity_engine.service import exclusions, health
from equity_engine.service.ingest import today_ist


def dashboard(request: Request):
    with transaction() as connection:
        context = {
            "summary": health.summary(connection),
            "sources": health.sources(connection),
            "excluded": len(exclusions.excluded(connection, today_ist())),
        }
    return templates.TemplateResponse(request, "dashboard.html", context)
