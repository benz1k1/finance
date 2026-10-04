"""
Silver loaders: validated records in, rows upserted (spec §83). Every loader is idempotent —
loading the same file twice leaves the same rows — because the schema is rebuilt from the cached
files, and a rebuild is the normal way to fix a parsing bug.

Each takes ``(connection, records, raw_id, day)`` and returns the number of rows written.
"""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import Connection

from equity_engine.db import execute, execute_many, scalar
from equity_engine.parsers.models import (
    BandRow,
    BoardMeetingRow,
    BrsrFilingRow,
    CompanyProfileRow,
    CreditRatingRow,
    DailyReportsRows,
    DealRow,
    DeliveryRow,
    DerivativeOiRow,
    DocumentRow,
    FinFacts,
    FinFilingRow,
    IndexRow,
    MarketCapRow,
    PriceRow,
    SecurityRow,
    ShareholdingFilingRow,
    ShareholdingPatternRow,
    SurveillanceRow,
)
from equity_engine.service import fundamentals


def prices(connection: Connection, records: Sequence[PriceRow], raw_id: str, day: date) -> int:
    execute_many(
        connection,
        """
        INSERT INTO price_daily (isin, trade_date, series, symbol, open, high, low, close, last,
                                 prev_close, volume, turnover, trades, raw_id)
        VALUES (:isin, :trade_date, :series, :symbol, :open, :high, :low, :close, :last,
                :prev_close, :volume, :turnover, :trades, :raw_id)
        ON CONFLICT (isin, trade_date, series) DO UPDATE SET
            symbol = EXCLUDED.symbol, open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, last = EXCLUDED.last, prev_close = EXCLUDED.prev_close,
            volume = EXCLUDED.volume, turnover = EXCLUDED.turnover, trades = EXCLUDED.trades,
            raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"raw_id": raw_id} for record in records],
    )
    return len(records)


def delivery(connection: Connection, records: Sequence[DeliveryRow], raw_id: str, day: date) -> int:
    """Fill delivery onto that day's price rows. The delivery file has no ISIN, so the match is
    symbol + series within the one trade date, where a symbol is unambiguous.

    Trade-for-trade series (BE, BZ) are absent from the file by construction — every trade there
    is delivered — and stay NULL rather than being invented as 100%."""
    priced = scalar(connection, "SELECT count(*) FROM price_daily WHERE trade_date = :d", {"d": day})
    if not priced:
        raise ValueError(f"delivery for {day} cannot be loaded before that day's prices")
    execute(
        connection,
        "CREATE TEMP TABLE delivery_stage (symbol text, series text, traded_qty bigint, "
        "deliv_qty bigint, deliv_pct numeric(6, 2)) ON COMMIT DROP",
    )
    execute_many(
        connection,
        "INSERT INTO delivery_stage VALUES (:symbol, :series, :traded_qty, :deliv_qty, :deliv_pct)",
        [record.model_dump(exclude={"trade_date"}) for record in records],
    )
    return execute(
        connection,
        """
        UPDATE price_daily p
           SET deliv_traded_qty = s.traded_qty, deliv_qty = s.deliv_qty, deliv_pct = s.deliv_pct,
               delivery_raw_id = :raw_id
          FROM delivery_stage s
         WHERE p.trade_date = :d AND p.symbol = s.symbol AND p.series = s.series
        """,
        {"raw_id": raw_id, "d": day},
    )


def market_caps(connection: Connection, records: Sequence[MarketCapRow], raw_id: str, day: date) -> int:
    """Fill issue size and market cap onto that day's price rows, matched like delivery: symbol +
    series within the one trade date. An empty list (a bundle from before NSE published the
    file) writes nothing."""
    if not records:
        return 0
    execute(
        connection,
        "CREATE TEMP TABLE market_cap_stage (symbol text, series text, issue_size bigint, "
        "market_cap numeric(22, 2)) ON COMMIT DROP",
    )
    execute_many(
        connection,
        "INSERT INTO market_cap_stage VALUES (:symbol, :series, :issue_size, :market_cap)",
        [record.model_dump(include={"symbol", "series", "issue_size", "market_cap"}) for record in records],
    )
    return execute(
        connection,
        """
        UPDATE price_daily p
           SET issue_size = s.issue_size, market_cap = s.market_cap, reports_raw_id = :raw_id
          FROM market_cap_stage s
         WHERE p.trade_date = :d AND p.symbol = s.symbol AND p.series = s.series
        """,
        {"raw_id": raw_id, "d": day},
    )


def securities(connection: Connection, records: Sequence[SecurityRow], raw_id: str, day: date) -> int:
    """Upsert by ISIN. A snapshot older than the one a row already came from does not overwrite
    it, so replaying cached snapshots in any order ends in the newest state."""
    execute_many(
        connection,
        """
        INSERT INTO security (isin, nse_symbol, name, series, segment, listing_date, face_value,
                              paid_up_value, master_date, raw_id)
        VALUES (:isin, :symbol, :name, :series, :segment, :listing_date, :face_value,
                :paid_up_value, :master_date, :raw_id)
        ON CONFLICT (isin) DO UPDATE SET
            nse_symbol = EXCLUDED.nse_symbol, name = EXCLUDED.name, series = EXCLUDED.series,
            segment = EXCLUDED.segment, listing_date = EXCLUDED.listing_date,
            face_value = EXCLUDED.face_value, paid_up_value = EXCLUDED.paid_up_value,
            master_date = EXCLUDED.master_date, raw_id = EXCLUDED.raw_id
        WHERE security.master_date <= EXCLUDED.master_date
        """,
        [record.model_dump() | {"master_date": day, "raw_id": raw_id} for record in records],
    )
    return len(records)


def bands(connection: Connection, records: Sequence[BandRow], raw_id: str, day: date) -> int:
    execute_many(
        connection,
        """
        INSERT INTO series_band_snapshot (snapshot_date, symbol, series, band, remarks, raw_id)
        VALUES (:snapshot_date, :symbol, :series, :band, :remarks, :raw_id)
        ON CONFLICT (snapshot_date, symbol, series) DO UPDATE SET
            band = EXCLUDED.band, remarks = EXCLUDED.remarks, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"snapshot_date": day, "raw_id": raw_id} for record in records],
    )
    return len(records)


