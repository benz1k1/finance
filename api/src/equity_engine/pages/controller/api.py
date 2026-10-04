"""JSON endpoints. Every response carries one explicit ``success`` indicator."""

from typing import Annotated, Any

from fastapi import HTTPException, Query

from equity_engine.db import transaction
from equity_engine.service import company as company_service
from equity_engine.service import exclusions as exclusion_service
from equity_engine.service import fundamentals as fundamentals_service
from equity_engine.service import health as health_service
from equity_engine.service import outcomes as outcomes_service
from equity_engine.service import securities
from equity_engine.service import signals as signal_service
from equity_engine.service import timeline as timeline_service
from equity_engine.service.ingest import today_ist


def health() -> dict[str, Any]:
    with transaction() as connection:
        summary = health_service.summary(connection)
    return {"success": True, "summary": summary}


def sources() -> dict[str, Any]:
    with transaction() as connection:
        return {"success": True, "sources": health_service.sources(connection)}


def security_search(
    q: str = "", limit: int = Query(default=50, ge=1, le=500), all: bool = False
) -> dict[str, Any]:  # noqa: A002
    """The universe (Nifty 500) unless ``all=true``."""
    with transaction() as connection:
        return {
            "success": True,
            "securities": securities.search(connection, q.strip(), limit, universe_only=not all),
        }


def prices(symbol: str, limit: int = Query(default=250, ge=1, le=5000)) -> dict[str, Any]:
    with transaction() as connection:
        security = securities.by_symbol(connection, symbol)
        if security is None:
            raise HTTPException(status_code=404, detail=f"No NSE security with symbol {symbol.upper()}")
        history = securities.prices(connection, security["isin"], limit)
    return {"success": True, "isin": security["isin"], "symbol": security["nse_symbol"], "prices": history}


def exclusions() -> dict[str, Any]:
    day = today_ist()
    with transaction() as connection:
        excluded = exclusion_service.excluded(connection, day)
    return {"success": True, "day": day, "excluded": excluded}


def _known_symbol(connection, symbol: str) -> str:
    security = securities.by_symbol(connection, symbol)
    if security is None:
        raise HTTPException(status_code=404, detail=f"No NSE security with symbol {symbol.upper()}")
    return security["nse_symbol"]


def ownership(symbol: str, quarters: int = Query(default=8, ge=1, le=40)) -> dict[str, Any]:
    with transaction() as connection:
        known = _known_symbol(connection, symbol)
        history = company_service.ownership_history(connection, known, quarters)
    return {"success": True, "symbol": known, "ownership": history}


def company(symbol: str) -> dict[str, Any]:
    """Website, business activities and products. ``profile`` is null for a company that files
    no sustainability report."""
    with transaction() as connection:
        known = _known_symbol(connection, symbol)
        profile = company_service.profile(connection, known)
    return {"success": True, "symbol": known, "profile": profile}


def deals(symbol: str, limit: int = Query(default=100, ge=1, le=2000)) -> dict[str, Any]:
    with transaction() as connection:
        known = _known_symbol(connection, symbol)
        found = company_service.deals(connection, known, limit)
    return {"success": True, "symbol": known, "deals": found}


def _run_or_404(connection):
    run = signal_service.latest_run(connection)
    if run is None:
        raise HTTPException(status_code=404, detail="No engine run yet. Run: python ingest.py signals")
    return run


def engines() -> dict[str, Any]:
    """The catalogue with each engine's derived status (spec §118)."""
    with transaction() as connection:
        run = signal_service.latest_run(connection)
        return {"success": True, "run": run, "engines": signal_service.catalogue(connection, run)}


def engine(key: str, limit: int = Query(default=200, ge=1, le=5000)) -> dict[str, Any]:
    with transaction() as connection:
        run = signal_service.latest_run(connection)
        found = next((e for e in signal_service.catalogue(connection, run) if e["engine_key"] == key), None)
        if found is None:
            raise HTTPException(status_code=404, detail=f"No engine {key}")
        fired = (
            signal_service.engine_signals(connection, run, key, limit) if run and found["implemented"] else []
        )
    with transaction() as connection:
        performance = (
            outcomes_service.stance_performance(connection)
            if key == "stance"
            else outcomes_service.engine_performance(connection, key)
        )
    return {"success": True, "engine": found, "signals": fired, "performance": performance}


