"""
Parsers for the NSE files (spec §82.1): bytes in, validated records out. No I/O, no database.

Every parser takes the file's logical date and checks the dates inside the file against it
where the file carries one — a file cached under the wrong date would otherwise load quietly
into the wrong day.
"""

import csv
import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import orjson
import polars as pl
from pydantic import TypeAdapter

from equity_engine.parsers.models import (
    EQUITY_SERIES,
    BandRow,
    CircuitHitRow,
    CorporateActionRow,
    DailyReportsRows,
    DealRow,
    DeliveryRow,
    DerivativeOiRow,
    IndexRow,
    MarketCapRow,
    PriceRow,
    SecurityRow,
    SurveillanceRow,
)

_PRICES = TypeAdapter(list[PriceRow])
_DELIVERIES = TypeAdapter(list[DeliveryRow])
_MARKET_CAPS = TypeAdapter(list[MarketCapRow])
_ACTIONS = TypeAdapter(list[CorporateActionRow])
_HITS = TypeAdapter(list[CircuitHitRow])
_DERIVATIVES = TypeAdapter(list[DerivativeOiRow])
_SECURITIES = TypeAdapter(list[SecurityRow])
_BANDS = TypeAdapter(list[BandRow])
_DEALS = TypeAdapter(list[DealRow])
_INDEX = TypeAdapter(list[IndexRow])
_SURVEILLANCE = TypeAdapter(list[SurveillanceRow])


def _read_csv(content: bytes) -> list[dict[str, str]]:
    """Every column as a stripped string; header names stripped too (NSE pads both)."""
    frame = pl.read_csv(io.BytesIO(content), infer_schema=False)
    frame = frame.rename({name: name.strip() for name in frame.columns})
    frame = frame.with_columns(pl.all().str.strip_chars().fill_null(""))
    return frame.to_dicts()