def deals(connection: Connection, records: Sequence[DealRow], raw_id: str, day: date) -> int:
    execute_many(
        connection,
        """
        INSERT INTO deal (kind, deal_date, seq, symbol, security_name, client_name, side, quantity,
                          price, remarks, raw_id)
        VALUES (:kind, :deal_date, :seq, :symbol, :security_name, :client_name, :side, :quantity,
                :price, :remarks, :raw_id)
        ON CONFLICT (kind, deal_date, seq) DO UPDATE SET
            symbol = EXCLUDED.symbol, security_name = EXCLUDED.security_name,
            client_name = EXCLUDED.client_name, side = EXCLUDED.side, quantity = EXCLUDED.quantity,
            price = EXCLUDED.price, remarks = EXCLUDED.remarks, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"raw_id": raw_id} for record in records],
    )
    return len(records)


def index_constituents(connection: Connection, records: Sequence[IndexRow], raw_id: str, day: date) -> int:
    execute_many(
        connection,
        """
        INSERT INTO index_constituent_snapshot (snapshot_date, index_code, isin, symbol, company_name,
                                                industry, raw_id)
        VALUES (:snapshot_date, :index_code, :isin, :symbol, :company_name, :industry, :raw_id)
        ON CONFLICT (snapshot_date, index_code, isin) DO UPDATE SET
            symbol = EXCLUDED.symbol, company_name = EXCLUDED.company_name,
            industry = EXCLUDED.industry, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"snapshot_date": day, "raw_id": raw_id} for record in records],
    )
    return len(records)


