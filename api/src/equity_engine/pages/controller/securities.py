"""The security list (search as you type) and one security's page."""

from typing import Annotated

from fastapi import HTTPException, Query
from fastapi.responses import RedirectResponse
from starlette.requests import Request

from equity_engine.db import transaction
from equity_engine.pages.charts import sparkline
from equity_engine.pages.focus import current as current_focus
from equity_engine.pages.templating import templates
from equity_engine.service import company, exclusions, fundamentals, securities, signals, timeline
from equity_engine.service.client_types import classify
from equity_engine.service.ingest import today_ist

LIST_LIMIT = 100
PRICE_ROWS = 120
CHART_RANGES = {
    "ytd": None,
    "1y": 252,
    "3y": 756,
    "5y": 1260,
    "all": None,
}  # sessions; ytd and all are date-bound
OWNERSHIP_QUARTERS = 8
DEAL_ROWS = 100


def redirect_to_equities(request: Request, rest: str = ""):
    """``/security…`` → ``/equities…`` (renamed 2026-10-04), query string kept."""
    target = (
        "/equities" + (f"/{rest}" if rest else "") + (f"?{request.url.query}" if request.url.query else "")
    )
    return RedirectResponse(target, status_code=301)


def security_list(request: Request, q: str = "", all: bool = False, govt: bool = False):  # noqa: A002 — ?all=1
    query = q.strip()
    with transaction() as connection:
        psu = company.psu_tags(connection)
        # the government toggle keeps central and state undertakings (PSU-promoted ventures are not
        # state-controlled); search wider first so the filter is not applied to a truncated list
        found = securities.search(
            connection,
            query,
            5000 if govt else LIST_LIMIT,
            universe_only=not all,
            focus=current_focus(request),
        )
        if govt:
            found = [
                s
                for s in found
                if s["nse_symbol"] in psu and psu[s["nse_symbol"]]["owner"] in ("central", "state")
            ][:LIST_LIMIT]
        stances = signals.stance_by_symbol(
            connection, signals.latest_run(connection), [s["nse_symbol"] for s in found]
        )
        pe = fundamentals.pe_table(connection)
    context = {
        "securities": found,
        "q": query,
        "limit": LIST_LIMIT,
        "stances": stances,
        "all": all,
        "govt": govt,
        "pe": pe,
        "psu": psu,
    }
    # The search box swaps only the table body.
    template = "_security_rows.html" if request.headers.get("HX-Request") else "security_list.html"
    return templates.TemplateResponse(request, template, context)


def security_page(request: Request, symbol: str):
    with transaction() as connection:
        security = securities.by_symbol(connection, symbol)
        if security is None:
            raise HTTPException(status_code=404, detail=f"No NSE security with symbol {symbol.upper()}")
        context = {
            "security": security,
            "prices": securities.prices(connection, security["isin"], PRICE_ROWS),
            **_price_chart(connection, security, "1y"),
            "excluded_as": exclusions.is_excluded(connection, security["isin"], today_ist()),
            **securities.profile(connection, security["isin"], security["nse_symbol"]),
            "ownership": company.ownership_history(connection, security["nse_symbol"], OWNERSHIP_QUARTERS),
            "classify": classify,
            "psu": company.psu_tag(connection, security["nse_symbol"]),
            "business": company.profile(connection, security["nse_symbol"]),
            "deals": company.deals(connection, security["nse_symbol"], DEAL_ROWS),
            **_engine_panel(connection, security["isin"]),
            **_financials(connection, security),
        }
    return templates.TemplateResponse(request, "security.html", context)


def _price_chart(connection, security: dict, range_key: str) -> dict:
    """The compact close chart for one range: a year of sessions by default, year to date, three or
    five years, or everything on record (prices here start in 2019)."""
    if range_key not in CHART_RANGES:
        raise HTTPException(status_code=422, detail=f"range must be one of {list(CHART_RANGES)}")
    limit = CHART_RANGES[range_key] or 5000
    found = securities.prices(connection, security["isin"], limit)
    if range_key == "ytd" and found:
        year_start = found[0]["trade_date"].replace(month=1, day=1)
        found = [p for p in found if p["trade_date"] >= year_start]
    return {
        "price_chart": sparkline([(p["trade_date"], float(p["close"])) for p in found]),
        "chart_range": range_key,
        "chart_ranges": list(CHART_RANGES),
        "chart_sessions": len(found),
    }