def _only_member(content: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        if len(names) != 1:
            raise ValueError(f"expected one file in the archive, found {names}")
        return archive.read(names[0])


def _require_date(found: date, expected: date, what: str) -> None:
    if found != expected:
        raise ValueError(f"{what}: the file is dated {found} but is cached under {expected}")


def _date(value: str, layout: str) -> date:
    return datetime.strptime(value, layout).date()


# ------------------------------------------------------------------ prices


def bhav_udiff(content: bytes, day: date) -> list[PriceRow]:
    records = []
    for line in _read_csv(_only_member(content)):
        if line["FinInstrmTp"] != "STK" or line["SctySrs"] not in EQUITY_SERIES:
            continue
        records.append(
            {
                "isin": line["ISIN"],
                "symbol": line["TckrSymb"],
                "series": line["SctySrs"],
                "trade_date": line["TradDt"],
                "open": line["OpnPric"],
                "high": line["HghPric"],
                "low": line["LwPric"],
                "close": line["ClsPric"],
                "last": line["LastPric"],
                "prev_close": line["PrvsClsgPric"],
                "volume": line["TtlTradgVol"],
                "turnover": line["TtlTrfVal"],
                "trades": line["TtlNbOfTxsExctd"],
            }
        )
    rows = _PRICES.validate_python(records)
    for found in {price.trade_date for price in rows}:
        _require_date(found, day, "UDiFF bhavcopy")
    return rows


def _legacy_date(text: str) -> date:
    """``02-JAN-2019`` in most files; some (from 13-Jul-2020) write a two-digit year, ``13-Jul-20``."""
    layout = "%d-%b-%Y" if len(text.rsplit("-", 1)[-1]) == 4 else "%d-%b-%y"
    return _date(text.title(), layout)


def bhav_legacy(content: bytes, day: date) -> list[PriceRow]:
    records = []
    for line in _read_csv(_only_member(content)):
        if line["SERIES"] not in EQUITY_SERIES:
            continue
        records.append(
            {
                "isin": line["ISIN"],
                "symbol": line["SYMBOL"],
                "series": line["SERIES"],
                "trade_date": _legacy_date(line["TIMESTAMP"]),
                "open": line["OPEN"],
                "high": line["HIGH"],
                "low": line["LOW"],
                "close": line["CLOSE"],
                "last": line["LAST"],
                "prev_close": line["PREVCLOSE"],
                "volume": line["TOTTRDQTY"],
                "turnover": line["TOTTRDVAL"],
                "trades": line["TOTALTRADES"],
            }
        )
    rows = _PRICES.validate_python(records)
    for found in {price.trade_date for price in rows}:
        _require_date(found, day, "legacy bhavcopy")
    return rows


def delivery_mto(content: bytes, day: date) -> list[DeliveryRow]:
    """``20,<sr>,<symbol>,<series>,<traded>,<deliverable>,<pct>`` under a four-line preamble whose
    second line carries the date as ``10,MTO,<ddmmyyyy>,...``."""
    lines = content.decode("utf-8").splitlines()
    header = lines[1].split(",")
    if header[:2] != ["10", "MTO"]:
        raise ValueError(f"MTO file: unexpected header line {lines[1]!r}")
    _require_date(_date(header[2], "%d%m%Y"), day, "MTO delivery file")
    records = []
    for line in lines:
        fields = [field.strip() for field in line.split(",")]
        if fields[0] != "20":
            continue
        if len(fields) != 7:
            raise ValueError(f"MTO file: expected 7 fields, got {line!r}")
        if fields[3] not in EQUITY_SERIES:
            continue
        records.append(
            {
                "symbol": fields[2],
                "series": fields[3],
                "trade_date": day,
                "traded_qty": fields[4],
                "deliv_qty": fields[5],
                "deliv_pct": fields[6],
            }
        )
    return _DELIVERIES.validate_python(records)


def market_cap(content: bytes, day: date) -> list[MarketCapRow]:
    """The ``mcap<ddmmyyyy>.csv`` member of the daily reports bundle: issue size (shares
    outstanding) and market cap per security.

    Older bundles have no such member (the 2019 ones do not), which is "not published for that
    date", so the result is empty rather than an error. A security that did not trade that day
    is listed with an earlier last-trade date, or the text ``Not Traded``, and is left out: it
    has no price row for the day to carry the figure."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = [name for name in archive.namelist() if name.lower().startswith("mcap")]
        if not members:
            return []
        if len(members) != 1:
            raise ValueError(f"expected one market-cap file in the bundle, found {members}")
        lines = _read_csv(archive.read(members[0]))
    records = []
    for line in lines:
        if line["Series"] not in EQUITY_SERIES:
            continue
        trade_date = _date(line["Trade Date"].title(), "%d %b %Y")
        _require_date(trade_date, day, "market-cap file")
        if line["Last Trade Date"].upper() != line["Trade Date"].upper():
            continue
        records.append(
            {
                "symbol": line["Symbol"],
                "series": line["Series"],
                "trade_date": trade_date,
                "face_value": line["Face Value(Rs.)"],
                "issue_size": line["Issue Size"],
                "market_cap": line["Market Cap(Rs.)"],
            }
        )
    return _MARKET_CAPS.validate_python(records)


# ------------------------------------------------------------------ master


def _master(content: bytes, segment: str, columns: dict[str, str], date_layout: str) -> list[SecurityRow]:
    records = [
        {
            "isin": line[columns["isin"]],
            "symbol": line["SYMBOL"],
            "name": line[columns["name"]],
            "series": line["SERIES"],
            "segment": segment,
            "listing_date": _date(line[columns["listing"]].title(), date_layout),
            "face_value": line[columns["face"]],
            "paid_up_value": line[columns["paid_up"]],
        }
        for line in _read_csv(content)
    ]
    return _SECURITIES.validate_python(records)


def equity_master(content: bytes, day: date) -> list[SecurityRow]:
    columns = {
        "isin": "ISIN NUMBER",
        "name": "NAME OF COMPANY",
        "listing": "DATE OF LISTING",
        "face": "FACE VALUE",
        "paid_up": "PAID UP VALUE",
    }
    return _master(content, "MAIN", columns, "%d-%b-%Y")


def sme_master(content: bytes, day: date) -> list[SecurityRow]:
    columns = {
        "isin": "ISIN_NUMBER",
        "name": "NAME_OF_COMPANY",
        "listing": "DATE_OF_LISTING",
        "face": "FACE_VALUE",
        "paid_up": "PAID_UP_VALUE",
    }
    return _master(content, "SME", columns, "%d-%b-%y")


def price_band(content: bytes, day: date) -> list[BandRow]:
    records = [
        {"symbol": line["Symbol"], "series": line["Series"], "band": line["Band"], "remarks": line["Remarks"]}
        for line in _read_csv(content)
    ]
    return _BANDS.validate_python(records)


# ------------------------------------------------------------------ deals


def _deals(content: bytes, kind: str) -> list[DealRow]:
    sequence: dict[date, int] = {}
    records = []
    for line in _read_csv(content):
        deal_date = _date(line["Date"].title(), "%d-%b-%Y")
        sequence[deal_date] = sequence.get(deal_date, 0) + 1
        records.append(
            {
                "kind": kind,
                "deal_date": deal_date,
                "seq": sequence[deal_date],
                "symbol": line["Symbol"],
                "security_name": line["Security Name"],
                "client_name": line["Client Name"],
                "side": line["Buy/Sell"],
                "quantity": line["Quantity Traded"],
                "price": line["Trade Price / Wght. Avg. Price"],
                # block.csv has no Remarks column at all
                "remarks": line["Remarks"] if kind == "BULK" else "",
            }
        )
    return _DEALS.validate_python(records)


def bulk_deal(content: bytes, day: date) -> list[DealRow]:
    return _deals(content, "BULK")


def block_deal(content: bytes, day: date) -> list[DealRow]:
    return _deals(content, "BLOCK")


# ------------------------------------------------------------------ index and surveillance


def index_constituents(content: bytes, index_code: str) -> list[IndexRow]:
    records = [
        {
            "index_code": index_code,
            "isin": line["ISIN Code"],
            "symbol": line["Symbol"],
            "company_name": line["Company Name"],
            "industry": line["Industry"],
        }
        for line in _read_csv(content)
    ]
    return _INDEX.validate_python(records)


def _surveillance(items: list[dict[str, Any]], list_code: str, stage_key: str) -> list[dict[str, Any]]:
    return [
        {
            "list_code": list_code,
            "isin": item["isin"],
            "symbol": item["symbol"],
            "company_name": item["companyName"],
            "stage": item[stage_key],
            "surv_code": item["survCode"],
            "surv_desc": item["survDesc"],
        }
        for item in items
    ]


def surveillance_asm(content: bytes, day: date) -> list[SurveillanceRow]:
    payload = orjson.loads(content)
    records = _surveillance(payload["longterm"]["data"], "ASM_LT", "asmSurvIndicator")
    records += _surveillance(payload["shortterm"]["data"], "ASM_ST", "asmSurvIndicator")
    return _SURVEILLANCE.validate_python(records)


def surveillance_gsm(content: bytes, day: date) -> list[SurveillanceRow]:
    return _SURVEILLANCE.validate_python(_surveillance(orjson.loads(content), "GSM", "gsmStage"))


def surveillance_esm(content: bytes, day: date) -> list[SurveillanceRow]:
    return _SURVEILLANCE.validate_python(_surveillance(orjson.loads(content), "ESM", "esmSurvIndicator"))


# ------------------------------------------------------------------ daily reports bundle

# Series whose corporate actions and band hits are kept: equity main board and SME, including the
# trade-for-trade series (an action on a BE name still adjusts its price history).
ACTION_SERIES = frozenset({"EQ", "BE", "BZ", "SM", "ST", "SZ"})

_MONEY = r"(?:RS\.?|RE\.?|INR)?\s*([0-9]+(?:\.[0-9]+)?)"
_RATIO = re.compile(r"([0-9]+)\s*:\s*([0-9]+)")
_SPLIT = re.compile(
    r"(?:FV\s*SPLI?T|SPLIT|SUB-?DIVISION).*?(?:FRM|FROM)\s*(?:RS\.?|RE\.?)?\s*([0-9]+(?:\.[0-9]+)?).*?TO\s*(?:RS\.?|RE\.?)?\s*([0-9]+(?:\.[0-9]+)?)"
)
_CONSOLIDATION = re.compile(
    r"CONSOLIDAT\w*.*?(?:RS\.?|RE\.?)?\s*([0-9]+(?:\.[0-9]+)?)\s*TO\s*(?:RS\.?|RE\.?)?\s*([0-9]+(?:\.[0-9]+)?)"
)
_DIVIDEND_AMOUNT = re.compile(r"(?:DIV\w*?|DV)\s*[-:]?\s*" + _MONEY)


def classify_action(purpose: str) -> tuple[str, Decimal | None, Decimal | None]:
    """(kind, dividend amount, adjustment factor) from the bundle's purpose text.

    The factor is old shares / new shares: a 1:1 bonus is 0.5 (each old share becomes two), a
    split from Rs 10 to Rs 2 is 0.2, a consolidation from Rs 1 to Rs 10 is 10. Multiplying a
    pre-ex-date price by the factor puts it on today's share basis (spec §84)."""
    text = " ".join(purpose.upper().split())
    if re.search(r"\bBONUS\b", text):
        ratio = _RATIO.search(text)
        if ratio:
            new, old = Decimal(ratio.group(1)), Decimal(ratio.group(2))
            return "BONUS", None, old / (old + new)
        return "BONUS", None, None
    split = _SPLIT.search(text)
    if split and re.search(r"SPLI?T|SUB-?DIVISION", text):
        old, new = Decimal(split.group(1)), Decimal(split.group(2))
        return ("SPLIT", None, new / old) if old > new else ("CONSOLIDATION", None, new / old)
    consolidation = _CONSOLIDATION.search(text)
    if consolidation:
        old, new = Decimal(consolidation.group(1)), Decimal(consolidation.group(2))
        return "CONSOLIDATION", None, new / old
    if re.search(r"CAP(?:ITAL)?\s*RED", text):
        # A capital reduction changes face value; whether the share count changes is not in the
        # text, so no adjustment factor is derived from it.
        return "OTHER", None, None
    if re.search(r"RIGHTS?|RGHTS", text):
        return "RIGHTS", None, None
    if re.search(r"BUY\s*-?\s*BACK", text):
        return "BUYBACK", None, None
    if re.search(r"DE-?MERGER|SCHEME OF ARRANGEMENT|ARRANGEMENT", text):
        return "DEMERGER", None, None
    if re.search(r"\bMERGER|AMALGAMATION", text):
        return "MERGER", None, None
    if re.search(r"\bDIV|DVSPDV|SPLDIV", text):
        amount = _DIVIDEND_AMOUNT.search(text)
        return "DIVIDEND", Decimal(amount.group(1)) if amount else None, None
    if re.search(r"\bAGM\b|\bEGM\b|\bEOGM\b|GENERAL MEETING|MEETING|ANNUAL", text):
        return "MEETING", None, None
    return "OTHER", None, None


def _bundle_date(value: str) -> date | None:
    text = value.strip()
    if not text:
        return None
    for layout in ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, layout).date()
        except ValueError:
            continue
    raise ValueError(f"unreadable date in daily reports bundle: {value!r}")


