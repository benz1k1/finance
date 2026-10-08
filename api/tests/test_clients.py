"""Deal counterparties: the client list and a client's disclosed portfolio, recomputed from the
deal table with plain SQL (never a holding statement — only what NSE disclosed)."""

from decimal import Decimal

import httpx
import pytest

from equity_engine.db import rows

HTML = {"Accept": "text/html"}


@pytest.fixture(scope="module")
def top_client(client: httpx.Client) -> str:
    from equity_engine.db import transaction

    with transaction() as connection:
        found = rows(connection, "SELECT client_name FROM deal GROUP BY 1 ORDER BY count(*) DESC LIMIT 1")
    if not found:
        pytest.fail("No bulk/block deals loaded. Run: python ingest.py deals")
    return found[0]["client_name"]


def test_client_list_renders_and_searches(client: httpx.Client, top_client: str):
    page = client.get("/client", headers=HTML)
    assert page.status_code == 200 and top_client in page.text and 'id="client-rows"' in page.text
    word = top_client.split()[0]
    partial = client.get("/client", params={"q": word.lower()}, headers={"HX-Request": "true"})
    assert partial.status_code == 200 and top_client in partial.text and "<html" not in partial.text
    none = client.get("/client", params={"q": "zzzz-no-such-client"}, headers={"HX-Request": "true"})
    assert "No counterparty matches" in none.text


def test_unknown_client_is_404(client: httpx.Client):
    assert client.get("/client/NO SUCH CLIENT LLP", headers=HTML).status_code == 404


def test_client_portfolio_adds_up_the_disclosed_deals(client: httpx.Client, top_client: str, connection):
    page = client.get(f"/client/{top_client}", headers=HTML)
    assert page.status_code == 200 and 'id="portfolio-table"' in page.text and 'id="deal-table"' in page.text
    from equity_engine.service import clients

    portfolio = {p["symbol"]: p for p in clients.portfolio(connection, top_client)["positions"]}
    expected = rows(
        connection,
        """
        SELECT symbol, count(*) AS deals,
               sum(CASE WHEN side = 'BUY' THEN quantity ELSE 0 END) AS bought,
               sum(CASE WHEN side = 'SELL' THEN quantity ELSE 0 END) AS sold,
               sum(CASE WHEN side = 'BUY' THEN quantity * price ELSE 0 END) AS bought_value
          FROM deal WHERE client_name = :name GROUP BY symbol
        """,
        {"name": top_client},
    )
    assert len(expected) == len(portfolio) > 0
    for e in expected:
        p = portfolio[e["symbol"]]
        assert (p["deals"], p["bought_qty"], p["sold_qty"]) == (e["deals"], e["bought"], e["sold"]), e[
            "symbol"
        ]
        assert p["covered_sold_qty"] + p["uncovered_sold_qty"] == e["sold"]
        assert p["open_qty"] == e["bought"] - p["covered_sold_qty"] >= 0
        if e["bought"] > 0:
            assert abs(
                Decimal(p["avg_buy_price"]) - Decimal(e["bought_value"]) / Decimal(e["bought"])
            ) < Decimal("0.01")
        if p["last_close"] is not None and p["open_qty"]:
            assert abs(
                Decimal(p["market_value"]) - Decimal(p["open_qty"]) * Decimal(str(p["last_close"]))
            ) < Decimal("0.01")
    summary = clients.summary(connection, top_client)
    assert summary["deals"] == sum(e["deals"] for e in expected)
    # the company page links each counterparty to its page
    symbol = expected[0]["symbol"]
    company = client.get(f"/equities/{symbol}", headers=HTML)
    assert company.status_code in (200, 404)
    if company.status_code == 200 and top_client in company.text:
        assert f'href="/client/{top_client.replace(" ", "%20")}"' in company.text


def test_average_cost_book_realised_unrealised_and_uncovered():
    from datetime import date

    from equity_engine.service.clients import positions

    def deal(day, side, qty, price, seq=1):
        return {
            "deal_date": date(2026, 1, day),
            "kind": "BULK",
            "seq": seq,
            "symbol": "X",
            "security_name": "X Ltd",
            "side": side,
            "quantity": qty,
            "price": price,
        }

    book = positions(
        [
            deal(1, "BUY", 100, 10),
            deal(2, "BUY", 100, 20),
            deal(3, "SELL", 150, 30),
            deal(4, "SELL", 100, 35),
        ],
        {"X": {"symbol": "X", "close": 40, "trade_date": date(2026, 1, 5)}},
    )
    (x,) = book["positions"]
    # avg cost 15 after two buys; 150 sold at 30 -> realised 2250; 50 left at cost 750
    # day 4: 50 covered at 35 -> realised +1000; 50 uncovered (no disclosed buy behind them)
    assert (x["bought_qty"], x["sold_qty"], x["open_qty"]) == (200, 250, 0)
    assert x["realised"] == 2250 + 1000 and x["covered_sold_qty"] == 200
    assert x["uncovered_sold_qty"] == 50 and x["uncovered_sold_value"] == 50 * 35
    assert x["market_value"] is None and x["unrealised"] is None and x["total_pnl"] == 3250
    t = book["totals"]
    assert t["realised"] == 3250 and t["unrealised"] == 0 and t["open_positions"] == 0
    assert t["return_on_bought_pct"] == pytest.approx(3250 / 3000 * 100)

    open_book = positions(
        [deal(1, "BUY", 100, 10), deal(2, "BUY", 100, 20)],
        {"X": {"symbol": "X", "close": 40, "trade_date": date(2026, 1, 5)}},
    )
    (x,) = open_book["positions"]
    assert (x["open_qty"], x["avg_cost"], x["market_value"], x["unrealised"]) == (200, 15, 8000, 5000)
    assert x["unrealised_pct"] == pytest.approx(5000 / 3000 * 100)
    assert open_book["totals"]["market_value"] == 8000 and open_book["totals"]["total_pnl"] == 5000


