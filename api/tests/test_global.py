"""Global context engines (spec §120, §121): pure tests on a stub snapshot, then the live run."""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import httpx

from equity_engine.engines.global_context import GlobalResilience, HistoricalPE
from equity_engine.service.global_markets import INDEXES, context

HTML = {"Accept": "text/html"}


def _quarters(pats: list[float], roce_ebit: float = 300.0) -> list[dict]:
    out = []
    for i, pat in enumerate(pats):
        out.append(
            {
                "period_end": date(2026, 6, 30).replace(year=2026 - (i // 4), month=[6, 3, 12, 9][i % 4]),
                "broadcast_at": datetime(2026, 7, 20),
                "q_pat": Decimal(str(pat)),
                "q_revenue": Decimal("1000"),
                "q_pbt": Decimal(str(pat * 1.3)),
                "q_finance_costs": Decimal("10"),
                "bs_equity": Decimal("1500"),
                "bs_borrowings": Decimal("500"),
                "is_lender": False,
                "consolidated": True,
            }
        )
    return out


def _snap(
    world_3m: float, stress: bool, ret3: float, ret6: float, pats: list[float], market_cap: float = 20000.0
):
    price = {
        "isin": "X",
        "symbol": "XYZ",
        "close": 100 * (1 + ret3 / 100),
        "c3m": 100.0,
        "c6m": 100 / (1 + ret6 / 100) * (1 + ret3 / 100),
        "market_cap": market_cap,
    }
    return SimpleNamespace(
        global_context={
            "stress": stress,
            "median_3m_pct": world_3m,
            "indexes": {"SPX": {"ret_3m_pct": world_3m}},
        },
        price_by_isin={"X": price},
        fundamentals={"X": _quarters(pats)},
        market_median_3m_pct=-8.0,
        pe_reference={
            "X": {
                "stress": [19.0, 21.0, 18.0],
                "expansion": [30.0, 34.0, 31.0],
                "all": [19.0, 21.0, 18.0, 30.0, 34.0, 31.0, 25.0],
            }
        },
        close=lambda isin: Decimal("100"),
    )


def test_global_resilience_only_fires_in_a_world_drawdown_and_needs_quality():
    engine = GlobalResilience()
    assert engine.evaluate(_snap(-2.0, False, 12.0, 15.0, [120, 115, 110, 105, 100, 95, 90, 85])) == []
    strong = engine.evaluate(_snap(-9.0, True, 4.0, 6.0, [120, 115, 110, 105, 100, 95, 90, 85]))
    assert [s.signal_type for s in strong] == ["RESILIENT_IN_GLOBAL_SELLOFF"] and strong[
        0
    ].stage == "CONFIRMED"
    assert strong[0].evidence["gap_points"] == 13.0 and strong[0].evidence["roce_pct"] is not None
    # beat the world but profit shrinking: not resilient, and not a beta casualty either
    assert engine.evaluate(_snap(-9.0, True, 4.0, 6.0, [80, 85, 90, 95, 100, 105, 110, 115])) == []
    beta = engine.evaluate(_snap(-9.0, True, -22.0, -25.0, [80, 85, 90, 95, 100, 105, 110, 115]))
    assert [s.signal_type for s in beta] == ["GLOBAL_BETA_SELLOFF"]


def test_historical_pe_reads_todays_pe_against_stress_and_expansion_dates():
    engine = HistoricalPE()
    # TTM PAT 450 on market cap 7,000 -> P/E 15.6, under 0.9 × 19 (stress median) with profit growing
    below = engine.evaluate(
        _snap(-9.0, True, 0.0, 0.0, [120, 115, 110, 105, 100, 95, 90, 85], market_cap=7000.0)
    )
    assert [s.signal_type for s in below] == ["BELOW_RECESSION_PE"]
    assert below[0].evidence["recession_pe_median"] == 19.0 and below[0].evidence["pe_now"] == 15.6
    # P/E 36 at expansion levels with profit shrinking in a stressed market
    rich = engine.evaluate(
        _snap(-9.0, True, 0.0, 0.0, [80, 85, 90, 95, 100, 105, 110, 115], market_cap=12600.0)
    )
    assert [s.signal_type for s in rich] == ["PE_YET_TO_DERATE"]
    # same rich P/E but the market is calm: nothing
    calm = _snap(2.0, False, 0.0, 0.0, [80, 85, 90, 95, 100, 105, 110, 115], market_cap=12600.0)
    calm.market_median_3m_pct = 4.0
    assert engine.evaluate(calm) == []


def test_global_indexes_loaded_and_in_the_regime(client: httpx.Client, connection):
    from equity_engine.db import rows

    counts = {
        r["index_code"]: (r["n"], r["first"])
        for r in rows(
            connection,
            "SELECT index_code, count(*) n, min(trade_date) first FROM global_index_daily GROUP BY 1",
        )
    }
    assert set(counts) == set(INDEXES), counts
    assert all(n > 2000 for n, _ in counts.values()) and counts["SPX"][1] < date(1995, 1, 1)
    world = context(connection, date(2026, 10, 1))
    assert (
        set(world["indexes"]) == set(INDEXES)
        and world["median_3m_pct"] is not None
        and isinstance(world["stress"], bool)
    )
    regime = rows(
        connection,
        "SELECT m.* FROM market_regime m JOIN engine_run r USING (run_id) WHERE r.kind = 'LIVE' ORDER BY r.started_at DESC LIMIT 1",
    )[0]
    assert regime["global_indexes"] is not None and regime["global_stress"] is not None
    page = client.get("/", headers=HTML).text
    assert 'id="world-tile"' in page and 'id="world-meaning"' in page and "S&amp;P 500" in page
    catalogue = {e["engine_key"]: e for e in client.get("/api/engine").json()["engines"]}
    assert (
        catalogue["global_resilience"]["status"] == "LIVE" and catalogue["historical_pe"]["status"] == "LIVE"
    )