def _loose_csv(content: bytes | None) -> list[dict[str, str]]:
    """Header-keyed rows with every key and value stripped; blank or ragged lines tolerated."""
    if not content:
        return []
    reader = csv.DictReader(io.StringIO(content.decode("latin-1")))
    out = []
    for line in reader:
        cleaned = {key.strip(): (value or "").strip() for key, value in line.items() if key}
        if any(cleaned.values()):
            out.append(cleaned)
    return out


def _member(archive: zipfile.ZipFile, prefix: str) -> bytes | None:
    members = [name for name in archive.namelist() if name.lower().startswith(prefix)]
    if not members:
        return None
    if len(members) != 1:
        raise ValueError(f"expected one {prefix}* file in the bundle, found {members}")
    return archive.read(members[0])


def daily_reports(content: bytes, day: date) -> DailyReportsRows:
    """The daily reports bundle (``PR<ddmmyy>.zip``): market cap (``mcap``), corporate actions
    (``bc``) and price-band hits (``bh``). Members missing from older bundles give empty lists."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        actions_csv = _member(archive, "bc")
        hits_csv = _member(archive, "bh")
    actions: list[dict[str, Any]] = []
    # Security names in older bundles carry Latin-1 bytes and some lines have stray extra commas,
    # so these two members go through the standard library reader, not the strict one.
    for line in _loose_csv(actions_csv):
        if line.get("SERIES") not in ACTION_SERIES:
            continue
        ex_date = _bundle_date(line["EX_DT"])
        if ex_date is None:
            continue  # announced without an ex-date yet; it reappears once dated
        kind, amount, factor = classify_action(line["PURPOSE"])
        actions.append(
            {
                "symbol": line["SYMBOL"],
                "series": line["SERIES"],
                "security_name": line["SECURITY"] or line["SYMBOL"],
                "ex_date": ex_date,
                "record_date": _bundle_date(line["RECORD_DT"]),
                "bc_start": _bundle_date(line["BC_STRT_DT"]),
                "bc_end": _bundle_date(line["BC_END_DT"]),
                "nd_start": _bundle_date(line["ND_STRT_DT"]),
                "nd_end": _bundle_date(line["ND_END_DT"]),
                "purpose": " ".join(line["PURPOSE"].split()),
                "kind": kind,
                "amount": amount,
                "adjust_factor": factor,
            }
        )
    hits: list[dict[str, Any]] = []
    for line in _loose_csv(hits_csv):
        if line.get("SERIES") in ACTION_SERIES and line.get("HIGH/LOW") in ("H", "L"):
            hits.append({"symbol": line["SYMBOL"], "series": line["SERIES"], "side": line["HIGH/LOW"]})
    return DailyReportsRows(
        market_caps=market_cap(content, day),
        actions=_ACTIONS.validate_python(actions),
        hits=_HITS.validate_python(hits),
    )


# ------------------------------------------------------------------ derivatives (spec §70)


def fo_bhav(content: bytes, day: date) -> list[DerivativeOiRow]:
    """The F&O UDiFF bhavcopy aggregated to one row per stock underlying: futures OI and its
    change across expiries, the near-month basis, and the put-call ratio by open interest.
    Index derivatives (NIFTY, BANKNIFTY …) are left out; the equity universe is stocks."""
    frame = pl.read_csv(_only_member(content), infer_schema_length=0)
    frame = frame.filter(pl.col("FinInstrmTp").is_in(["STF", "STO"]))
    if frame.is_empty():
        return []
    frame = frame.with_columns(
        pl.col("OpnIntrst").cast(pl.Int64, strict=False).fill_null(0),
        pl.col("ChngInOpnIntrst").cast(pl.Int64, strict=False).fill_null(0),
        pl.col("TtlTradgVol").cast(pl.Int64, strict=False).fill_null(0),
        pl.col("ClsPric").cast(pl.Float64, strict=False),
        pl.col("UndrlygPric").cast(pl.Float64, strict=False),
        pl.col("XpryDt").str.strptime(pl.Date, "%Y-%m-%d", strict=False),
    )
    futures = frame.filter(pl.col("FinInstrmTp") == "STF")
    near = (
        futures.filter(pl.col("XpryDt") >= day)
        .sort("XpryDt")
        .group_by("TckrSymb", maintain_order=True)
        .agg(
            pl.col("XpryDt").first().alias("near_expiry"),
            pl.col("ClsPric").first().alias("near_close"),
            pl.col("UndrlygPric").first().alias("underlying_close"),
        )
    )
    fut_agg = futures.group_by("TckrSymb").agg(
        pl.col("OpnIntrst").sum().alias("futures_oi"),
        pl.col("ChngInOpnIntrst").sum().alias("futures_oi_change"),
        pl.col("TtlTradgVol").sum().alias("futures_volume"),
    )
    options = (
        frame.filter(pl.col("FinInstrmTp") == "STO")
        .group_by("TckrSymb")
        .agg(
            pl.col("OpnIntrst").filter(pl.col("OptnTp") == "CE").sum().alias("call_oi"),
            pl.col("OpnIntrst").filter(pl.col("OptnTp") == "PE").sum().alias("put_oi"),
        )
    )
    merged = (
        fut_agg.join(near, on="TckrSymb", how="left").join(options, on="TckrSymb", how="left").fill_null(0)
    )
    records = []
    for line in merged.to_dicts():
        near_close, underlying = line.get("near_close") or None, line.get("underlying_close") or None
        basis = round((near_close / underlying - 1) * 100, 4) if near_close and underlying else None
        call_oi, put_oi = int(line["call_oi"]), int(line["put_oi"])
        records.append(
            {
                "symbol": line["TckrSymb"],
                "trade_date": day,
                "futures_oi": int(line["futures_oi"]),
                "futures_oi_change": int(line["futures_oi_change"]),
                "futures_volume": int(line["futures_volume"]),
                "near_expiry": line.get("near_expiry") or None,
                "near_close": near_close,
                "underlying_close": underlying,
                "basis_pct": basis,
                "call_oi": call_oi,
                "put_oi": put_oi,
                "pcr_oi": round(put_oi / call_oi, 4) if call_oi else None,
            }
        )
    return _DERIVATIVES.validate_python(records)
