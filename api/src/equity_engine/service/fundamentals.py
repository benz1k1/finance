"""
Canonical line items (spec §5, §57) from the facts a results XBRL carries, per taxonomy.

NSE's four results taxonomies name the same concept differently (``ProfitLossForPeriod`` vs
``ProfitLossForThePeriod``; banks have no revenue line at all). ``canonical`` maps a filing's
facts to the ``fin_quarter`` columns once, at load time. Everything is rupees as filed; nothing
is scaled. A concept the filing does not carry is None, never 0.

Reporting rules applied here (§57): the quarter columns are the quarter itself (NSE files Q4
figures directly, so no balancing is needed); year-to-date and balance-sheet columns are kept as
filed and are NULL in filings that do not carry them (most companies publish a balance sheet
only at the half-year and the year end).
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import Connection

from equity_engine.db import rows
from equity_engine.parsers.models import FinFacts

Facts = dict[str, dict[str, Decimal]]  # period_kind -> item -> value


def _by_kind(parsed: FinFacts) -> Facts:
    out: Facts = {"Q": {}, "YTD": {}, "INSTANT": {}}
    for fact in parsed.facts:
        out[fact.period_kind][fact.item] = fact.value
    return out


def _first(items: dict[str, Decimal], *names: str) -> Decimal | None:
    for name in names:
        if name in items:
            return items[name]
    return None


def _sum(items: dict[str, Decimal], *names: str) -> Decimal | None:
    found = [items[name] for name in names if name in items]
    return sum(found, Decimal(0)) if found else None


def canonical(parsed: FinFacts) -> dict[str, Any]:
    facts = _by_kind(parsed)
    q, ytd, bs = facts["Q"], facts["YTD"], facts["INSTANT"]
    taxonomy = parsed.taxonomy
    is_bank = taxonomy == "BANKING"
    is_lender = taxonomy in ("BANKING", "NBFC")
    row: dict[str, Any] = {"taxonomy": taxonomy, "is_bank": is_bank, "is_lender": is_lender}

    if is_bank:
        row.update(
            q_revenue=_first(q, "InterestEarned"),
            q_other_income=_first(q, "OtherIncome"),
            q_total_income=_first(q, "Income"),
            q_expenses=_first(q, "ExpenditureExcludingProvisionsAndContingencies"),
            q_employee_cost=_first(q, "EmployeesCost"),
            q_material_cost=None,
            q_finance_costs=_first(q, "InterestExpended"),
            q_depreciation=None,
            q_exceptional=_first(q, "ExceptionalItems", "ExtraordinaryItems"),
            q_pbt=_first(q, "ProfitLossFromOrdinaryActivitiesBeforeTax"),
            q_tax=_first(q, "TaxExpense"),
            q_pat=_first(
                q,
                "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates",
                "ProfitLossForThePeriod",
            ),
            q_pat_owners=_first(
                q,
                "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates",
                "ProfitLossForThePeriod",
            ),
            q_eps_basic=_first(
                q,
                "BasicEarningsPerShareAfterExtraordinaryItems",
                "BasicEarningsPerShareBeforeExtraordinaryItems",
            ),
            q_eps_diluted=_first(
                q,
                "DilutedEarningsPerShareAfterExtraordinaryItems",
                "DilutedEarningsPerShareBeforeExtraordinaryItems",
            ),
            q_interest_earned=_first(q, "InterestEarned"),
            q_interest_expended=_first(q, "InterestExpended"),
            q_operating_profit=_first(q, "OperatingProfitBeforeProvisionAndContingencies"),
            q_provisions=_first(q, "ProvisionsOtherThanTaxAndContingencies"),
            q_gnpa_pct=_first(q, "PercentageOfGrossNpa"),
            ytd_revenue=_first(ytd, "InterestEarned"),
            ytd_pat=_first(
                ytd,
                "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates",
                "ProfitLossForThePeriod",
            ),
            bs_equity=_sum(bs, "Capital", "ReservesAndSurplus"),
            bs_share_capital=_first(bs, "Capital"),
            bs_borrowings=_first(bs, "Borrowings"),
            bs_cash=_sum(
                bs, "CashAndBalancesWithReserveBankOfIndia", "BalancesWithBanksAndMoneyAtCallAndShortNotice"
            ),
            bs_total_assets=_first(bs, "CapitalAndLiabilities"),
            bs_deposits=_first(bs, "Deposits"),
            bs_advances=_first(bs, "Advances"),
        )
    elif taxonomy == "NONINDAS":
        row.update(
            q_revenue=_first(q, "RevenueFromOperations"),
            q_other_income=_first(q, "OtherIncome"),
            q_total_income=_first(q, "Revenue"),
            q_expenses=_first(q, "Expenses"),
            q_employee_cost=_first(q, "EmployeeBenefitExpense"),
            q_material_cost=_sum(
                q,
                "CostOfMaterialsConsumed",
                "PurchasesOfStockInTrade",
                "ChangesInInventoriesOfFinishedGoodsWorkInProgressAndStockInTrade",
            ),
            q_finance_costs=_first(q, "FinanceCosts"),
            q_depreciation=_first(q, "DepreciationAndAmortisationExpense"),
            q_exceptional=_first(q, "ExceptionalItems"),
            q_pbt=_first(q, "ProfitBeforeTax"),
            q_tax=_first(q, "TaxExpense"),
            q_pat=_first(q, "ProfitLossForThePeriod", "ProfitLossForThePeriodFromContinuingOperations"),
            q_pat_owners=_first(
                q, "ProfitLossForThePeriod", "ProfitLossForThePeriodFromContinuingOperations"
            ),
            q_eps_basic=_first(
                q,
                "BasicEarningsPerShareAfterExtraordinaryItems",
                "BasicEarningsPerShareBeforeExtraordinaryItems",
            ),
            q_eps_diluted=_first(
                q,
                "DilutedEarningsPerShareAfterExtraordinaryItems",
                "DilutedEarningsPerShareBeforeExtraordinaryItems",
            ),
            ytd_revenue=_first(ytd, "RevenueFromOperations"),
            ytd_pat=_first(ytd, "ProfitLossForThePeriod"),
            ytd_cfo=_first(ytd, "CashFlowsFromUsedInOperatingActivities"),
            bs_equity=_first(bs, "ShareholdersFunds"),
            bs_share_capital=_first(bs, "ShareCapital"),
            bs_borrowings=_sum(bs, "LongTermBorrowings", "ShortTermBorrowings"),
            bs_cash=_first(bs, "CashAndBankBalances", "CashAndCashEquivalents"),
            bs_total_assets=_first(bs, "EquityAndLiabilities"),
            bs_current_assets=_first(bs, "CurrentAssets"),
            bs_current_liabilities=_first(bs, "CurrentLiabilities"),
            bs_inventories=_first(bs, "Inventories"),
            bs_receivables=_first(bs, "TradeReceivables"),
        )
    else:  # INDAS, CAPMKT (the integrated filing uses the Ind-AS names), NBFC
        row.update(
            q_revenue=_first(q, "RevenueFromOperations"),
            q_other_income=_first(q, "OtherIncome"),
            q_total_income=_first(q, "Income"),
            q_expenses=_first(q, "Expenses"),
            q_employee_cost=_first(q, "EmployeeBenefitExpense"),
            q_material_cost=_sum(
                q,
                "CostOfMaterialsConsumed",
                "PurchasesOfStockInTrade",
                "ChangesInInventoriesOfFinishedGoodsWorkInProgressAndStockInTrade",
            ),
            q_finance_costs=_first(q, "FinanceCosts"),
            q_depreciation=_first(q, "DepreciationDepletionAndAmortisationExpense"),
            q_exceptional=_first(q, "ExceptionalItemsBeforeTax"),
            q_pbt=_first(q, "ProfitBeforeTax"),
            q_tax=_first(q, "TaxExpense"),
            q_pat=_first(q, "ProfitLossForPeriod", "ProfitLossForPeriodFromContinuingOperations"),
            q_pat_owners=_first(q, "ProfitOrLossAttributableToOwnersOfParent", "ProfitLossForPeriod"),
            q_eps_basic=_first(
                q,
                "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
                "BasicEarningsLossPerShareFromContinuingOperations",
            ),
            q_eps_diluted=_first(
                q,
                "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
                "DilutedEarningsLossPerShareFromContinuingOperations",
            ),
            q_interest_earned=_first(q, "InterestEarned") if is_lender else None,
            ytd_revenue=_first(ytd, "RevenueFromOperations"),
            ytd_pat=_first(ytd, "ProfitLossForPeriod"),
            ytd_cfo=_first(ytd, "CashFlowsFromUsedInOperatingActivities"),
            ytd_capex=_sum(
                ytd,
                "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",
                "PurchaseOfIntangibleAssetsUnderDevelopment",
            ),
            ytd_dividends_paid=_first(ytd, "DividendsPaidClassifiedAsFinancingActivities"),
            ytd_buyback=_first(ytd, "PaymentsToAcquireOrRedeemEntitysShares"),
            ytd_interest_paid=_first(ytd, "InterestPaidClassifiedAsFinancingActivities"),
            bs_equity=_first(bs, "Equity", "EquityAttributableToOwnersOfParent"),
            bs_share_capital=_first(bs, "EquityShareCapital"),
            bs_borrowings=_sum(bs, "BorrowingsCurrent", "BorrowingsNoncurrent")
            if not is_lender
            else _sum(
                bs,
                "DebtSecurities",
                "BorrowingsOtherThanDebtSecurities",
                "Deposits",
                "SubordinatedLiabilities",
                "Borrowings",
            ),
            bs_cash=_first(bs, "CashAndCashEquivalents"),
            bs_total_assets=_first(bs, "Assets"),
            bs_current_assets=_first(bs, "CurrentAssets"),
            bs_current_liabilities=_first(bs, "CurrentLiabilities"),
            bs_inventories=_first(bs, "Inventories"),
            bs_receivables=_first(bs, "TradeReceivablesCurrent", "TradeReceivables"),
        )
    row["face_value"] = _first(q, "FaceValueOfEquityShareCapital")
    return row


QUARTER_COLUMNS = (
    "q_revenue",
    "q_other_income",
    "q_total_income",
    "q_expenses",
    "q_employee_cost",
    "q_material_cost",
    "q_finance_costs",
    "q_depreciation",
    "q_exceptional",
    "q_pbt",
    "q_tax",
    "q_pat",
    "q_pat_owners",
    "q_eps_basic",
    "q_eps_diluted",
    "q_interest_earned",
    "q_interest_expended",
    "q_operating_profit",
    "q_provisions",
    "q_gnpa_pct",
    "ytd_revenue",
    "ytd_pat",
    "ytd_cfo",
    "ytd_capex",
    "ytd_dividends_paid",
    "ytd_buyback",
    "ytd_interest_paid",
    "bs_equity",
    "bs_share_capital",
    "bs_borrowings",
    "bs_cash",
    "bs_total_assets",
    "bs_current_assets",
    "bs_current_liabilities",
    "bs_inventories",
    "bs_receivables",
    "bs_deposits",
    "bs_advances",
    "face_value",
)


def ebitda(quarter: dict[str, Any]) -> float | None:
    """Operating EBITDA = PBT + finance costs + depreciation − other income + exceptional charges
    (exceptional items are added back when negative). Not defined for banks."""
    if quarter.get("is_bank") or quarter.get("q_pbt") is None:
        return None
    value = float(quarter["q_pbt"])
    value += float(quarter.get("q_finance_costs") or 0) if not quarter.get("is_lender") else 0.0
    value += float(quarter.get("q_depreciation") or 0)
    value -= float(quarter.get("q_other_income") or 0)
    exceptional = quarter.get("q_exceptional")
    if exceptional is not None and float(exceptional) < 0:
        value -= float(exceptional)
    return value


# ------------------------------------------------------------------ read side (company page, API)


def quarters(connection: Connection, symbol: str, limit: int = 12) -> list[dict[str, Any]]:
    """Newest first; the newest broadcast per quarter, consolidated preferred. Adds EBITDA and the
    margins the page shows."""
    found = rows(
        connection,
        """
        WITH known AS (
            SELECT DISTINCT ON (q.period_end, q.consolidated) q.*
              FROM fin_quarter q WHERE q.symbol = :symbol
             ORDER BY q.period_end, q.consolidated, q.broadcast_at DESC
        ),
        preferred AS (SELECT DISTINCT ON (k.period_end) k.* FROM known k ORDER BY k.period_end, k.consolidated DESC)
        SELECT * FROM preferred ORDER BY period_end DESC LIMIT :limit
        """,
        {"symbol": symbol, "limit": limit},
    )
    for q in found:
        for key, value in list(q.items()):
            if isinstance(value, Decimal):
                q[key] = float(value)
        q["ebitda"] = ebitda(q)
        revenue = q.get("q_revenue")
        q["ebitda_margin_pct"] = (
            round(q["ebitda"] / revenue * 100, 1) if q["ebitda"] is not None and revenue else None
        )
        q["pat_margin_pct"] = (
            round(q["q_pat"] / revenue * 100, 1) if q.get("q_pat") is not None and revenue else None
        )
    return found


def ttm(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Trailing twelve months from the newest four quarters, plus growth against the four before."""

    def total(key: str, offset: int = 0) -> float | None:
        window = history[offset : offset + 4]
        if len(window) < 4 or any(q.get(key) is None for q in window):
            return None
        return float(sum(q[key] for q in window))

    def growth(now: float | None, then: float | None) -> float | None:
        if now is None or then is None or then <= 0:
            return None
        return round((now / then - 1) * 100, 1)

    revenue, pat = total("q_revenue"), total("q_pat")
    ebitda_values = [q["ebitda"] for q in history[:4]]
    ttm_ebitda = (
        float(sum(v for v in ebitda_values if v is not None))
        if len(ebitda_values) == 4 and None not in ebitda_values
        else None
    )
    return {
        "revenue": revenue,
        "pat": pat,
        "ebitda": ttm_ebitda,
        "eps": total("q_eps_basic"),
        "revenue_growth_pct": growth(revenue, total("q_revenue", 4)),
        "pat_growth_pct": growth(pat, total("q_pat", 4)),
        "ebitda_margin_pct": round(ttm_ebitda / revenue * 100, 1)
        if ttm_ebitda is not None and revenue
        else None,
        "quarters": min(4, len(history)),
    }