def price_chart_fragment(request: Request, symbol: str, range: str = "1y"):  # noqa: A002 — the query parameter is ?range=
    with transaction() as connection:
        security = securities.by_symbol(connection, symbol)
        if security is None:
            raise HTTPException(status_code=404, detail=f"No NSE security with symbol {symbol.upper()}")
        context = {"security": security, **_price_chart(connection, security, range)}
    return templates.TemplateResponse(request, "_price_chart.html", context)


def _engine_panel(connection, isin: str) -> dict:
    """The stance panel and engine grid (spec §118): every engine, fired or not, with its reason."""
    run = signals.latest_run(connection)
    catalogue = [e for e in signals.catalogue(connection, run) if e["group"] != "FRAMEWORK"]
    fired = signals.for_security(connection, run, isin) if run else []
    by_engine: dict[str, list] = {}
    for signal in fired:
        by_engine.setdefault(signal["engine_key"], []).append(signal)
    for engine in catalogue:
        engine["fired"] = by_engine.get(engine["engine_key"], [])
    groups: dict[str, list] = {}
    for engine in catalogue:
        groups.setdefault(engine["group"], []).append(engine)
    return {
        "run": run,
        "stance": signals.stance_for(connection, run, isin) if run else None,
        "stance_history": signals.stance_history(connection, isin, 12),
        "fired": fired,
        "for_signals": [s for s in fired if s["direction"] == "BULL"][:3],
        "against_signals": [s for s in fired if s["direction"] in ("BEAR", "GATE")][:3],
        "engine_groups": groups,
    }


def ownership_page(request: Request, sort: str = "fii_pct"):
    if sort not in company.OWNERSHIP_COLUMNS:
        raise HTTPException(status_code=422, detail=f"Unknown sort column {sort}")
    with transaction() as connection:
        rows = company.ownership_screen(connection, sort, LIST_LIMIT, current_focus(request))
        context = {
            "rows": rows,
            "sort": sort,
            "limit": LIST_LIMIT,
            "stances": signals.stance_by_symbol(
                connection, signals.latest_run(connection), [r["symbol"] for r in rows]
            ),
        }
    return templates.TemplateResponse(request, "ownership.html", context)


def _financials(connection, security: dict) -> dict:
    """Quarterly results (spec §5, §45): the canonical quarters, TTM, the newest balance sheet and
    trailing multiples at the newest market cap."""
    history = fundamentals.quarters(connection, security["nse_symbol"], 12)
    market_cap = float(security["market_cap"]) if security.get("market_cap") else None
    multiples = fundamentals.multiples(market_cap, history) if history else {}
    sector = fundamentals.industry_pe(connection, security["isin"]) if multiples.get("pe") else None
    return {
        "quarters": history,
        "ttm": fundamentals.ttm(history) if history else None,
        "balance_sheet": fundamentals.balance_sheet(history) if history else None,
        "multiples": multiples,
        "sector_pe": sector,
    }


TIMELINE_ROWS = 300


def timeline_page(request: Request, symbol: str, kind: Annotated[list[str] | None, Query()] = None):
    """The company timeline (spec §31): one chronology of filings, actions, meetings, ratings,
    deals and stance changes, filterable by kind."""
    kinds = [k for k in (kind or []) if k in timeline.KINDS]
    with transaction() as connection:
        security = securities.by_symbol(connection, symbol)
        if security is None:
            raise HTTPException(status_code=404, detail=f"No NSE security with symbol {symbol.upper()}")
        entries = timeline.for_symbol(connection, security["nse_symbol"], kinds, TIMELINE_ROWS)
    context = {
        "security": security,
        "entries": entries,
        "kinds": timeline.KINDS,
        "selected": kinds,
        "limit": TIMELINE_ROWS,
    }
    template = "_timeline_rows.html" if request.headers.get("HX-Request") else "timeline.html"
    return templates.TemplateResponse(request, template, context)
