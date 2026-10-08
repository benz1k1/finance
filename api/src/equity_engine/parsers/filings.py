"""
Parsers for NSE's filing feeds and the XBRL documents behind them (spec §117): shareholding
patterns (for the promoter / FII / DII split), the sustainability report (website, business
activities, products) and full-month deal history. Bytes in, validated records out.
"""

import io
import re
import xml.etree.ElementTree as ElementTree
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import orjson
from pydantic import TypeAdapter

from equity_engine.parsers.models import (
    BoardMeetingRow,
    BrsrFilingRow,
    CompanyProfileRow,
    CreditRatingRow,
    DealRow,
    DocumentRow,
    FinFactRow,
    FinFacts,
    FinFilingRow,
    ShareholdingFilingRow,
    ShareholdingPatternRow,
    Taxonomy,
)
from equity_engine.parsers.nse import _read_csv

IST = ZoneInfo("Asia/Kolkata")
_FILINGS = TypeAdapter(list[ShareholdingFilingRow])
_BRSR_FILINGS = TypeAdapter(list[BrsrFilingRow])
_DEALS = TypeAdapter(list[DealRow])
_FIN_FILINGS = TypeAdapter(list[FinFilingRow])
_FIN_FACTS = TypeAdapter(list[FinFactRow])
_DOCUMENTS = TypeAdapter(list[DocumentRow])
_MEETINGS = TypeAdapter(list[BoardMeetingRow])
_RATINGS = TypeAdapter(list[CreditRatingRow])
# NSE writes these for "nothing here".
_BLANK = frozenset({"", "-", "NA", "N.A.", "null"})


