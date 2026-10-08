"""The Jinja environment for the pages, and the filters every template may use."""

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi.templating import Jinja2Templates

from equity_engine.pages.charts import donut_dasharray
from equity_engine.pages.focus import current as current_focus
from equity_engine.pages.nav import nav_items
from equity_engine.service.stance import CONVICTION_LABEL, STANCE_LABEL
from equity_engine.universe import FOCUS_CHOICES

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

templates = Jinja2Templates(directory=_TEMPLATES_DIR)
templates.env.globals["nav_items"] = nav_items
templates.env.globals["donut_dasharray"] = donut_dasharray
templates.env.globals["current_focus"] = current_focus
templates.env.globals["FOCUS_CHOICES"] = FOCUS_CHOICES
templates.env.globals["STANCE_LABEL"] = STANCE_LABEL
templates.env.globals["CONVICTION_LABEL"] = CONVICTION_LABEL
# daisyUI badge colours per stance / direction / stage, so every page paints them the same way.
# Stance: buy = green, sell = red, avoid = grey (user rule, 2026-10-04, superseding the earlier
# blue-for-short rule). Negative numbers, lagging and risk are red everywhere.
templates.env.globals["STANCE_CLASS"] = {
    "LONG": "badge-success",
    "LEAN_LONG": "badge-success badge-outline",
    "NEUTRAL": "badge-ghost",
    "LEAN_SHORT": "badge-error badge-outline",
    "SHORT": "badge-error",
    "AVOID": "badge-neutral",
}
templates.env.globals["DIRECTION_CLASS"] = {
    "BULL": "text-success",
    "BEAR": "text-error",
    "GATE": "text-warning",
}
templates.env.globals["STAGE_CLASS"] = {
    "EARLY": "badge-ghost",
    "EMERGING": "badge-info badge-outline",
    "CONFIRMED": "badge-info",
    "MATURE": "badge-neutral",
    "REVERSING": "badge-warning badge-outline",
}
templates.env.globals["STATUS_CLASS"] = {
    "LIVE": "badge-success",
    "READY": "badge-info",
    "BLOCKED": "badge-ghost",
    "FRAMEWORK": "badge-neutral badge-outline",
}

_DASH = "—"


def format_date(value: Any) -> Any:
    if not value:
        return _DASH
    if isinstance(value, (date, datetime)):
        return value.strftime("%d-%b-%Y")
    return value


def format_datetime(value: Any) -> Any:
    if not value:
        return _DASH
    if isinstance(value, datetime):
        return value.astimezone().strftime("%d-%b-%Y %H:%M")
    return value


def indian_number(value: Any, decimals: int = 0) -> str:
    """Indian digit grouping: 12,34,56,789.00."""
    if value is None:
        return _DASH
    number = Decimal(str(value))
    whole, _, fraction = f"{abs(number):.{decimals}f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups: list[str] = []
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    grouped = ",".join([*groups, tail])
    sign = "-" if number < 0 else ""
    return f"{sign}{grouped}.{fraction}" if decimals else f"{sign}{grouped}"


def crore(rupees: Any) -> str:
    """Rupees shown in crore."""
    if rupees is None:
        return _DASH
    return indian_number(Decimal(str(rupees)) / Decimal(10_000_000), 2)


templates.env.filters["fmt_date"] = format_date
templates.env.filters["fmt_dt"] = format_datetime
templates.env.filters["num"] = indian_number
templates.env.filters["crore"] = crore


def signed(value: Any, decimals: int = 0) -> str:
    """+1,234.5 / -1,234.5 for P&L columns; Jinja's % operator cannot add thousands separators."""
    if value is None:
        return _DASH
    return f"{float(value):+,.{decimals}f}"


templates.env.filters["signed"] = signed


def pct(value: Any, sign: bool = False) -> str:
    """A percentage for display: whole numbers, except that anything under 1% in size keeps one
    decimal so a +0.1% margin does not print as +0% (user rule, 2026-10-04). No % sign appended."""
    if value is None:
        return _DASH
    number = float(value)
    decimals = 1 if 0 < abs(number) < 1 else 0
    return f"{number:{'+' if sign else ''}.{decimals}f}"


templates.env.filters["pct"] = pct
