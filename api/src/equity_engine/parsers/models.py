"""
The validated record every parser emits (spec §83). A row that fails validation stops the run
for that file: it is never skipped or defaulted, because a silently dropped row is a hole in a
price series that nothing downstream can see.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Isin = Annotated[str, StringConstraints(pattern=r"^IN[A-Z0-9]{10}$")]
# Index files also carry NSE's placeholder constituents for demerged entities that are not listed
# yet ("Dummy HEG Ltd.", ISIN DUM545A01024). They hold index weight, so they are kept, not dropped.
IndexIsin = Annotated[str, StringConstraints(pattern=r"^(IN|DU)[A-Z0-9]{10}$")]
Symbol = Annotated[str, StringConstraints(min_length=1, max_length=40)]
Text = Annotated[str, StringConstraints(strip_whitespace=True)]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# The series this engine treats as equity. Everything else in the exchange files (gold bonds,
# government securities, debentures, REIT/InvIT units, rights entitlements) is left out at
# parse time; REIT/InvIT come back as their own asset class later (spec §3.1).
EQUITY_SERIES = frozenset({"EQ", "BE", "BZ", "SM", "ST", "SZ"})


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PriceRow(_Record):
    isin: Isin
    symbol: Symbol
    series: str
    trade_date: date
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    last: Decimal = Field(gt=0)
    prev_close: Decimal = Field(ge=0)
    volume: int = Field(ge=0)
    turnover: Decimal = Field(ge=0)
    trades: int = Field(ge=0)

    @model_validator(mode="after")
    def _range(self) -> "PriceRow":
        if not self.low <= self.high:
            raise ValueError(f"{self.symbol} {self.trade_date}: low {self.low} above high {self.high}")
        for label, value in (("open", self.open), ("close", self.close), ("last", self.last)):
            if not self.low <= value <= self.high:
                raise ValueError(
                    f"{self.symbol} {self.trade_date}: {label} {value} outside low {self.low} – high {self.high}"
                )
        return self


class DeliveryRow(_Record):
    symbol: Symbol
    series: str
    trade_date: date
    traded_qty: int = Field(ge=0)
    deliv_qty: int = Field(ge=0)
    deliv_pct: Decimal = Field(ge=0, le=100)


class SecurityRow(_Record):
    isin: Isin
    symbol: Symbol
    name: NonEmpty
    series: NonEmpty
    segment: Literal["MAIN", "SME"]
    listing_date: date
    face_value: Decimal = Field(gt=0)
    paid_up_value: Decimal = Field(gt=0)


class BandRow(_Record):
    symbol: Symbol
    series: NonEmpty
    band: Literal["2", "5", "10", "20", "40", "No Band"]
    remarks: Text


class DealRow(_Record):
    kind: Literal["BULK", "BLOCK"]
    deal_date: date
    seq: int = Field(ge=1)
    symbol: Symbol
    security_name: NonEmpty
    client_name: NonEmpty
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    price: Decimal = Field(gt=0)
    remarks: Text


class IndexRow(_Record):
    index_code: NonEmpty
    isin: IndexIsin
    symbol: Symbol
    company_name: NonEmpty
    industry: NonEmpty


class SurveillanceRow(_Record):
    list_code: Literal["ASM_LT", "ASM_ST", "GSM", "ESM"]
    isin: Isin
    symbol: Symbol
    company_name: NonEmpty
    stage: NonEmpty
    surv_code: NonEmpty
    surv_desc: NonEmpty


class MarketCapRow(_Record):
    symbol: Symbol
    series: str
    trade_date: date
    face_value: Decimal = Field(gt=0)
    issue_size: int = Field(gt=0)  # shares outstanding
    market_cap: Decimal = Field(ge=0)  # rupees


# ------------------------------------------------------------------ ownership and profile

Percent = Annotated[Decimal, Field(ge=0, le=100)]


class ShareholdingFilingRow(_Record):
    record_id: NonEmpty
    symbol: Symbol
    # Typed in by the company and sometimes malformed ("INE 439A0401"), so it is kept as text
    # and never used as a key; the symbol, which NSE assigns, is.
    isin: str | None
    company_name: NonEmpty
    period_end: date
    promoter_pct: Percent | None
    public_pct: Percent | None
    broadcast_at: datetime
    revised: bool
    xbrl_url: str | None


class ShareholdingPatternRow(_Record):
    """The category breakdown of one filing. Every percentage is of total shares, 0–100."""

    symbol: Symbol
    isin: str  # as typed in the filing; see ShareholdingFilingRow.isin
    period_end: date
    total_shares: int = Field(gt=0)
    total_shareholders: int = Field(ge=0)
    # None when the company has no promoter group at all (professionally managed, e.g. 3i
    # Infotech): the filing then carries no promoter category.
    promoter_pct: Percent | None
    public_pct: Percent
    fii_pct: Percent | None
    fpi_pct: Percent | None
    dii_pct: Percent | None
    mutual_fund_pct: Percent | None
    insurance_pct: Percent | None
    pension_fund_pct: Percent | None
    aif_pct: Percent | None
    bank_pct: Percent | None
    government_pct: Percent | None
    retail_pct: Percent | None
    hni_pct: Percent | None
    nri_pct: Percent | None
    bodies_corporate_pct: Percent | None


class BrsrFilingRow(_Record):
    symbol: Symbol
    company_name: NonEmpty
    fy_to: int = Field(ge=2000, le=2100)
    submitted_on: date
    xbrl_url: str
    annual_report_url: str | None


class ActivityRow(_Record):
    seq: int = Field(ge=1)
    main_activity: NonEmpty
    description: Text
    turnover_pct: Percent | None


class ProductRow(_Record):
    seq: int = Field(ge=1)
    product: NonEmpty
    nic_code: str | None
    turnover_pct: Percent | None


class CompanyProfileRow(_Record):
    company_name: NonEmpty
    cin: str | None
    incorporated_on: date | None
    website: str | None
    email: str | None
    registered_address: str | None
    states_served: int | None = Field(default=None, ge=0)
    countries_served: int | None = Field(default=None, ge=0)
    employees: int | None = Field(default=None, ge=0)
    workers: int | None = Field(default=None, ge=0)
    turnover: Decimal | None
    net_worth: Decimal | None
    activities: tuple[ActivityRow, ...]
    products: tuple[ProductRow, ...]


class CorporateActionRow(_Record):
    """One line of the bundle's ``bc`` file for an equity series. ``kind``, ``amount`` and
    ``adjust_factor`` are read from the free-text purpose; a purpose the reader does not
    recognise is kept as OTHER with both NULL, never dropped."""

    symbol: Symbol
    series: NonEmpty
    security_name: NonEmpty
    ex_date: date
    record_date: date | None
    bc_start: date | None
    bc_end: date | None
    nd_start: date | None
    nd_end: date | None
    purpose: NonEmpty
    kind: str
    amount: Decimal | None = None
    adjust_factor: Decimal | None = Field(default=None, gt=0)


class CircuitHitRow(_Record):
    symbol: Symbol
    series: NonEmpty
    side: str = Field(pattern="^[HL]$")


class DailyReportsRows(BaseModel):
    """Everything read from one daily reports bundle."""

    market_caps: list[MarketCapRow]
    actions: list[CorporateActionRow]
    hits: list[CircuitHitRow]

    def __len__(self) -> int:
        """The ingest log counts parsed rows; this bundle parses into three lists."""
        return len(self.market_caps) + len(self.actions) + len(self.hits)


class FinFilingRow(_Record):
    filing_id: NonEmpty
    feed: Literal["RESULTS", "INTEGRATED"]
    symbol: Symbol
    isin: str | None
    company_name: NonEmpty
    period_end: date
    period_start: date | None
    consolidated: bool
    audited: bool
    bank: Literal["N", "B", "F", "?"]
    broadcast_at: datetime
    revised: bool
    xbrl_url: str | None


class FinFactRow(_Record):
    item: NonEmpty
    period_kind: Literal["Q", "YTD", "INSTANT"]
    value: Decimal
    unit: NonEmpty


Taxonomy = Literal["INDAS", "NBFC", "BANKING", "NONINDAS", "CAPMKT"]


class FinFacts(BaseModel):
    """Everything numeric in one results XBRL, with the taxonomy it was filed under."""

    taxonomy: Taxonomy
    period_end: date | None
    facts: list[FinFactRow]

    def __len__(self) -> int:
        return len(self.facts)


class DocumentRow(_Record):
    document_id: NonEmpty
    symbol: Symbol
    isin: str | None
    company_name: NonEmpty
    broadcast_at: datetime
    category: NonEmpty
    event_kind: NonEmpty
    summary: str
    attachment_url: str | None
    attachment_kb: Decimal | None
    has_xbrl: bool
    industry: str | None


class BoardMeetingRow(_Record):
    symbol: Symbol
    meeting_date: date
    purpose: NonEmpty
    company_name: NonEmpty
    description: str


class CreditRatingRow(_Record):
    rating_id: NonEmpty
    symbol: str | None
    isin: str | None
    company_name: NonEmpty
    agency: NonEmpty
    rating: NonEmpty
    outlook: str | None
    action: NonEmpty
    rating_earlier: str | None
    rated_on: date | None
    broadcast_at: datetime


class DerivativeOiRow(_Record):
    symbol: Symbol
    trade_date: date
    futures_oi: int = Field(ge=0)
    futures_oi_change: int
    futures_volume: int = Field(ge=0)
    near_expiry: date | None
    near_close: Decimal | None
    underlying_close: Decimal | None
    basis_pct: Decimal | None
    call_oi: int = Field(ge=0)
    put_oi: int = Field(ge=0)
    pcr_oi: Decimal | None
