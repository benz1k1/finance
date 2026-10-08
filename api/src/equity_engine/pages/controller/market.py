"""Market history (spec §28, §29): industry rotation and breadth over time, as line charts."""

from typing import Annotated

from fastapi import HTTPException, Query
from starlette.requests import Request

from equity_engine.db import transaction
from equity_engine.pages.charts import line_chart
from equity_engine.pages.templating import templates
from equity_engine.service import market_history

MAX_SERIES = 8
DEFAULT_EACH_SIDE = 3  # leaders and laggards shown when nothing is chosen


def market_page(
    request: Request,
    range: str = "1y",  # noqa: A002 — the query parameter is ?range=
    industry: Annotated[list[str] | None, Query()] = None,
    smooth: bool = False,
):
    if range not in market_history.RANGES:
        raise HTTPException(status_code=422, detail=f"range must be one of {sorted(market_history.RANGES)}")
    chosen = industry or []
    with transaction() as connection:
        start, end, step = market_history.window(connection, range)
        rotation = market_history.rotation(connection, start, end, step)
        breadth = market_history.breadth(connection, start, end)
    industries = rotation["industries"]
    latest = {name: pts[-1]["value"] for name, pts in industries.items()}
    ranked = sorted(latest, key=latest.get, reverse=True)
    if not chosen:
        chosen = ranked[:DEFAULT_EACH_SIDE] + ranked[-DEFAULT_EACH_SIDE:]
    chosen = [name for name in chosen if name in industries][:MAX_SERIES]
    rotation_chart = line_chart(
        {name: [(p["date"], p["value"]) for p in industries[name]] for name in chosen},
        unit=" pts",
        smooth=smooth,
    )
    breadth_chart = line_chart(
        {
            "Above 200-day average %": [
                (b["as_of"], float(b["above_200dma_pct"]))
                for b in breadth
                if b["above_200dma_pct"] is not None
            ],
            "Advancing over 1 month %": [
                (b["as_of"], float(b["advancing_1m_pct"]))
                for b in breadth
                if b["advancing_1m_pct"] is not None
            ],
        },
        unit="%",
        zero_line=False,
        smooth=smooth,
    )
    median_chart = line_chart(
        {
            "Median 3-month return %": [
                (b["as_of"], float(b["median_return_3m_pct"]))
                for b in breadth
                if b["median_return_3m_pct"] is not None
            ]
        },
        unit="%",
        smooth=smooth,
    )
    context = {
        "range": range,
        "smooth": smooth,
        "ranges": list(market_history.RANGES),
        "start": start,
        "end": end,
        "step": step,
        "industries": ranked,
        "latest": latest,
        "chosen": chosen,
        "members": {name: industries[name][-1]["members"] for name in industries},
        "rotation_chart": rotation_chart,
        "breadth_chart": breadth_chart,
        "median_chart": median_chart,
        "regimes": breadth,
        "max_series": MAX_SERIES,
    }
    template = "_market_charts.html" if request.headers.get("HX-Request") else "market.html"
    return templates.TemplateResponse(request, template, context)
