"""Parsers against small slices cut from real exchange files (tests/fixtures)."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from equity_engine.parsers import nse
from equity_engine.parsers.models import PriceRow

DAY = date(2026, 9, 30)


def test_udiff_keeps_equity_series_and_drops_bonds(fixtures: Path):
    rows = nse.bhav_udiff((fixtures / "BhavCopy_NSE_CM_0_0_0_20260930_F_0000.csv.zip").read_bytes(), DAY)
    assert {row.series for row in rows} == {"EQ", "BE", "SM"}  # the two GB gold bonds are gone
    reliance = next(row for row in rows if row.symbol == "RELIANCE")
    assert reliance.isin == "INE002A01018"
    assert reliance.trade_date == DAY
    assert reliance.low <= reliance.close <= reliance.high
    assert isinstance(reliance.turnover, Decimal) and reliance.turnover > 0


def test_udiff_refuses_a_file_cached_under_the_wrong_date(fixtures: Path):
    content = (fixtures / "BhavCopy_NSE_CM_0_0_0_20260930_F_0000.csv.zip").read_bytes()
    with pytest.raises(ValueError, match="dated 2026-09-30 but is cached under 2026-09-29"):
        nse.bhav_udiff(content, date(2026, 9, 29))


def test_legacy_bhavcopy(fixtures: Path):
    rows = nse.bhav_legacy((fixtures / "cm02JAN2019bhav.csv.zip").read_bytes(), date(2019, 1, 2))
    assert len(rows) == 4 and {row.series for row in rows} == {"EQ"}  # N1 / N3 debentures dropped
    assert {row.trade_date for row in rows} == {date(2019, 1, 2)}
    assert all(row.isin.startswith("INE") for row in rows)


def test_legacy_bhavcopy_date_with_a_two_digit_year():
    assert nse._legacy_date("02-JAN-2019") == date(2019, 1, 2)
    assert nse._legacy_date("13-Jul-20") == date(2020, 7, 13)


def test_delivery_file(fixtures: Path):
    rows = nse.delivery_mto((fixtures / "MTO_30092026.DAT").read_bytes(), DAY)
    assert {row.symbol for row in rows} == {"20MICRONS", "RELIANCE", "TCS"}
    micron = next(row for row in rows if row.symbol == "20MICRONS")
    assert (micron.traded_qty, micron.deliv_qty, micron.deliv_pct) == (76779, 34719, Decimal("45.22"))
    with pytest.raises(ValueError, match="cached under"):
        nse.delivery_mto((fixtures / "MTO_30092026.DAT").read_bytes(), date(2026, 9, 29))


def test_masters(fixtures: Path):
    main = nse.equity_master((fixtures / "EQUITY_L.csv").read_bytes(), DAY)
    reliance = next(row for row in main if row.symbol == "RELIANCE")
    assert (reliance.isin, reliance.segment, reliance.listing_date) == (
        "INE002A01018",
        "MAIN",
        date(1995, 11, 29),
    )
    sme = nse.sme_master((fixtures / "SME_EQUITY_L.csv").read_bytes(), DAY)
    # The SME file writes a two-digit year: 30-Sep-26.
    assert all(row.segment == "SME" and row.listing_date.year >= 2012 for row in sme)


def test_price_band_and_deals(fixtures: Path):
    bands = nse.price_band((fixtures / "sec_list.csv").read_bytes(), DAY)
    assert next(row for row in bands if row.symbol == "RELIANCE").band == "No Band"
    bulk = nse.bulk_deal((fixtures / "bulk.csv").read_bytes(), DAY)
    assert [row.seq for row in bulk] == [1, 2, 3] and bulk[0].kind == "BULK"
    block = nse.block_deal((fixtures / "block.csv").read_bytes(), DAY)
    assert block[0].kind == "BLOCK" and block[0].remarks == ""  # block.csv has no Remarks column


def test_index_file_keeps_placeholder_constituents(fixtures: Path):
    rows = nse.index_constituents((fixtures / "ind_nifty500list.csv").read_bytes(), "nifty500")
    assert "DUM545A01024" in {row.isin for row in rows}  # "Dummy HEG Ltd."
    assert {row.index_code for row in rows} == {"nifty500"}


def test_surveillance_lists(fixtures: Path):
    asm = nse.surveillance_asm((fixtures / "reportASM.json").read_bytes(), DAY)
    assert [row.list_code for row in asm] == ["ASM_LT", "ASM_LT", "ASM_ST"]
    assert {
        row.list_code for row in nse.surveillance_gsm((fixtures / "reportGSM.json").read_bytes(), DAY)
    } == {"GSM"}
    assert {
        row.list_code for row in nse.surveillance_esm((fixtures / "reportESM.json").read_bytes(), DAY)
    } == {"ESM"}


def test_market_cap_from_the_daily_reports_bundle(fixtures: Path):
    day = date(2026, 10, 1)
    rows = nse.market_cap((fixtures / "PR011026.zip").read_bytes(), day)
    reliance = next(row for row in rows if row.symbol == "RELIANCE")
    assert reliance.issue_size > 10_000_000_000 and reliance.market_cap > 0
    # A security whose last trade is an earlier date is left out.
    assert all(row.trade_date == day for row in rows) and len(rows) == 3
    with pytest.raises(ValueError, match="cached under"):
        nse.market_cap((fixtures / "PR011026.zip").read_bytes(), date(2026, 9, 30))


def test_a_bundle_without_a_market_cap_file_yields_nothing(fixtures: Path):
    assert nse.market_cap((fixtures / "PR020119.zip").read_bytes(), date(2019, 1, 2)) == []


def test_a_bad_price_row_fails_the_file():
    good = {
        "isin": "INE002A01018", "symbol": "RELIANCE", "series": "EQ", "trade_date": DAY, "open": "10",
        "high": "12", "low": "9", "close": "11", "last": "11", "prev_close": "10", "volume": 5,
        "turnover": "55", "trades": 1,
    }  # fmt: skip
    PriceRow.model_validate(good)
    for field, value in (
        ("close", "13"),
        ("low", "12.5"),
        ("isin", "XX0000000000"),
        ("volume", -1),
        ("close", "0"),
    ):
        with pytest.raises(ValidationError):
            PriceRow.model_validate(good | {field: value})
