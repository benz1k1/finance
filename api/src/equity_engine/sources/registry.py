"""
The source registry (spec §82): every file the engine reads, where it comes from and how it is
named in the cache. ``load_data.py`` writes this list to ``source_registry``.

Four kinds:

* ``daily`` — one file per trade date, the date is in the server's filename. Backfillable.
* ``snapshot`` — a current-only file with no history at the exchange. Fetched once per calendar
  day and stored under that day, so its history starts when ingestion starts.
* ``monthly`` — a date-range query, asked one calendar month at a time and keyed by the first of
  the month. Only a month that has ended is fetched, because a cached file is never refreshed.
* ``document`` — files named by another source's rows (the XBRL behind a filing). No URL
  template: the listing supplies the URL and the cache keeps the server's filename.
* ``per_symbol`` — a feed that answers only for one symbol at a time (insider trades, pledge).
  ``{symbol}`` in the templates; not fetched by the snapshot or monthly loops.

Template fields: ``{yyyymmdd}`` ``{ddmmyyyy}`` ``{ddmmyy}`` ``{yyyy}`` ``{dd}`` ``{MON}``
(upper-case month); for monthly sources ``{yyyy_mm}`` ``{from_dmy}`` ``{to_dmy}`` (first and
last day of the month as dd-mm-yyyy).
"""

import calendar
from dataclasses import dataclass
from datetime import date

NSE_ARCHIVE = "https://nsearchives.nseindia.com"
NSE_API = "https://www.nseindia.com/api"

# NSE moved the daily price file to the UDiFF layout on Monday 8-Jul-2024; the legacy layout's
# last file is Friday 5-Jul-2024. The weekend between belongs to UDiFF, so that every calendar
# date has exactly one price source to ask.
LEGACY_LAST_DATE = date(2024, 7, 5)
UDIFF_FIRST_DATE = date(2024, 7, 6)
# The accepted start of history (spec §82.1): backtests begin in 2019.
HISTORY_FIRST_DATE = date(2019, 1, 1)


@dataclass(frozen=True)
class Source:
    source_id: str
    name: str
    kind: str  # daily | snapshot | monthly | document
    host_group: str  # nse_archive | nse_api — pacing and session are per group
    url_template: str
    filename_template: str  # the server's own filename, kept as-is in the cache
    parser: str
    magic: bytes  # what a genuine file starts with; an HTML error page does not
    owner: str
    licence: str
    cadence: str
    staleness_hours: int
    first_date: date | None = None
    last_date: date | None = None

    def _fields(self, day: date) -> dict[str, str]:
        return {
            "yyyymmdd": day.strftime("%Y%m%d"),
            "ddmmyyyy": day.strftime("%d%m%Y"),
            "ddmmyy": day.strftime("%d%m%y"),
            "yyyy": day.strftime("%Y"),
            "dd": day.strftime("%d"),
            "MON": day.strftime("%b").upper(),
            "yyyy_mm": day.strftime("%Y-%m"),
            "from_dmy": day.replace(day=1).strftime("%d-%m-%Y"),
            "to_dmy": month_end(day).strftime("%d-%m-%Y"),
        }

    def url(self, day: date) -> str:
        return self.url_template.format(**self._fields(day))

    def filename(self, day: date) -> str:
        return self.filename_template.format(**self._fields(day))

    def covers(self, day: date) -> bool:
        return (self.first_date is None or day >= self.first_date) and (
            self.last_date is None or day <= self.last_date
        )