def balance_sheet(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The newest quarter that carries a balance sheet."""
    for q in history:
        if q.get("bs_equity") is not None:
            return {k: q[k] for k in q if k.startswith("bs_")} | {"period_end": q["period_end"]}
    return None


def multiples(market_cap: float | None, history: list[dict[str, Any]]) -> dict[str, Any]:
    if not market_cap or not history:
        return {}
    trailing = ttm(history)
    sheet = balance_sheet(history)
    pat = trailing["pat"]
    equity = sheet["bs_equity"] if sheet else None
    debt = (sheet or {}).get("bs_borrowings") or 0.0
    cash = (sheet or {}).get("bs_cash") or 0.0
    ev = market_cap + debt - cash
    return {
        "pe": round(market_cap / pat, 1) if pat and pat > 0 else None,
        "pb": round(market_cap / equity, 2) if equity and equity > 0 else None,
        "ev_ebitda": round(ev / trailing["ebitda"], 1)
        if trailing["ebitda"] and trailing["ebitda"] > 0 and not history[0].get("is_lender")
        else None,
        "earnings_yield_pct": round(pat / market_cap * 100, 2) if pat else None,
        "market_cap": market_cap,
    }


_INDUSTRY_PE = """
    WITH me AS (
        SELECT DISTINCT ON (c.isin) c.isin, c.industry FROM index_constituent_snapshot c
         WHERE c.isin = :isin AND c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot)
         ORDER BY c.isin, CASE c.index_code WHEN 'nifty500' THEN 0 ELSE 1 END
    ),
    members AS (
        SELECT DISTINCT c.isin, s.nse_symbol AS symbol FROM index_constituent_snapshot c
          JOIN me ON me.industry = c.industry JOIN security s ON s.isin = c.isin
         WHERE c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot) AND c.index_code = 'nifty500'
    ),
    mcap AS (
        SELECT DISTINCT ON (p.isin) p.isin, p.market_cap FROM price_daily p JOIN members m USING (isin)
         WHERE p.market_cap IS NOT NULL AND p.series IN ('EQ', 'SM') ORDER BY p.isin, p.trade_date DESC
    ),
    quarters AS (
        SELECT DISTINCT ON (q.symbol, q.period_end) q.symbol, q.period_end, q.q_pat
          FROM fin_quarter q JOIN members m ON m.symbol = q.symbol
         WHERE q.q_pat IS NOT NULL ORDER BY q.symbol, q.period_end DESC, q.consolidated DESC, q.broadcast_at DESC
    ),
    ranked AS (SELECT *, row_number() OVER (PARTITION BY symbol ORDER BY period_end DESC) AS rn FROM quarters),
    ttm AS (SELECT symbol, sum(q_pat) AS pat, count(*) AS n FROM ranked WHERE rn <= 4 GROUP BY symbol HAVING count(*) = 4)
    SELECT (SELECT industry FROM me) AS industry, m.symbol, mc.market_cap / t.pat AS pe
      FROM members m JOIN mcap mc USING (isin) JOIN ttm t USING (symbol)
     WHERE t.pat > 0