def _blank_to_none(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    return None if text in _BLANK else text


def _xbrl_link(value: Any) -> str | None:
    """A filing with no XBRL carries a link ending in ``/-``."""
    link = _blank_to_none(value)
    if link is None or link.endswith("/-") or not link.lower().endswith(".xml"):
        return None
    return link


# ------------------------------------------------------------------ deal history


def _deal_history(content: bytes, kind: str) -> list[DealRow]:
    """The monthly CSV: same columns as the daily file, but padded header names, ``Buy / Sell``
    for the side and Indian digit grouping in the quantity (``55,83,831``)."""
    sequence: dict[date, int] = {}
    records = []
    for line in _read_csv(content.removeprefix(b"\xef\xbb\xbf")):
        deal_date = datetime.strptime(line["Date"].title(), "%d-%b-%Y").date()
        sequence[deal_date] = sequence.get(deal_date, 0) + 1
        records.append(
            {
                "kind": kind,
                "deal_date": deal_date,
                "seq": sequence[deal_date],
                "symbol": line["Symbol"],
                "security_name": line["Security Name"],
                "client_name": line["Client Name"],
                "side": line["Buy / Sell"],
                "quantity": line["Quantity Traded"].replace(",", ""),
                "price": line["Trade Price / Wght. Avg. Price"].replace(",", ""),
                "remarks": line["Remarks"],
            }
        )
    return _DEALS.validate_python(records)


def bulk_deal_history(content: bytes, day: date) -> list[DealRow]:
    return _deal_history(content, "BULK")


def block_deal_history(content: bytes, day: date) -> list[DealRow]:
    return _deal_history(content, "BLOCK")


# ------------------------------------------------------------------ filing lists


def shareholding_filings(content: bytes, day: date) -> list[ShareholdingFilingRow]:
    records = [
        {
            "record_id": item["recordId"],
            "symbol": item["symbol"],
            "isin": _blank_to_none(item["isin"]),
            "company_name": item["name"],
            "period_end": datetime.strptime(item["date"].title(), "%d-%b-%Y").date(),
            "promoter_pct": _blank_to_none(item["pr_and_prgrp"]),
            "public_pct": _blank_to_none(item["public_val"]),
            "broadcast_at": datetime.strptime(item["broadcastDate"].title(), "%d-%b-%Y %H:%M:%S").replace(
                tzinfo=IST
            ),
            "revised": item["revisedStatus"] == "Revised",
            "xbrl_url": _xbrl_link(item["xbrl"]),
        }
        for item in orjson.loads(content)
        if _blank_to_none(item.get("date"))  # a few 2021-22 rows carry no quarter end; unkeyable
    ]
    return _FILINGS.validate_python(records)


def brsr_filings(content: bytes, day: date) -> list[BrsrFilingRow]:
    """Filings without an XBRL file carry nothing this engine can read and are left out."""
    records = [
        {
            "symbol": item["symbol"],
            "company_name": item["companyName"],
            "fy_to": item["fyTo"],
            "submitted_on": datetime.strptime(item["submissionDate"], "%d-%b-%Y").date(),
            "xbrl_url": _xbrl_link(item["xbrlFile"]),
            "annual_report_url": _blank_to_none(item["attachmentFile"]),
        }
        for item in orjson.loads(content)["data"]
        if _xbrl_link(item["xbrlFile"]) is not None
    ]
    return _BRSR_FILINGS.validate_python(records)


# ------------------------------------------------------------------ XBRL


def _facts(content: bytes) -> dict[str, dict[str, str]]:
    """``context id -> {local tag name -> text}`` for every fact in an XBRL instance."""
    facts: dict[str, dict[str, str]] = defaultdict(dict)
    for _, element in ElementTree.iterparse(io.BytesIO(content)):
        context = element.get("contextRef")
        if context is not None and element.text is not None:
            facts[context][element.tag.rsplit("}", 1)[-1]] = element.text.strip()
    return facts


def _percent(fraction: str | None) -> Decimal | None:
    """XBRL percentages are fractions of one (0.172); the tables hold 0–100."""
    return None if fraction is None else (Decimal(fraction) * 100).quantize(Decimal("0.0001"))


# shareholder category -> the context that carries it (format "SHP V1.1")
_CATEGORY_CONTEXT = {
    "promoter_pct": "ShareholdingOfPromoterAndPromoterGroup_ContextI",
    "public_pct": "PublicShareholding_ContextI",
    "fii_pct": "InstitutionsForeign_ContextI",
    "dii_pct": "InstitutionsDomestic_ContextI",
    "mutual_fund_pct": "MutualFundsOrUTI_ContextI",
    "insurance_pct": "InsuranceCompanies_ContextI",
    "pension_fund_pct": "ProvidentFundsOrPensionFunds_ContextI",
    "aif_pct": "AlternativeInvestmentFunds_ContextI",
    "bank_pct": "Banks_ContextI",
    "government_pct": "Governments_ContextI",
    "retail_pct": "ResidentIndividualShareholdersHoldingNominalShareCapitalUpToRsTwoLakh_ContextI",
    "hni_pct": "ResidentIndividualShareholdersHoldingNominalShareCapitalInExcessOfRsTwoLakh_ContextI",
    "nri_pct": "NonResidentIndians_ContextI",
    "bodies_corporate_pct": "BodiesCorporate_ContextI",
}
_FPI_CONTEXTS = (
    "InstitutionsForeignPortfolioInvestorCategoryOne_ContextI",
    "InstitutionsForeignPortfolioInvestorCategoryTwo_ContextI",
)
_SHARE = "ShareholdingAsAPercentageOfTotalNumberOfShares"


# The format filed until late 2024: context ids without the ``_Context`` infix, the header in
# ``OneD``/``OneI``, and institutions reported as one block with no foreign/domestic total. The
# foreign share is taken as FPI + foreign venture capital; domestic is the rest of institutions.
_OLD_CATEGORY_CONTEXT = {
    "promoter_pct": "ShareholdingOfPromoterAndPromoterGroupI",
    "public_pct": "PublicShareholdingI",
    "mutual_fund_pct": "MutualFundsOrUtiI",
    "insurance_pct": "InsuranceCompaniesI",
    "pension_fund_pct": "ProvidentFundsOrPensionFundsI",
    "aif_pct": "AlternativeInvestmentFundsI",
    "bank_pct": "FinancialInstitutionOrBanksI",
    "government_pct": "GovermentsI",  # NSE's spelling
    "retail_pct": "IndividualShareholdersHoldingNominalShareCapitalUpToRsTwoLakhI",
    "hni_pct": "IndividualShareholdersHoldingNominalShareCapitalInExcessOfRsTwoLakhI",
}
_OLD_FOREIGN_CONTEXTS = ("InstitutionsForeignPortfolioInvestorI", "ForeignVentureCapitalInvestorsI")


def _old_percent(value: str | None) -> Decimal | None:
    """The old layout already states percentages (95.39), where the new one states fractions."""
    text = _blank_to_none(value)
    return None if text is None else Decimal(text).quantize(Decimal("0.0001"))


def _sum_percent(
    facts: dict[str, dict[str, str]], contexts: tuple[str, ...], read=_percent
) -> Decimal | None:
    parts = [read(facts.get(context, {}).get(_SHARE)) for context in contexts]
    present = [part for part in parts if part is not None]
    return sum(present, Decimal(0)) if present else None


def shareholding_pattern(content: bytes) -> ShareholdingPatternRow:
    """One filing's category breakdown, in either of NSE's two XBRL layouts. A category with no
    context in the file (a class of holder the company does not have) is None, not zero."""
    facts = _facts(content)
    if "MainD" in facts:
        total = facts["ShareholdingPattern_ContextI"]
        record: dict[str, Any] = {
            "symbol": facts["MainD"]["Symbol"],
            "isin": facts["MainD"]["ISIN"],
            "period_end": facts["MainI"]["DateOfReport"],
            "total_shares": total["NumberOfShares"],
            "total_shareholders": total["NumberOfShareholders"],
        }
        for field, context in _CATEGORY_CONTEXT.items():
            record[field] = _percent(facts.get(context, {}).get(_SHARE))
        record["fpi_pct"] = _sum_percent(facts, _FPI_CONTEXTS)
        return ShareholdingPatternRow.model_validate(record)
    total = facts["ShareholdingPatternI"]
    record = {
        "symbol": facts["OneD"]["Symbol"],
        "isin": facts["OneD"]["ISIN"],
        "period_end": facts["OneI"]["DateOfReport"],
        "total_shares": total["NumberOfShares"],
        "total_shareholders": total["NumberOfShareholders"],
        "nri_pct": None,
        "bodies_corporate_pct": None,
    }
    for field, context in _OLD_CATEGORY_CONTEXT.items():
        record[field] = _old_percent(facts.get(context, {}).get(_SHARE))
    institutions = _old_percent(facts.get("InstitutionsI", {}).get(_SHARE))
    foreign = _sum_percent(facts, _OLD_FOREIGN_CONTEXTS, _old_percent)
    record["fpi_pct"] = _old_percent(facts.get("InstitutionsForeignPortfolioInvestorI", {}).get(_SHARE))
    record["fii_pct"] = foreign
    record["dii_pct"] = (
        (institutions - foreign) if institutions is not None and foreign is not None else institutions
    )
    return ShareholdingPatternRow.model_validate(record)


def _numbered(facts: dict[str, dict[str, str]], prefix: str) -> list[dict[str, str]]:
    """The facts of ``<prefix>1``, ``<prefix>2``, … in order."""
    found = []
    for context, values in facts.items():
        if context.startswith(prefix) and context[len(prefix) :].isdigit():
            found.append((int(context[len(prefix) :]), values))
    return [values for _, values in sorted(found, key=lambda item: item[0])]


def company_profile(content: bytes) -> CompanyProfileRow:
    """Section A of the sustainability report: identity, website, the business activities and
    the products that make up 90% of turnover."""
    facts = _facts(content)
    main = facts["DCYMain"] | facts.get("ICYMain", {})
    headcount = "NumberOfEmployeesOrWorkersIncludingDifferentlyAbled"
    activities = [
        {
            "seq": index,
            "main_activity": values["DescriptionOfMainActivity"],
            "description": values.get("DescriptionOfBusinessActivity", ""),
            "turnover_pct": _percent(values.get("PercentageOfTotalTurnoverForBusinessActivities")),
        }
        for index, values in enumerate(_numbered(facts, "D_BusinessActivities"), start=1)
        if "DescriptionOfMainActivity" in values
    ]
    products = [
        {
            "seq": index,
            "product": values["ProductOrServiceSoldByTheEntity"],
            "nic_code": _blank_to_none(values.get("NICCodeOfProductOrServiceSoldByTheEntity")),
            "turnover_pct": _percent(values.get("PercentageOfTotalTurnoverForProductOrServiceSold")),
        }
        for index, values in enumerate(_numbered(facts, "D_ProductServiceSold"), start=1)
        if "ProductOrServiceSoldByTheEntity" in values
    ]
    return CompanyProfileRow.model_validate(
        {
            "company_name": main["NameOfTheCompany"],
            "cin": _blank_to_none(main.get("CorporateIdentityNumber")),
            "incorporated_on": _blank_to_none(main.get("DateOfIncorporation")),
            "website": _blank_to_none(main.get("WebsiteOfCompany")),
            "email": _blank_to_none(main.get("EMailOfTheCompany")),
            "registered_address": _blank_to_none(main.get("AddressOfRegisteredOfficeOfCompany")),
            "states_served": _blank_to_none(main.get("NumberOfStatesWhereMarketServedByTheEntity")),
            "countries_served": _blank_to_none(main.get("NumberOfCountriesWhereMarketServedByTheEntity")),
            "employees": facts.get("D_Gender_Employees_TableA", {}).get(headcount),
            "workers": facts.get("D_Gender_Workers_TableA", {}).get(headcount),
            "turnover": _blank_to_none(main.get("Turnover")),
            "net_worth": _blank_to_none(main.get("NetWorth")),
            "activities": activities,
            "products": products,
        }
    )


# ------------------------------------------------------------------ financial results (spec §5)


def _ist(text: str, layout: str) -> datetime:
    return datetime.strptime(text.strip(), layout).replace(tzinfo=IST)


def results_filings(content: bytes, day: date) -> list[FinFilingRow]:
    """The old results feed (``corporates-financial-results``): a bare list, one row per filing,
    both standalone and consolidated, quarterly only (the request asks for ``period=Quarterly``)."""
    records = []
    for item in orjson.loads(content):
        records.append(
            {
                "filing_id": f"R{item['seqNumber']}",
                "feed": "RESULTS",
                "symbol": item["symbol"],
                "isin": _blank_to_none(item.get("isin")),
                "company_name": item["companyName"],
                "period_end": datetime.strptime(item["toDate"], "%d-%b-%Y").date(),
                "period_start": datetime.strptime(item["fromDate"], "%d-%b-%Y").date(),
                "consolidated": (item.get("consolidated") or "").strip().lower() == "consolidated",
                "audited": (item.get("audited") or "").strip().lower() == "audited",
                "bank": item["bank"] if item.get("bank") in ("N", "B", "F") else "?",
                "broadcast_at": _ist(
                    item["broadCastDate"] or item["filingDate"] + ":00", "%d-%b-%Y %H:%M:%S"
                ),
                "revised": item.get("reInd") == "Y",
                "xbrl_url": _xbrl_link(item.get("xbrl")),
            }
        )
    return _FIN_FILINGS.validate_python(records)


def integrated_filings(content: bytes, day: date) -> list[FinFilingRow]:
    """The integrated-filing feed (from the Mar-2025 quarter): ``{data, totalCount}``. The page
    size in the request covers a whole month; a response shorter than ``totalCount`` is refused
    rather than loaded as a partial month."""
    body = orjson.loads(content)
    items = body["data"]
    if body.get("totalCount") is not None and int(body["totalCount"]) != len(items):
        raise ValueError(f"integrated filings: {len(items)} rows of {body['totalCount']} — a partial page")
    records = []
    for item in items:
        if item.get("type") != "Integrated Filing- Financials":
            continue
        records.append(
            {
                "filing_id": f"I{item['seq_Id']}",
                "feed": "INTEGRATED",
                "symbol": item["symbol"],
                "isin": None,
                "company_name": item.get("cmName") or item.get("smName") or item["symbol"],
                "period_end": datetime.strptime(item["qe_Date"].title(), "%d-%b-%Y").date(),
                "period_start": None,
                "consolidated": (item.get("consolidated") or "").strip().lower() == "consolidated",
                "audited": (item.get("audited") or "").strip().lower() == "audited",
                "bank": "?",
                "broadcast_at": _ist(
                    item.get("broadcast_Date") or item["creation_Date"], "%d-%b-%Y %H:%M:%S"
                ),
                "revised": item.get("type_Sub") == "Revision",
                "xbrl_url": _xbrl_link(item.get("xbrl")),
            }
        )
    return _FIN_FILINGS.validate_python(records)


_XBRLI = "{http://www.xbrl.org/2003/instance}"
# NSE's results taxonomies name the plain contexts the same way whatever the taxonomy: the
# quarter is OneD, the financial year to date FourD (its period dates are often wrong in the
# file and are not trusted), the balance sheet at period end OneI. Everything else is a
# dimensional breakdown (segments, OCI items) and is left out of the fact table.
_PLAIN_CONTEXTS = {"OneD": "Q", "FourD": "YTD", "OneI": "INSTANT"}
_TAXONOMY_BY_PREFIX: tuple[tuple[str, Taxonomy], ...] = (
    ("INTEGRATED", "CAPMKT"),
    ("NBFC", "NBFC"),
    ("BANKING", "BANKING"),
    ("NONINDAS", "NONINDAS"),
    ("INDAS", "INDAS"),
)


def taxonomy_of(filename: str) -> Taxonomy:
    upper = filename.upper()
    for prefix, taxonomy in _TAXONOMY_BY_PREFIX:
        if upper.startswith(prefix):
            return taxonomy
    raise ValueError(f"results XBRL with an unknown taxonomy prefix: {filename}")


def financial_facts(content: bytes, filename: str) -> FinFacts:
    """Every numeric fact in the three plain contexts of a results XBRL, as filed. Values are
    absolute rupees (the taxonomy's ``decimals`` attribute only describes rounding)."""
    root = ElementTree.fromstring(content)
    period_end = None
    units: dict[str, str] = {}
    for unit_element in root.iter(_XBRLI + "unit"):
        measures = [m.text.split(":")[-1] for m in unit_element.iter(_XBRLI + "measure") if m.text]
        units[unit_element.get("id", "")] = (
            "INRPerShare" if measures == ["INR", "shares"] else (measures[0] if measures else "pure")
        )
    for context in root.iter(_XBRLI + "context"):
        if context.get("id") == "OneI":
            instant = context.find(f"{_XBRLI}period/{_XBRLI}instant")
            if instant is not None and instant.text:
                period_end = date.fromisoformat(instant.text.strip())
    facts: dict[tuple[str, str], dict[str, Any]] = {}
    for element in root:
        kind = _PLAIN_CONTEXTS.get(element.get("contextRef", ""))
        unit = element.get("unitRef")
        if kind is None or unit is None or element.text is None or not element.text.strip():
            continue
        item = element.tag.split("}")[-1]
        try:
            value = Decimal(element.text.strip().replace(",", ""))
        except ArithmeticError:
            continue
        # A fact repeated for the same item and period keeps its first value.
        facts.setdefault(
            (item, kind), {"item": item, "period_kind": kind, "value": value, "unit": units.get(unit, unit)}
        )
    return FinFacts(
        taxonomy=taxonomy_of(filename),
        period_end=period_end,
        facts=_FIN_FACTS.validate_python(list(facts.values())),
    )


# ------------------------------------------------------------------ announcements (spec §83, §30)

# NSE's subject line ("desc") and the attachment text, read by rule into an event kind. The order
# matters: the first matching rule wins. LLM classification (Phase 3) refines, never replaces, this.
_EVENT_RULES: tuple[tuple[str, str], ...] = (
    (r"financial result|outcome of board meeting.*result|results?\b", "RESULTS"),
    (r"board meeting", "BOARD_MEETING"),
    (
        r"acquisition|amalgamation|merger|demerger|scheme of arrangement|joint venture|disinvestment|slump sale",
        "ACQUISITION",
    ),
    (r"order|contract|bagged|awarded|loi\b|letter of intent|work order", "ORDER_WIN"),
    (r"buy ?back", "BUYBACK"),
    (r"dividend", "DIVIDEND"),
    (
        r"preferential|qip|qualified institution|rights issue|fund ?rais|allotment|private placement|debenture|ncd|warrant",
        "FUND_RAISE",
    ),
    (r"credit rating|rating", "RATING"),
    (r"pledge|encumbrance", "PLEDGE"),
    (r"insider|trading window|sast|substantial acquisition|disclosure under reg", "INSIDER"),
    (
        r"analyst|investor meet|investors? presentation|conference call|earnings call|transcript|audio recording",
        "INVESTOR_MEET",
    ),
    (r"press release|media release|newspaper", "PRESS_RELEASE"),
    (
        r"sebi|penalty|show cause|litigation|order of|tribunal|nclt|regulatory|gst|income tax|customs",
        "REGULATORY",
    ),
    (
        r"resignation|appointment|director|kmp|key managerial|auditor|cfo|chief|company secretary|change in management",
        "GOVERNANCE",
    ),
    (
        r"general meeting|agm|egm|postal ballot|voting|record date|book closure|shareholders meeting",
        "MEETING",
    ),
    (r"update|clarification|intimation|certificate|compliance|closure of trading", "ROUTINE"),
)
_EVENT_PATTERNS = tuple((re.compile(pattern, re.IGNORECASE), kind) for pattern, kind in _EVENT_RULES)


def classify_announcement(category: str, text: str) -> str:
    haystack = f"{category} {text}"
    for pattern, kind in _EVENT_PATTERNS:
        if pattern.search(haystack):
            return kind
    return "OTHER"


def _kb(size: Any) -> Decimal | None:
    value = _blank_to_none(size)
    if value is None:
        return None
    number, _, unit = value.partition(" ")
    try:
        amount = Decimal(number)
    except ArithmeticError:
        return None
    return {"KB": amount, "MB": amount * 1024, "Bytes": amount / 1024, "bytes": amount / 1024}.get(
        unit, amount
    )


def announcements(content: bytes, day: date) -> list[DocumentRow]:
    """The monthly announcement list: one row per filing with its PDF link."""
    records = []
    for item in orjson.loads(content):
        symbol = _blank_to_none(item.get("symbol"))
        if symbol is None:
            continue
        category = (_blank_to_none(item.get("desc")) or "Announcement").strip()
        text = (item.get("attchmntText") or "").strip()
        records.append(
            {
                "document_id": str(item["seq_id"]),
                "symbol": symbol,
                "isin": _blank_to_none(item.get("sm_isin")),
                "company_name": item.get("sm_name") or symbol,
                "broadcast_at": _ist(item["an_dt"], "%d-%b-%Y %H:%M:%S"),
                "category": category,
                "event_kind": classify_announcement(category, text),
                "summary": text[:2000],
                "attachment_url": _blank_to_none(item.get("attchmntFile")),
                "attachment_kb": _kb(item.get("attFileSize")),
                "has_xbrl": bool(item.get("hasXbrl")),
                "industry": _blank_to_none(item.get("smIndustry")),
            }
        )
    return _DOCUMENTS.validate_python(records)


def board_meetings(content: bytes, day: date) -> list[BoardMeetingRow]:
    records = []
    for item in orjson.loads(content):
        if not _blank_to_none(item.get("symbol")):
            continue
        records.append(
            {
                "symbol": item["symbol"],
                "meeting_date": datetime.strptime(item["date"].title(), "%d-%b-%Y").date(),
                "purpose": (_blank_to_none(item.get("purpose")) or "Other").strip(),
                "company_name": item.get("company") or item["symbol"],
                "description": (item.get("bm_desc") or "").strip()[:2000],
            }
        )
    return _MEETINGS.validate_python(records)


def credit_ratings(content: bytes, day: date) -> list[CreditRatingRow]:
    records = []
    for item in orjson.loads(content):
        symbol = _blank_to_none(item.get("Symbol"))
        if symbol in ("NOTLISTED",):
            symbol = None
        rated = _blank_to_none(item.get("DateofCR"))
        records.append(
            {
                "rating_id": str(item["AppID"]),
                "symbol": symbol,
                "isin": _blank_to_none(item.get("ISIN")),
                "company_name": item.get("CompanyName") or symbol or "-",
                "agency": item.get("NameOfCRAgency") or "-",
                "rating": item.get("CreditRating") or "-",
                "outlook": _blank_to_none(item.get("Outlook")),
                "action": item.get("RatingAction") or "Other",
                "rating_earlier": _blank_to_none(item.get("CreditRatingEarlier")),
                "rated_on": datetime.strptime(rated, "%d-%m-%Y").date() if rated else None,
                "broadcast_at": _ist(item["BroadcastDateTime"].title(), "%d-%b-%Y %H:%M:%S"),
            }
        )
    return _RATINGS.validate_python(records)
