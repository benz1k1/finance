"""
Deal counterparties (spec §65, §69.2): the named clients in NSE's bulk and block deal
disclosures, and what their disclosed trades add up to per security. A "portfolio" here is only
what the disclosures show — shares bought or sold in deals NSE published — never a holding
statement: positions acquired through ordinary trading are invisible, so a net quantity below
zero means the client sold more through disclosed deals than it bought through them.
"""

from typing import Any

from sqlalchemy import Connection

from equity_engine.db import row, rows
from equity_engine.service.client_types import classify

# Newest close per symbol for marking disclosed positions to market.
_LATEST_CLOSE = """
    SELECT DISTINCT ON (p.symbol) p.symbol, p.trade_date, p.close
      FROM price_daily p
     WHERE p.series IN ('EQ', 'SM') AND p.trade_date > (SELECT max(trade_date) FROM price_daily) - 10
     ORDER BY p.symbol, p.trade_date DESC
"""


def search(connection: Connection, query: str, limit: int, client_type: str = "") -> list[dict[str, Any]]:
    """Clients matching ``query`` (any part of the name), most deals first, each with its inferred
    type; ``client_type`` keeps one category. Classification is by name, so it happens here."""
    found = rows(
        connection,
        """
        SELECT client_name, count(*) AS deals, count(DISTINCT symbol) AS securities,
               sum(CASE WHEN side = 'BUY' THEN quantity * price ELSE 0 END) / 1e7 AS bought_crore,
               sum(CASE WHEN side = 'SELL' THEN quantity * price ELSE 0 END) / 1e7 AS sold_crore,
               min(deal_date) AS first_deal, max(deal_date) AS last_deal
          FROM deal
         WHERE client_name ILIKE :pattern
         GROUP BY client_name
         ORDER BY deals DESC, client_name
        """,
        {"pattern": f"%{query}%"},
    )
    for client in found:
        client["kind"] = classify(client["client_name"])
    if client_type:
        found = [c for c in found if c["kind"]["type"] == client_type]
    return found[:limit]


def type_counts(connection: Connection) -> list[dict[str, Any]]:
    """How many counterparties and how much disclosed value fall in each inferred type."""
    found = rows(
        connection,
        "SELECT client_name, count(*) AS deals, sum(quantity * price) / 1e7 AS value_crore FROM deal GROUP BY client_name",
    )
    tally: dict[str, dict[str, Any]] = {}
    for client in found:
        kind = classify(client["client_name"])
        cell = tally.setdefault(
            kind["type"],
            {
                "type": kind["type"],
                "label": kind["label"],
                "badge": kind["badge"],
                "clients": 0,
                "deals": 0,
                "value_crore": 0.0,
            },
        )
        cell["clients"] += 1
        cell["deals"] += client["deals"]
        cell["value_crore"] += float(client["value_crore"])
    return sorted(tally.values(), key=lambda c: -c["value_crore"])


def summary(connection: Connection, client_name: str) -> dict[str, Any] | None:
    found = row(
        connection,
        """
        SELECT client_name, count(*) AS deals, count(DISTINCT symbol) AS securities,
               count(*) FILTER (WHERE kind = 'BULK') AS bulk_deals, count(*) FILTER (WHERE kind = 'BLOCK') AS block_deals,
               sum(CASE WHEN side = 'BUY' THEN quantity * price ELSE 0 END) / 1e7 AS bought_crore,
               sum(CASE WHEN side = 'SELL' THEN quantity * price ELSE 0 END) / 1e7 AS sold_crore,
               min(deal_date) AS first_deal, max(deal_date) AS last_deal
          FROM deal WHERE client_name = :name GROUP BY client_name
        """,
        {"name": client_name},
    )
    if found is not None:
        found["kind"] = classify(client_name)
    return found


def latest_closes(connection: Connection) -> dict[str, dict[str, Any]]:
    return {r["symbol"]: r for r in rows(connection, _LATEST_CLOSE)}