"""


def industry_pe(connection: Connection, isin: str) -> dict[str, Any] | None:
    """The security's Nifty 500 industry, the median trailing P/E of its members with positive TTM
    profit, and how many members that median rests on. None when the industry has under five."""
    found = rows(connection, _INDUSTRY_PE, {"isin": isin})
    pes = sorted(float(r["pe"]) for r in found)
    if len(pes) < 5:
        return None
    middle = len(pes) // 2
    median_pe = pes[middle] if len(pes) % 2 else (pes[middle - 1] + pes[middle]) / 2
    return {"industry": found[0]["industry"], "median_pe": round(median_pe, 1), "members": len(pes)}


_PE_TABLE = """
    WITH members AS (
        SELECT DISTINCT ON (c.isin) c.isin, c.industry, s.nse_symbol AS symbol
          FROM index_constituent_snapshot c JOIN security s ON s.isin = c.isin
         WHERE c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot) AND c.index_code = 'nifty500'
         ORDER BY c.isin
    ),
    mcap AS (
        SELECT DISTINCT ON (p.isin) p.isin, p.market_cap, p.close FROM price_daily p JOIN members m USING (isin)
         WHERE p.market_cap IS NOT NULL AND p.series IN ('EQ', 'SM') ORDER BY p.isin, p.trade_date DESC
    ),
    quarters AS (
        SELECT DISTINCT ON (q.symbol, q.period_end) q.symbol, q.period_end, q.q_pat
          FROM fin_quarter q JOIN members m ON m.symbol = q.symbol
         WHERE q.q_pat IS NOT NULL ORDER BY q.symbol, q.period_end DESC, q.consolidated DESC, q.broadcast_at DESC
    ),
    ranked AS (SELECT *, row_number() OVER (PARTITION BY symbol ORDER BY period_end DESC) AS rn FROM quarters),
    ttm AS (SELECT symbol, sum(q_pat) AS pat FROM ranked WHERE rn <= 4 GROUP BY symbol HAVING count(*) = 4),
    pe AS (
        SELECT m.isin, m.symbol, m.industry, mc.close, CASE WHEN t.pat > 0 THEN mc.market_cap / t.pat END AS pe
          FROM members m JOIN mcap mc USING (isin) LEFT JOIN ttm t USING (symbol)
    ),
    industry AS (
        SELECT industry, percentile_cont(0.5) WITHIN GROUP (ORDER BY pe) AS median_pe, count(pe) AS members
          FROM pe WHERE pe IS NOT NULL GROUP BY industry HAVING count(pe) >= 5
    )
    SELECT p.symbol, p.industry, round(CAST(p.pe AS numeric), 1) AS pe, round(CAST(i.median_pe AS numeric), 1) AS sector_pe, i.members
      FROM pe p LEFT JOIN industry i USING (industry)
"""


def pe_table(connection: Connection) -> dict[str, dict[str, Any]]:
    """Per universe symbol: trailing P/E, its industry, and the industry's median P/E (members with
    positive TTM profit, at least five). One query for the list pages."""
    out = {}
    for r in rows(connection, _PE_TABLE):
        pe, sector = (
            (float(r["pe"]) if r["pe"] is not None else None),
            (float(r["sector_pe"]) if r["sector_pe"] is not None else None),
        )
        out[r["symbol"]] = {
            "pe": pe,
            "industry": r["industry"],
            "sector_pe": sector,
            "members": r["members"],
            "gap_pct": round((sector / pe - 1) * 100, 1) if pe and sector else None,
        }
    return out
