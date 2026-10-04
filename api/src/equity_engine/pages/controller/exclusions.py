"""Hard exclusions (spec §69.1): what is out of the universe today, and why."""

from starlette.requests import Request

from equity_engine.db import transaction
from equity_engine.pages.templating import templates
from equity_engine.service import exclusions
from equity_engine.service.ingest import today_ist


def exclusion_page(request: Request):
    day = today_ist()
    with transaction() as connection:
        context = {
            "day": day,
            "counts": exclusions.counts_by_rule(connection, day),
            "excluded": exclusions.excluded(connection, day),
        }
    return templates.TemplateResponse(request, "exclusion.html", context)