def positions(deals: list[dict[str, Any]], closes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Average-cost book of one client's disclosed deals, oldest first (buys before sells on a day).

    Per security: open quantity and its cost, market value at the latest close, unrealised P&L,
    realised P&L on the sells that earlier disclosed buys cover, and the *uncovered* sells — shares
    sold through disclosed deals that no disclosed buy supplied, so their profit cannot be known.
    Rupees throughout; the page converts to crore. Pure, so the arithmetic is unit-tested."""
    ordered = sorted(deals, key=lambda d: (d["deal_date"], d["side"] != "BUY", d["seq"]))
    book: dict[str, dict[str, Any]] = {}
    for d in ordered:
        b = book.setdefault(
            d["symbol"],
            {
                "symbol": d["symbol"],
                "security_name": d["security_name"],
                "deals": 0,
                "bought_qty": 0,
                "bought_value": 0.0,
                "sold_qty": 0,
                "sold_value": 0.0,
                "open_qty": 0,
                "open_cost": 0.0,
                "realised": 0.0,
                "covered_sold_qty": 0,
                "uncovered_sold_qty": 0,
                "uncovered_sold_value": 0.0,
                "first_deal": d["deal_date"],
                "last_deal": d["deal_date"],
            },
        )
        qty, price = int(d["quantity"]), float(d["price"])
        b["deals"] += 1
        b["last_deal"] = max(b["last_deal"], d["deal_date"])
        b["first_deal"] = min(b["first_deal"], d["deal_date"])
        if d["side"] == "BUY":
            b["bought_qty"] += qty
            b["bought_value"] += qty * price
            b["open_qty"] += qty
            b["open_cost"] += qty * price
        else:
            b["sold_qty"] += qty
            b["sold_value"] += qty * price
            covered = min(qty, b["open_qty"])
            if covered:
                avg_cost = b["open_cost"] / b["open_qty"]
                b["realised"] += covered * (price - avg_cost)
                b["open_cost"] -= covered * avg_cost
                b["open_qty"] -= covered
                b["covered_sold_qty"] += covered
            if qty > covered:
                b["uncovered_sold_qty"] += qty - covered
                b["uncovered_sold_value"] += (qty - covered) * price
    totals = {
        "securities": len(book),
        "open_positions": 0,
        "bought_value": 0.0,
        "sold_value": 0.0,
        "open_cost": 0.0,
        "market_value": 0.0,
        "unrealised": 0.0,
        "realised": 0.0,
        "uncovered_sold_value": 0.0,
        "unpriced_open_qty": 0,
    }
    for b in book.values():
        close = closes.get(b["symbol"])
        b["last_close"] = float(close["close"]) if close else None
        b["close_date"] = close["trade_date"] if close else None
        b["avg_buy_price"] = b["bought_value"] / b["bought_qty"] if b["bought_qty"] else None
        b["avg_sell_price"] = b["sold_value"] / b["sold_qty"] if b["sold_qty"] else None
        b["avg_cost"] = b["open_cost"] / b["open_qty"] if b["open_qty"] else None
        if b["open_qty"] and b["last_close"] is not None:
            b["market_value"] = b["open_qty"] * b["last_close"]
            b["unrealised"] = b["market_value"] - b["open_cost"]
            b["unrealised_pct"] = (b["market_value"] / b["open_cost"] - 1) * 100 if b["open_cost"] else None
        else:
            b["market_value"] = b["unrealised"] = b["unrealised_pct"] = None
            if b["open_qty"]:
                totals["unpriced_open_qty"] += b["open_qty"]
        b["total_pnl"] = b["realised"] + (b["unrealised"] or 0.0)
        for key in ("bought_value", "sold_value", "open_cost", "realised", "uncovered_sold_value"):
            totals[key] += b[key]
        if b["open_qty"]:
            totals["open_positions"] += 1
        totals["market_value"] += b["market_value"] or 0.0
        totals["unrealised"] += b["unrealised"] or 0.0
    totals["total_pnl"] = totals["realised"] + totals["unrealised"]
    deployed = totals["bought_value"]
    totals["return_on_bought_pct"] = (totals["total_pnl"] / deployed * 100) if deployed else None
    totals["unrealised_pct"] = (
        (totals["unrealised"] / totals["open_cost"] * 100) if totals["open_cost"] else None
    )
    ranked = sorted(
        book.values(),
        key=lambda b: -abs((b["market_value"] or 0.0) if b["open_qty"] else b["total_pnl"]),
    )
    return {"positions": ranked, "totals": totals}


def portfolio(connection: Connection, client_name: str) -> dict[str, Any]:
    """One client's disclosed deals, booked with ``positions`` and priced at the latest close."""
    client_deals = rows(
        connection,
        """
        SELECT d.deal_date, d.kind, d.seq, d.symbol, d.security_name, d.side, d.quantity, d.price, s.name, s.isin
          FROM deal d LEFT JOIN security s ON s.nse_symbol = d.symbol WHERE d.client_name = :name
        """,
        {"name": client_name},
    )
    result = positions(client_deals, latest_closes(connection))
    names = {d["symbol"]: d["name"] for d in client_deals}
    for position in result["positions"]:
        position["name"] = names.get(position["symbol"])
    return result


def portfolios_for(connection: Connection, client_names: list[str]) -> dict[str, dict[str, Any]]:
    """Totals per client for a list page, from one query over all their deals."""
    if not client_names:
        return {}
    all_deals = rows(
        connection,
        """
        SELECT client_name, deal_date, kind, seq, symbol, security_name, side, quantity, price
          FROM deal WHERE client_name = ANY(:names)
        """,
        {"names": client_names},
    )
    closes = latest_closes(connection)
    by_client: dict[str, list[dict[str, Any]]] = {}
    for d in all_deals:
        by_client.setdefault(d["client_name"], []).append(d)
    return {name: positions(client_deals, closes)["totals"] for name, client_deals in by_client.items()}


def deals(connection: Connection, client_name: str, limit: int) -> list[dict[str, Any]]:
    return rows(
        connection,
        """
        SELECT kind, deal_date, symbol, security_name, side, quantity, price, quantity * price / 1e7 AS value_crore, remarks
          FROM deal WHERE client_name = :name ORDER BY deal_date DESC, kind, seq LIMIT :limit
        """,
        {"name": client_name, "limit": limit},
    )


def about(summary: dict[str, Any], book: dict[str, Any]) -> list[str]:
    """Plain sentences describing a counterparty from its disclosed deals: what kind of entity the
    name says it is, how active, which way it leans, where it concentrates, and how it has done.
    Every number is one already on the page; this reads them out."""
    kind = summary["kind"]
    totals, positions = book["totals"], book["positions"]
    bought, sold = float(summary["bought_crore"]), float(summary["sold_crore"])
    years = max(1, (summary["last_deal"] - summary["first_deal"]).days) / 365.25
    lines = [
        f"{summary['client_name']} is read as {kind['label'].lower()} from its name: {kind['basis']}."
        + (" As a domestic institution it counts toward DII flows." if kind["dii"] else "")
        + (" As a foreign investor it counts toward FII/FPI flows." if kind["type"] == "FII" else "")
        + (
            " Proprietary and high-frequency firms trade both sides daily, so their net flow carries no investment view."
            if kind["type"] == "PROP_TRADER"
            else ""
        )
    ]
    lines.append(
        f"It appears in {summary['deals']:,} disclosed bulk and block deals across {summary['securities']} securities "
        f"between {summary['first_deal']:%b %Y} and {summary['last_deal']:%b %Y}"
        + (f", about {summary['deals'] / years:.0f} a year." if years >= 1 else ".")
    )
    net = bought - sold
    if bought and sold:
        tilt = (
            "a net buyer"
            if net > 0.1 * (bought + sold)
            else (
                "a net seller"
                if net < -0.1 * (bought + sold)
                else "roughly balanced between buying and selling"
            )
        )
        lines.append(f"It bought ₹{bought:,.0f} crore and sold ₹{sold:,.0f} crore at deal prices: {tilt}.")
    elif bought:
        lines.append(f"Every disclosed deal was a purchase, ₹{bought:,.0f} crore in all.")
    elif sold:
        lines.append(
            f"Every disclosed deal was a sale, ₹{sold:,.0f} crore in all — typical of a promoter or early investor exiting."
        )
    open_positions = [p for p in positions if p["open_qty"] and p["market_value"]]
    if open_positions:
        top = sorted(open_positions, key=lambda p: -p["market_value"])[:3]
        share = (
            sum(p["market_value"] for p in top) / totals["market_value"] * 100
            if totals["market_value"]
            else 0
        )
        lines.append(
            f"Its disclosed buys still held are worth ₹{totals['market_value'] / 1e7:,.0f} crore across {len(open_positions)} securities; "
            f"the largest — {', '.join(p['symbol'] for p in top)} — make up {share:.0f}% of that."
        )
    if totals["bought_value"]:
        lines.append(
            f"Marked at the newest close, the disclosed book shows {'+' if totals['realised'] >= 0 else '−'}₹{abs(totals['realised']) / 1e7:,.0f} crore realised and "
            f"{'+' if totals['unrealised'] >= 0 else '−'}₹{abs(totals['unrealised']) / 1e7:,.0f} crore unrealised, {totals['return_on_bought_pct']:+.1f}% on everything bought."
            + (
                f" ₹{totals['uncovered_sold_value'] / 1e7:,.0f} crore of sales had no disclosed buy behind them and are left out."
                if totals["uncovered_sold_value"]
                else ""
            )
        )
    return lines
