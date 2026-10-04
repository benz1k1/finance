"""The Nifty 50 / Nifty 500 focus toggle: a cookie read by every page and list query."""

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from starlette.requests import Request

from equity_engine.universe import DEFAULT_FOCUS, FOCUS_CHOICES

COOKIE = "focus"


def current(request: Request) -> str:
    value = request.cookies.get(COOKIE, DEFAULT_FOCUS)
    return value if value in FOCUS_CHOICES else DEFAULT_FOCUS


def set_focus(request: Request, index_code: str, next: str = "/"):  # noqa: A002 — the query parameter
    """``GET /focus/{index_code}?next=/path`` sets the cookie and goes back to the page."""
    if index_code not in FOCUS_CHOICES:
        raise HTTPException(status_code=422, detail=f"Unknown focus {index_code}")
    target = next if next.startswith("/") and not next.startswith("//") else "/"
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(COOKIE, index_code, max_age=365 * 24 * 3600, samesite="lax")
    return response