def surveillance(connection: Connection, records: Sequence[SurveillanceRow], raw_id: str, day: date) -> int:
    execute_many(
        connection,
        """
        INSERT INTO surveillance_snapshot (snapshot_date, list_code, isin, symbol, company_name, stage,
                                           surv_code, surv_desc, raw_id)
        VALUES (:snapshot_date, :list_code, :isin, :symbol, :company_name, :stage, :surv_code,
                :surv_desc, :raw_id)
        ON CONFLICT (snapshot_date, list_code, isin) DO UPDATE SET
            symbol = EXCLUDED.symbol, company_name = EXCLUDED.company_name, stage = EXCLUDED.stage,
            surv_code = EXCLUDED.surv_code, surv_desc = EXCLUDED.surv_desc, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"snapshot_date": day, "raw_id": raw_id} for record in records],
    )
    return len(records)


def shareholding_filings(
    connection: Connection, records: Sequence[ShareholdingFilingRow], raw_id: str, day: date
) -> int:
    execute_many(
        connection,
        """
        INSERT INTO shareholding_filing (record_id, symbol, isin, company_name, period_end, promoter_pct,
                                         public_pct, broadcast_at, revised, xbrl_url, raw_id)
        VALUES (:record_id, :symbol, :isin, :company_name, :period_end, :promoter_pct,
                :public_pct, :broadcast_at, :revised, :xbrl_url, :raw_id)
        ON CONFLICT (record_id) DO UPDATE SET
            symbol = EXCLUDED.symbol, isin = EXCLUDED.isin, company_name = EXCLUDED.company_name,
            period_end = EXCLUDED.period_end, promoter_pct = EXCLUDED.promoter_pct,
            public_pct = EXCLUDED.public_pct, broadcast_at = EXCLUDED.broadcast_at,
            revised = EXCLUDED.revised, xbrl_url = EXCLUDED.xbrl_url, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"raw_id": raw_id} for record in records],
    )
    return len(records)


def shareholding_pattern(
    connection: Connection, record: ShareholdingPatternRow, raw_id: str, record_id: str, symbol: str
) -> None:
    """One filing's breakdown. ``symbol`` is the filing list's, not the XBRL's: see the model."""
    fields = record.model_dump(exclude={"symbol", "isin"})
    columns = ", ".join(fields)
    values = ", ".join(f":{name}" for name in fields)
    updates = ", ".join(f"{name} = EXCLUDED.{name}" for name in fields)
    execute(
        connection,
        f"""
        INSERT INTO shareholding_pattern (record_id, symbol, raw_id, {columns})
        VALUES (:record_id, :symbol, :raw_id, {values})
        ON CONFLICT (record_id) DO UPDATE SET symbol = EXCLUDED.symbol, raw_id = EXCLUDED.raw_id, {updates}
        """,
        fields | {"record_id": record_id, "symbol": symbol, "raw_id": raw_id},
    )


def company_profile(
    connection: Connection, record: CompanyProfileRow, raw_id: str, filing: BrsrFilingRow
) -> bool:
    """Upsert one company-year. A filing older than the one already stored is ignored, so the
    newest submission for a financial year wins whatever order they are loaded in."""
    key = {"symbol": filing.symbol, "fy_to": filing.fy_to}
    fields = record.model_dump(exclude={"activities", "products"})
    columns = ", ".join(fields)
    values = ", ".join(f":{name}" for name in fields)
    updates = ", ".join(f"{name} = EXCLUDED.{name}" for name in fields)
    written = execute(
        connection,
        f"""
        INSERT INTO company_profile (symbol, fy_to, annual_report_url, submitted_on, raw_id, {columns})
        VALUES (:symbol, :fy_to, :annual_report_url, :submitted_on, :raw_id, {values})
        ON CONFLICT (symbol, fy_to) DO UPDATE SET
            annual_report_url = EXCLUDED.annual_report_url, submitted_on = EXCLUDED.submitted_on,
            raw_id = EXCLUDED.raw_id, {updates}
        WHERE company_profile.submitted_on <= EXCLUDED.submitted_on
        """,
        fields
        | key
        | {
            "annual_report_url": filing.annual_report_url,
            "submitted_on": filing.submitted_on,
            "raw_id": raw_id,
        },
    )
    if not written:
        return False
    execute(connection, "DELETE FROM company_activity WHERE symbol = :symbol AND fy_to = :fy_to", key)
    execute(connection, "DELETE FROM company_product WHERE symbol = :symbol AND fy_to = :fy_to", key)
    execute_many(
        connection,
        "INSERT INTO company_activity (symbol, fy_to, seq, main_activity, description, turnover_pct) "
        "VALUES (:symbol, :fy_to, :seq, :main_activity, :description, :turnover_pct)",
        [activity.model_dump() | key for activity in record.activities],
    )
    execute_many(
        connection,
        "INSERT INTO company_product (symbol, fy_to, seq, product, nic_code, turnover_pct) "
        "VALUES (:symbol, :fy_to, :seq, :product, :nic_code, :turnover_pct)",
        [product.model_dump() | key for product in record.products],
    )
    return True