def test_client_page_totals_are_the_sum_of_its_rows(client: httpx.Client, top_client: str, connection):
    from equity_engine.service import clients

    book = clients.portfolio(connection, top_client)
    rows_ = book["positions"]
    assert book["totals"]["market_value"] == pytest.approx(sum(p["market_value"] or 0 for p in rows_))
    assert book["totals"]["realised"] == pytest.approx(sum(p["realised"] for p in rows_))
    assert book["totals"]["bought_value"] == pytest.approx(sum(p["bought_value"] for p in rows_))
    page = client.get(f"/client/{top_client}", headers=HTML)
    assert page.status_code == 200 and "Portfolio value" in page.text and "Realised" in page.text
    assert 'id="client-about"' in page.text and "disclosed bulk and block deals across" in page.text
    listing = client.get("/client", params={"q": top_client.split()[0]}, headers={"HX-Request": "true"}).text
    assert "—" not in listing.split(top_client)[1].split("</tr>")[0] or book["totals"]["bought_value"] == 0


def test_client_portfolio_rows_carry_sortable_data_attributes(client: httpx.Client, top_client: str):
    page = client.get(f"/client/{top_client}", headers=HTML).text
    assert (
        'data-total-pnl="' in page
        and 'data-open-qty="' in page
        and "@click=\"sort('total_pnl', true)\"" in page
    )


def test_client_type_is_inferred_from_the_name_with_foreign_cues_before_fund():
    from equity_engine.service.client_types import (
        AIF_PMS,
        BROKER,
        CORPORATE,
        FII,
        INDIVIDUAL,
        INSURANCE,
        MUTUAL_FUND,
        PROP_TRADER,
        classify,
    )

    cases = {
        "SBI MUTUAL FUND": MUTUAL_FUND,
        "ICICI PRUDENTIAL MUTUAL FUND": MUTUAL_FUND,
        "NORGES BANK ON ACCOUNT OF THE GOVERNMENT PENSION FUND GLOBAL": FII,
        "ISHARES CORE MSCI EMERGING MARKETS ETF": FII,
        "GOLDMAN SACHS (SINGAPORE) PTE - ODI": FII,
        "SOCIETE GENERALE": FII,
        "THE MTBJ LTD. AS TRST FOR GOVRNMNT PENSION INVSTMNT FUND MTBJ400045828": FII,
        "SBI LIFE INSURANCE COMPANY LIMITED": INSURANCE,
        "KOTAKMAHINDRALIFEINSURANCECOMPANYLIMITED": INSURANCE,
        "GRAVITON RESEARCH CAPITAL LLP": PROP_TRADER,
        "HRTI PRIVATE LIMITED": PROP_TRADER,
        "ABAKKUS EMERGING OPPORTUNITIES FUND - 1": AIF_PMS,
        "SHARE INDIA SECURITIES LIMITED": BROKER,
        "SHANTI ENTREPRENEURS": CORPORATE,
        "RAKESH JHUNJHUNWALA": INDIVIDUAL,
        "VIJAY KEDIA HUF": INDIVIDUAL,
    }
    wrong = {
        name: (classify(name)["type"], want) for name, want in cases.items() if classify(name)["type"] != want
    }
    assert wrong == {}, wrong
    assert classify("SBI MUTUAL FUND")["dii"] and not classify("SOCIETE GENERALE")["dii"]
    assert "known" in classify("GRAVITON RESEARCH CAPITAL LLP")["basis"]


def test_client_meta_relevance_filter_and_query():
    from equity_engine.service.client_meta import relevant, search_query

    assert not relevant("GRAVITON RESEARCH CAPITAL LLP", "Cities in Flight")
    assert relevant("GRAVITON RESEARCH CAPITAL LLP", "Graviton Research Capital")
    assert relevant("NORGES BANK ON ACCOUNT OF THE GOVERNMENT PENSION FUND GLOBAL", "Norges Bank")
    assert relevant("SBI MUTUAL FUND", "SBI Mutual Fund") and not relevant(
        "SBI MUTUAL FUND", "Sbi Life Insurance"
    )
    assert search_query("ICICI PRUDENTIAL MUTUAL FUND") == "ICICI PRUDENTIAL mutual fund"


def test_client_list_type_filter_and_sortable_rows(client: httpx.Client):
    page = client.get("/client", headers=HTML).text
    assert (
        'id="type-counts"' in page
        and 'name="type"' in page
        and 'data-client="' in page
        and "@click=\"sort('pnl', true)\"" in page
    )
    only = client.get("/client", params={"type": "MUTUAL_FUND"}, headers={"HX-Request": "true"}).text
    assert only.count("<tr data-client") > 0 and only.count("<tr data-client") == only.count(
        'data-type="Mutual fund"'
    )
    assert client.get("/client", params={"type": "NOPE"}, headers=HTML).status_code == 422
