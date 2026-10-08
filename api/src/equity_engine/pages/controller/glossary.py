"""Terminology: the jargon the app prints, explained with worked examples."""

from starlette.requests import Request

from equity_engine.pages.glossary import TERMS, by_group
from equity_engine.pages.templating import templates


def glossary_page(request: Request):
    return templates.TemplateResponse(request, "glossary.html", {"groups": by_group(), "count": len(TERMS)})