def daily_reports(connection: Connection, bundle: DailyReportsRows, raw_id: str, day: date) -> int:
    """The three tables fed by one daily reports bundle. Actions are keyed by the action itself
    (the same row appears in every bundle until its ex-date), so a reload only moves last_seen."""
    written = market_caps(connection, bundle.market_caps, raw_id, day)
    execute_many(
        connection,
        """
        INSERT INTO corporate_action (symbol, series, ex_date, purpose, security_name, record_date, bc_start, bc_end,
                                      nd_start, nd_end, kind, amount, adjust_factor, first_seen, last_seen, raw_id)
        VALUES (:symbol, :series, :ex_date, :purpose, :security_name, :record_date, :bc_start, :bc_end,
                :nd_start, :nd_end, :kind, :amount, :adjust_factor, :day, :day, :raw_id)
        ON CONFLICT (symbol, series, ex_date, purpose) DO UPDATE SET
            record_date = coalesce(EXCLUDED.record_date, corporate_action.record_date),
            kind = EXCLUDED.kind, amount = EXCLUDED.amount, adjust_factor = EXCLUDED.adjust_factor,
            first_seen = least(corporate_action.first_seen, EXCLUDED.first_seen),
            last_seen = greatest(corporate_action.last_seen, EXCLUDED.last_seen),
            raw_id = CASE WHEN EXCLUDED.first_seen < corporate_action.first_seen THEN EXCLUDED.raw_id ELSE corporate_action.raw_id END
        """,
        [record.model_dump() | {"day": day, "raw_id": raw_id} for record in bundle.actions],
    )
    execute_many(
        connection,
        """
        INSERT INTO circuit_hit (symbol, series, trade_date, side, raw_id)
        VALUES (:symbol, :series, :day, :side, :raw_id)
        ON CONFLICT (symbol, series, trade_date) DO UPDATE SET side = EXCLUDED.side, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"day": day, "raw_id": raw_id} for record in bundle.hits],
    )
    return written + len(bundle.actions) + len(bundle.hits)


def fin_filings(connection: Connection, records: Sequence[FinFilingRow], raw_id: str, day: date) -> int:
    execute_many(
        connection,
        """
        INSERT INTO fin_filing (filing_id, feed, symbol, isin, company_name, period_end, period_start, consolidated,
                                audited, bank, broadcast_at, revised, xbrl_url, raw_id)
        VALUES (:filing_id, :feed, :symbol, :isin, :company_name, :period_end, :period_start, :consolidated,
                :audited, :bank, :broadcast_at, :revised, :xbrl_url, :raw_id)
        ON CONFLICT (filing_id) DO UPDATE SET
            symbol = EXCLUDED.symbol, isin = EXCLUDED.isin, company_name = EXCLUDED.company_name,
            period_end = EXCLUDED.period_end, period_start = EXCLUDED.period_start, consolidated = EXCLUDED.consolidated,
            audited = EXCLUDED.audited, bank = EXCLUDED.bank, broadcast_at = EXCLUDED.broadcast_at,
            revised = EXCLUDED.revised, xbrl_url = EXCLUDED.xbrl_url, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"raw_id": raw_id} for record in records],
    )
    return len(records)


def fin_facts(connection: Connection, parsed: FinFacts, raw_id: str, filing_id: str) -> int:
    """One filing's facts plus its canonical fin_quarter row. A reload replaces both wholesale."""
    execute(connection, "DELETE FROM fin_fact WHERE filing_id = :filing_id", {"filing_id": filing_id})
    row = fundamentals.canonical(parsed)
    columns = ", ".join(fundamentals.QUARTER_COLUMNS)
    values = ", ".join(f":{name}" for name in fundamentals.QUARTER_COLUMNS)
    updates = ", ".join(f"{name} = EXCLUDED.{name}" for name in fundamentals.QUARTER_COLUMNS)
    execute(
        connection,
        f"""
        INSERT INTO fin_quarter (filing_id, symbol, period_end, consolidated, broadcast_at, taxonomy, is_bank, is_lender,
                                 raw_id, {columns})
        SELECT f.filing_id, f.symbol, f.period_end, f.consolidated, f.broadcast_at, :taxonomy, :is_bank, :is_lender,
               :raw_id, {values}
          FROM fin_filing f WHERE f.filing_id = :filing_id
        ON CONFLICT (filing_id) DO UPDATE SET taxonomy = EXCLUDED.taxonomy, is_bank = EXCLUDED.is_bank,
            is_lender = EXCLUDED.is_lender, raw_id = EXCLUDED.raw_id, broadcast_at = EXCLUDED.broadcast_at, {updates}
        """,
        {name: row.get(name) for name in fundamentals.QUARTER_COLUMNS}
        | {
            "taxonomy": row["taxonomy"],
            "is_bank": row["is_bank"],
            "is_lender": row["is_lender"],
            "raw_id": raw_id,
            "filing_id": filing_id,
        },
    )
    execute_many(
        connection,
        """
        INSERT INTO fin_fact (filing_id, item, period_kind, value, unit, taxonomy, raw_id)
        VALUES (:filing_id, :item, :period_kind, :value, :unit, :taxonomy, :raw_id)
        """,
        [
            fact.model_dump() | {"filing_id": filing_id, "taxonomy": parsed.taxonomy, "raw_id": raw_id}
            for fact in parsed.facts
        ],
    )
    return len(parsed.facts)


