"""Deal counterparties: the client list (search as you type) and one client's disclosed portfolio."""

from fastapi import HTTPException
from starlette.requests import Request

from equity_engine.db import transaction
from equity_engine.pages.templating import templates
from equity_engine.service import client_meta, client_types, clients

LIST_LIMIT = 100
DEAL_ROWS = 200


def client_list(request: Request, q: str = "", type: str = ""):  # noqa: A002 — the query parameter is ?type=
    query = q.strip()
    if type and type not in client_types.LABEL:
        raise HTTPException(status_code=422, detail=f"Unknown client type {type!r}")
    with transaction() as connection:
        found = clients.search(connection, query, LIST_LIMIT, type)
        totals = clients.portfolios_for(connection, [c["client_name"] for c in found])
        counts = clients.type_counts(connection)
    context = {
        "clients": found,
        "totals": totals,
        "q": query,
        "type": type,
        "type_counts": counts,
        "limit": LIST_LIMIT,
    }
    template = "_client_rows.html" if request.headers.get("HX-Request") else "client_list.html"
    return templates.TemplateResponse(request, template, context)


def client_page(request: Request, name: str):
    with transaction() as connection:
        summary = clients.summary(connection, name)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"No deal counterparty named {name!r}")
        book = clients.portfolio(connection, name)
        context = {
            "client": summary,
            "meta": client_meta.for_client(connection, name),
            "about": clients.about(summary, book),
            "portfolio": book["positions"],
            "totals": book["totals"],
            "deals": clients.deals(connection, name, DEAL_ROWS),
            "deal_limit": DEAL_ROWS,
        }
    return templates.TemplateResponse(request, "client.html", context)