def radar() -> dict[str, Any]:
    with transaction() as connection:
        run = _run_or_404(connection)
        previous = signal_service.previous_run(connection, run)
        return {
            "success": True,
            "run": run,
            "regime": signal_service.regime(connection, run),
            "tiles": signal_service.radar(connection, run, previous),
            "stances": signal_service.stance_counts(connection, run),
        }


def signals(
    engine: str = "",
    stage: str = "",
    direction: str = "",
    q: str = "",
    limit: int = Query(default=200, ge=1, le=5000),
) -> dict[str, Any]:
    with transaction() as connection:
        run = _run_or_404(connection)
        found = signal_service.feed(connection, run, engine, stage, direction, q.strip().upper(), limit)
    return {"success": True, "run": run, "signals": found}


def stance(symbol: str) -> dict[str, Any]:
    """One company's stance with the signals it was computed from (spec §118)."""
    with transaction() as connection:
        security = securities.by_symbol(connection, symbol)
        if security is None:
            raise HTTPException(status_code=404, detail=f"No NSE security with symbol {symbol.upper()}")
        run = _run_or_404(connection)
        found = signal_service.stance_for(connection, run, security["isin"])
        fired = signal_service.for_security(connection, run, security["isin"])
        history = signal_service.stance_history(connection, security["isin"], 12)
    return {
        "success": True,
        "symbol": security["nse_symbol"],
        "run": run,
        "stance": found,
        "signals": fired,
        "history": history,
    }


def screen(
    stance: Annotated[list[str] | None, Query()] = None,
    conviction: Annotated[list[str] | None, Query()] = None,
    has: Annotated[list[str] | None, Query()] = None,
    has_not: Annotated[list[str] | None, Query()] = None,
    confirmed_only: bool = False,
    min_mcap: float | None = None,
    index: str = "",
    limit: int = Query(default=200, ge=1, le=5000),
) -> dict[str, Any]:
    stance, conviction, has, has_not = stance or [], conviction or [], has or [], has_not or []
    with transaction() as connection:
        run = _run_or_404(connection)
        found = signal_service.screen(
            connection, run, stance, conviction, has, has_not, confirmed_only, min_mcap, index, limit
        )
    return {"success": True, "run": run, "rows": found}


def financials(symbol: str, limit: int = Query(default=12, ge=1, le=40)) -> dict[str, Any]:
    """Canonical quarterly results, TTM, newest balance sheet and trailing multiples (spec §5)."""
    with transaction() as connection:
        security = securities.by_symbol(connection, symbol)
        if security is None:
            raise HTTPException(status_code=404, detail=f"No NSE security with symbol {symbol.upper()}")
        history = fundamentals_service.quarters(connection, security["nse_symbol"], limit)
        market_cap = float(security["market_cap"]) if security.get("market_cap") else None
    return {
        "success": True,
        "symbol": security["nse_symbol"],
        "quarters": history,
        "ttm": fundamentals_service.ttm(history) if history else None,
        "balance_sheet": fundamentals_service.balance_sheet(history) if history else None,
        "multiples": fundamentals_service.multiples(market_cap, history) if history else {},
    }


def timeline(
    symbol: str,
    kind: Annotated[list[str] | None, Query()] = None,
    limit: int = Query(default=300, ge=1, le=2000),
) -> dict[str, Any]:
    """The company timeline (spec §31)."""
    kinds = [k for k in (kind or []) if k in timeline_service.KINDS]
    with transaction() as connection:
        known = _known_symbol(connection, symbol)
        entries = timeline_service.for_symbol(connection, known, kinds, limit)
    return {"success": True, "symbol": known, "entries": entries}