def documents(connection: Connection, records: Sequence[DocumentRow], raw_id: str, day: date) -> int:
    execute_many(
        connection,
        """
        INSERT INTO document (document_id, symbol, isin, company_name, broadcast_at, category, event_kind, summary,
                              attachment_url, attachment_kb, has_xbrl, industry, raw_id)
        VALUES (:document_id, :symbol, :isin, :company_name, :broadcast_at, :category, :event_kind, :summary,
                :attachment_url, :attachment_kb, :has_xbrl, :industry, :raw_id)
        ON CONFLICT (document_id) DO UPDATE SET category = EXCLUDED.category, event_kind = EXCLUDED.event_kind,
            summary = EXCLUDED.summary, attachment_url = EXCLUDED.attachment_url, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"raw_id": raw_id} for record in records],
    )
    return len(records)


def board_meetings(connection: Connection, records: Sequence[BoardMeetingRow], raw_id: str, day: date) -> int:
    execute_many(
        connection,
        """
        INSERT INTO board_meeting (symbol, meeting_date, purpose, company_name, description, raw_id)
        VALUES (:symbol, :meeting_date, :purpose, :company_name, :description, :raw_id)
        ON CONFLICT (symbol, meeting_date, purpose) DO UPDATE SET description = EXCLUDED.description, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"raw_id": raw_id} for record in records],
    )
    return len(records)


def credit_ratings(connection: Connection, records: Sequence[CreditRatingRow], raw_id: str, day: date) -> int:
    execute_many(
        connection,
        """
        INSERT INTO credit_rating (rating_id, symbol, isin, company_name, agency, rating, outlook, action, rating_earlier,
                                   rated_on, broadcast_at, raw_id)
        VALUES (:rating_id, :symbol, :isin, :company_name, :agency, :rating, :outlook, :action, :rating_earlier,
                :rated_on, :broadcast_at, :raw_id)
        ON CONFLICT (rating_id) DO UPDATE SET rating = EXCLUDED.rating, outlook = EXCLUDED.outlook, action = EXCLUDED.action,
            rating_earlier = EXCLUDED.rating_earlier, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"raw_id": raw_id} for record in records],
    )
    return len(records)


def derivatives(connection: Connection, records: Sequence[DerivativeOiRow], raw_id: str, day: date) -> int:
    execute_many(
        connection,
        """
        INSERT INTO derivative_oi (symbol, trade_date, futures_oi, futures_oi_change, futures_volume, near_expiry, near_close,
                                   underlying_close, basis_pct, call_oi, put_oi, pcr_oi, raw_id)
        VALUES (:symbol, :trade_date, :futures_oi, :futures_oi_change, :futures_volume, :near_expiry, :near_close,
                :underlying_close, :basis_pct, :call_oi, :put_oi, :pcr_oi, :raw_id)
        ON CONFLICT (symbol, trade_date) DO UPDATE SET futures_oi = EXCLUDED.futures_oi, futures_oi_change = EXCLUDED.futures_oi_change,
            futures_volume = EXCLUDED.futures_volume, near_expiry = EXCLUDED.near_expiry, near_close = EXCLUDED.near_close,
            underlying_close = EXCLUDED.underlying_close, basis_pct = EXCLUDED.basis_pct, call_oi = EXCLUDED.call_oi,
            put_oi = EXCLUDED.put_oi, pcr_oi = EXCLUDED.pcr_oi, raw_id = EXCLUDED.raw_id
        """,
        [record.model_dump() | {"raw_id": raw_id} for record in records],
    )
    return len(records)