def month_end(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


_NSE_TERMS = "NSE website terms of use; personal research, no redistribution"
# The earliest shareholding filings NSE's feed returns are for the Sep-2021 quarter (spec §82.1).
SHAREHOLDING_FIRST_MONTH = date(2021, 10, 1)
# Results: XBRL exists from the Dec-2018 quarter (filed from Jan-2019). The old results feed
# stopped carrying new filings after the Dec-2024 quarter; from the Mar-2025 quarter results
# are "integrated filings" on a second feed. The two overlap by a few months on purpose.
RESULTS_FIRST_MONTH = date(2019, 1, 1)
RESULTS_LAST_MONTH = date(2025, 3, 1)
INTEGRATED_FIRST_MONTH = date(2025, 1, 1)


def _deal_history(kind: str) -> Source:
    return Source(
        source_id=f"nse_{kind}_deal_history",
        name=f"NSE {kind} deals — full month",
        kind="monthly",
        host_group="nse_api",
        url_template=(
            NSE_API + "/historicalOR/bulk-block-short-deals?optionType=" + kind + "_deals"
            "&from={from_dmy}&to={to_dmy}&csv=true"
        ),
        filename_template=kind + "_deals_{yyyy_mm}.csv",
        parser=f"nse_{kind}_deal_history",
        magic=b'\xef\xbb\xbf"Date',
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each month, after it ends",
        staleness_hours=24 * 45,
        first_date=HISTORY_FIRST_DATE,
    )


def _document(source_id: str, name: str) -> Source:
    return Source(
        source_id=source_id,
        name=name,
        kind="document",
        host_group="nse_archive",
        url_template="",
        filename_template="",
        parser=source_id,
        magic=b"<?xml",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="one file per filing",
        staleness_hours=0,
    )


def _index(code: str, filename: str) -> Source:
    return Source(
        source_id=f"nse_index_{code}",
        name=f"NSE index constituents — {code}",
        kind="snapshot",
        host_group="nse_archive",
        url_template=f"{NSE_ARCHIVE}/content/indices/{filename}",
        filename_template=filename,
        parser="nse_index",
        magic=b"Company Name",
        owner="NSE Indices",
        licence=_NSE_TERMS,
        cadence="daily snapshot",
        staleness_hours=72,
    )


def _surveillance(code: str) -> Source:
    return Source(
        source_id=f"nse_surveillance_{code.lower()}",
        name=f"NSE surveillance list — {code}",
        kind="snapshot",
        host_group="nse_api",
        url_template=f"{NSE_API}/report{code}",
        filename_template=f"report{code}.json",
        parser=f"nse_surveillance_{code.lower()}",
        magic=b"{" if code == "ASM" else b"[",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="daily snapshot",
        staleness_hours=72,
    )


SOURCES: tuple[Source, ...] = (
    Source(
        source_id="nse_bhav_udiff",
        name="NSE daily prices (UDiFF bhavcopy)",
        kind="daily",
        host_group="nse_archive",
        url_template=NSE_ARCHIVE + "/content/cm/BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip",
        filename_template="BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip",
        parser="nse_bhav_udiff",
        magic=b"PK",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each trading day, after close",
        staleness_hours=96,
        first_date=UDIFF_FIRST_DATE,
    ),
    Source(
        source_id="nse_bhav_legacy",
        name="NSE daily prices (legacy bhavcopy)",
        kind="daily",
        host_group="nse_archive",
        url_template=NSE_ARCHIVE + "/content/historical/EQUITIES/{yyyy}/{MON}/cm{dd}{MON}{yyyy}bhav.csv.zip",
        filename_template="cm{dd}{MON}{yyyy}bhav.csv.zip",
        parser="nse_bhav_legacy",
        magic=b"PK",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="historical only",
        staleness_hours=0,
        first_date=HISTORY_FIRST_DATE,
        last_date=LEGACY_LAST_DATE,
    ),
    Source(
        source_id="nse_delivery_mto",
        name="NSE security-wise delivery position (MTO)",
        kind="daily",
        host_group="nse_archive",
        url_template=NSE_ARCHIVE + "/archives/equities/mto/MTO_{ddmmyyyy}.DAT",
        filename_template="MTO_{ddmmyyyy}.DAT",
        parser="nse_delivery_mto",
        magic=b"Security Wise Delivery Position",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each trading day, after close",
        staleness_hours=96,
        first_date=HISTORY_FIRST_DATE,
    ),
    Source(
        source_id="nse_daily_reports",
        name="NSE daily reports bundle (market cap, issue size)",
        kind="daily",
        host_group="nse_archive",
        url_template=NSE_ARCHIVE + "/archives/equities/bhavcopy/pr/PR{ddmmyy}.zip",
        filename_template="PR{ddmmyy}.zip",
        parser="nse_market_cap",
        magic=b"PK",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each trading day, after close",
        staleness_hours=96,
        first_date=HISTORY_FIRST_DATE,
    ),
    Source(
        source_id="nse_equity_master",
        name="NSE listed equities (mainboard)",
        kind="snapshot",
        host_group="nse_archive",
        url_template=NSE_ARCHIVE + "/content/equities/EQUITY_L.csv",
        filename_template="EQUITY_L.csv",
        parser="nse_equity_master",
        magic=b"SYMBOL",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="daily snapshot",
        staleness_hours=72,
    ),
    Source(
        source_id="nse_sme_master",
        name="NSE listed equities (SME)",
        kind="snapshot",
        host_group="nse_archive",
        url_template=NSE_ARCHIVE + "/emerge/corporates/content/SME_EQUITY_L.csv",
        filename_template="SME_EQUITY_L.csv",
        parser="nse_sme_master",
        magic=b"SYMBOL",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="daily snapshot",
        staleness_hours=72,
    ),
    Source(
        source_id="nse_price_band",
        name="NSE series and price bands",
        kind="snapshot",
        host_group="nse_archive",
        url_template=NSE_ARCHIVE + "/content/equities/sec_list.csv",
        filename_template="sec_list.csv",
        parser="nse_price_band",
        magic=b"Symbol",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="daily snapshot",
        staleness_hours=72,
    ),
    Source(
        source_id="nse_bulk_deal",
        name="NSE bulk deals",
        kind="snapshot",
        host_group="nse_archive",
        url_template=NSE_ARCHIVE + "/content/equities/bulk.csv",
        filename_template="bulk.csv",
        parser="nse_bulk_deal",
        magic=b"Date",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="daily snapshot",
        staleness_hours=72,
    ),
    Source(
        source_id="nse_block_deal",
        name="NSE block deals",
        kind="snapshot",
        host_group="nse_archive",
        url_template=NSE_ARCHIVE + "/content/equities/block.csv",
        filename_template="block.csv",
        parser="nse_block_deal",
        magic=b"Date",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="daily snapshot",
        staleness_hours=72,
    ),
    _index("nifty50", "ind_nifty50list.csv"),
    _index("niftynext50", "ind_niftynext50list.csv"),
    _index("nifty100", "ind_nifty100list.csv"),
    _index("nifty200", "ind_nifty200list.csv"),
    _index("nifty500", "ind_nifty500list.csv"),
    _index("niftymidcap150", "ind_niftymidcap150list.csv"),
    _index("niftysmallcap250", "ind_niftysmallcap250list.csv"),
    _index("niftymicrocap250", "ind_niftymicrocap250_list.csv"),
    _deal_history("bulk"),
    _deal_history("block"),
    Source(
        source_id="nse_shareholding_filings",
        name="NSE shareholding pattern filings — full month",
        kind="monthly",
        host_group="nse_api",
        url_template=NSE_API
        + "/corporate-share-holdings-master?index=equities&from_date={from_dmy}&to_date={to_dmy}",
        filename_template="shareholding_filings_{yyyy_mm}.json",
        parser="nse_shareholding_filings",
        magic=b"[",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each month, after it ends",
        staleness_hours=24 * 45,
        first_date=SHAREHOLDING_FIRST_MONTH,
    ),
    _document("nse_shareholding_xbrl", "NSE shareholding pattern XBRL (one per filing)"),
    Source(
        source_id="nse_results_filings",
        name="NSE financial results filings — full month (to the Dec-2024 quarter)",
        kind="monthly",
        host_group="nse_api",
        url_template=NSE_API
        + "/corporates-financial-results?index=equities&from_date={from_dmy}&to_date={to_dmy}&period=Quarterly",
        filename_template="results_filings_{yyyy_mm}.json",
        parser="nse_results_filings",
        magic=b"[",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each month, after it ends",
        staleness_hours=0,
        first_date=RESULTS_FIRST_MONTH,
        last_date=RESULTS_LAST_MONTH,
    ),
    Source(
        source_id="nse_integrated_filings",
        name="NSE integrated filings (financials) — full month (from the Mar-2025 quarter)",
        kind="monthly",
        host_group="nse_api",
        url_template=NSE_API
        + "/integrated-filing-results?index=equities&type=Integrated%20Filing-%20Financials"
        "&from_date={from_dmy}&to_date={to_dmy}&size=10000&page=1",
        filename_template="integrated_filings_{yyyy_mm}.json",
        parser="nse_integrated_filings",
        magic=b"{",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each month, after it ends",
        staleness_hours=24 * 45,
        first_date=INTEGRATED_FIRST_MONTH,
    ),
    _document("nse_results_xbrl", "NSE financial results XBRL (one per filing, both feeds)"),
    Source(
        source_id="nse_announcement_pdf",
        name="NSE announcement attachments (PDF, one per announcement fetched)",
        kind="document",
        host_group="nse_archive",
        url_template="",
        filename_template="",
        parser="nse_announcement_pdf",
        magic=b"%PDF",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="on demand, by announcement kind",
        staleness_hours=0,
    ),
    Source(
        source_id="nse_announcements",
        name="NSE corporate announcements — full month",
        kind="monthly",
        host_group="nse_api",
        url_template=NSE_API
        + "/corporate-announcements?index=equities&from_date={from_dmy}&to_date={to_dmy}",
        filename_template="announcements_{yyyy_mm}.json",
        parser="nse_announcements",
        magic=b"[",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each month, after it ends",
        staleness_hours=24 * 45,
        first_date=HISTORY_FIRST_DATE,
    ),
    Source(
        source_id="nse_insider_trades",
        name="NSE insider trading disclosures (PIT) — full month",
        kind="per_symbol",
        host_group="nse_api",
        url_template=NSE_API
        + "/corporates-pit?index=equities&symbol={symbol}&from_date={from_dmy}&to_date={to_dmy}",
        filename_template="insider_{symbol}_{yyyy_mm}.json",
        parser="nse_insider_trades",
        magic=b"{",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="per symbol, each month (the market-wide query returns nothing)",
        staleness_hours=24 * 45,
        first_date=HISTORY_FIRST_DATE,
    ),
    Source(
        source_id="nse_pledge",
        name="NSE promoter pledge disclosures (current)",
        kind="per_symbol",
        host_group="nse_api",
        url_template=NSE_API + "/corporate-pledgedata?index=equities&symbol={symbol}",
        filename_template="pledge_{symbol}.json",
        parser="nse_pledge",
        magic=b"{",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="daily snapshot",
        staleness_hours=72,
    ),
    Source(
        source_id="nse_board_meetings",
        name="NSE board meetings and event calendar — full month",
        kind="monthly",
        host_group="nse_api",
        url_template=NSE_API + "/event-calendar?index=equities&from_date={from_dmy}&to_date={to_dmy}",
        filename_template="events_{yyyy_mm}.json",
        parser="nse_board_meetings",
        magic=b"[",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each month, after it ends",
        staleness_hours=24 * 45,
        first_date=HISTORY_FIRST_DATE,
    ),
    Source(
        source_id="nse_credit_ratings",
        name="NSE credit rating disclosures — full month",
        kind="monthly",
        host_group="nse_api",
        url_template=NSE_API
        + "/corporate-credit-rating?index=equities&from_date={from_dmy}&to_date={to_dmy}",
        filename_template="credit_ratings_{yyyy_mm}.json",
        parser="nse_credit_ratings",
        magic=b"[",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each month, after it ends",
        staleness_hours=24 * 45,
        first_date=HISTORY_FIRST_DATE,
    ),
    Source(
        source_id="nse_fo_bhav",
        name="NSE F&O bhavcopy (UDiFF)",
        kind="daily",
        host_group="nse_archive",
        url_template=NSE_ARCHIVE + "/content/fo/BhavCopy_NSE_FO_0_0_0_{yyyymmdd}_F_0000.csv.zip",
        filename_template="BhavCopy_NSE_FO_0_0_0_{yyyymmdd}_F_0000.csv.zip",
        parser="nse_fo_bhav",
        magic=b"PK",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="each trade date after close",
        staleness_hours=0,
        first_date=UDIFF_FIRST_DATE,
    ),
    Source(
        source_id="nse_brsr_filings",
        name="NSE sustainability report (BRSR) filings",
        kind="snapshot",
        host_group="nse_api",
        url_template=NSE_API + "/corporate-bussiness-sustainabilitiy?index=equities",
        filename_template="brsr_filings.json",
        parser="nse_brsr_filings",
        magic=b"{",
        owner="NSE",
        licence=_NSE_TERMS,
        cadence="weekly snapshot",
        staleness_hours=24 * 30,
    ),
    _document("nse_brsr_xbrl", "NSE sustainability report (BRSR) XBRL (one per filing)"),
    _surveillance("ASM"),
    _surveillance("GSM"),
    _surveillance("ESM"),
)

BY_ID: dict[str, Source] = {source.source_id: source for source in SOURCES}
SNAPSHOT_SOURCES: tuple[Source, ...] = tuple(source for source in SOURCES if source.kind == "snapshot")
MONTHLY_SOURCES: tuple[Source, ...] = tuple(source for source in SOURCES if source.kind == "monthly")


def get(source_id: str) -> Source:
    if source_id not in BY_ID:
        raise ValueError(f"Unknown source {source_id!r}. Known: {', '.join(sorted(BY_ID))}")
    return BY_ID[source_id]


def price_source_for(day: date) -> Source:
    """The one price file that exists for a trade date: legacy before the UDiFF switch, UDiFF after."""
    return BY_ID["nse_bhav_udiff"] if day >= UDIFF_FIRST_DATE else BY_ID["nse_bhav_legacy"]
