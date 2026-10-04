"""Page and /api routes, registered as a list so the whole surface reads in one place.
REST paths are singular; the method distinguishes collection from item."""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from equity_engine.pages import focus
from equity_engine.pages.controller import api, dashboard, engines, exclusions, securities, signals

ROUTES: list[tuple[str, Callable[..., Any], list[str]]] = [
    ("/", signals.radar_page, ["GET"]),
    ("/health", dashboard.dashboard, ["GET"]),
    ("/focus/{index_code}", focus.set_focus, ["GET"]),
    ("/signal", signals.feed_page, ["GET"]),
    ("/engine", engines.engine_list, ["GET"]),
    ("/engine/{key}", engines.engine_page, ["GET"]),
    ("/screen", signals.screen_page, ["GET"]),
    ("/security", securities.security_list, ["GET"]),
    ("/security/{symbol}", securities.security_page, ["GET"]),
    ("/security/{symbol}/timeline", securities.timeline_page, ["GET"]),
    ("/ownership", securities.ownership_page, ["GET"]),
    ("/exclusion", exclusions.exclusion_page, ["GET"]),
    ("/api/health", api.health, ["GET"]),
    ("/api/source", api.sources, ["GET"]),
    ("/api/security", api.security_search, ["GET"]),
    ("/api/price/{symbol}", api.prices, ["GET"]),
    ("/api/exclusion", api.exclusions, ["GET"]),
    ("/api/ownership/{symbol}", api.ownership, ["GET"]),
    ("/api/company/{symbol}", api.company, ["GET"]),
    ("/api/deal/{symbol}", api.deals, ["GET"]),
    ("/api/financials/{symbol}", api.financials, ["GET"]),
    ("/api/timeline/{symbol}", api.timeline, ["GET"]),
    ("/api/engine", api.engines, ["GET"]),
    ("/api/engine/{key}", api.engine, ["GET"]),
    ("/api/radar", api.radar, ["GET"]),
    ("/api/signal", api.signals, ["GET"]),
    ("/api/stance/{symbol}", api.stance, ["GET"]),
    ("/api/screen", api.screen, ["GET"]),
]


def register_routes(app: FastAPI) -> None:
    for path, endpoint, methods in ROUTES:
        app.add_api_route(path, endpoint, methods=methods, include_in_schema=path.startswith("/api/"))
