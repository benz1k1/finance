"""
Index membership history (spec §82.2) from the files already in raw/_reference/index_history:
NSE's yearly constituent lists for the Nifty 500 (CSV for Apr-2013, PDF for Mar-2014 to
Mar-2022; the 2023–2026 zips carry no Nifty 500 file), plus the newest daily constituent
snapshot. Symbols are resolved to ISINs through today's master, so a company renamed since then
stays unresolved (NULL isin) and is listed in the load report.
"""

import io
import re
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from loguru import logger
from pypdf import PdfReader

from equity_engine.config import RAW_DIR
from equity_engine.db import execute, execute_many, rows, transaction
from equity_engine.parsers import nse
from equity_engine.sources import bronze
from equity_engine.sources.registry import BY_ID

REFERENCE = RAW_DIR / "_reference" / "index_history"
_SYMBOL = re.compile(r"^([A-Z][A-Z0-9&-]{1,19})\s+\S")
_NOT_SYMBOLS = {
    "SYMBOL",
    "CONSTITUENTS",
    "NIFTY",
    "CNX",
    "INDEX",
    "MARCH",
    "APRIL",
    "NSE",
    "NOTE",
    "DISCLAIMER",
    "INDUSTRY",
    "SECURITY",
    "CLOSE",
    "RS",
}
_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def _snapshot_date(zip_name: str) -> date:
    """indices_dataMar2019.zip -> the last day of that month."""
    match = re.search(r"([A-Z][a-z]{2})(\d{4})", zip_name)
    if not match:
        raise ValueError(f"no month in {zip_name}")
    month, year = _MONTHS[match.group(1)], int(match.group(2))
    import calendar  # noqa: PLC0415 — one call

    return date(year, month, calendar.monthrange(year, month)[1])


def _symbols_from_pdf(content: bytes) -> list[str]:
    found: list[str] = []
    for page in PdfReader(io.BytesIO(content)).pages:
        for line in (page.extract_text() or "").splitlines():
            match = _SYMBOL.match(line.strip())
            if match and match.group(1) not in _NOT_SYMBOLS and not match.group(1).isdigit():
                found.append(match.group(1))
    return list(dict.fromkeys(found))


def _symbols_from_csv(content: bytes) -> list[str]:
    import csv  # noqa: PLC0415 — one call

    reader = csv.DictReader(io.StringIO(content.decode("utf-8", "replace")))
    column = next((c for c in (reader.fieldnames or []) if c.strip().lower() == "symbol"), None)
    if column is None:
        raise ValueError("no Symbol column in the constituent CSV")
    return [line[column].strip() for line in reader if line[column].strip()]


def _full_master() -> list[Any]:
    source = BY_ID["nse_equity_master"]
    cached = bronze.cached_dates(source)
    if not cached:
        return []
    return list(nse.equity_master(bronze.path_for(source, cached[-1]).read_bytes(), cached[-1]))


def snapshots(index_code: str = "nifty500") -> list[tuple[date, str, list[str]]]:
    """(as_of, source file, symbols) for every yearly file that carries the index."""
    out = []
    for archive in sorted(REFERENCE.glob("indices_data*.zip")):
        with zipfile.ZipFile(archive) as z:
            members = [n for n in z.namelist() if re.search(r"(nifty_?500|cnx500)", n, re.IGNORECASE)]
            if not members:
                continue
            content = z.read(members[0])
            symbols = (
                _symbols_from_csv(content)
                if members[0].lower().endswith(".csv")
                else _symbols_from_pdf(content)
            )
            out.append((_snapshot_date(archive.name), f"{archive.name}:{Path(members[0]).name}", symbols))
    return out


def load(index_code: str = "nifty500") -> dict[str, Any]:
    """Load every yearly snapshot plus the newest daily constituent list; resolve ISINs via the master."""
    report: dict[str, Any] = {"snapshots": [], "unresolved": Counter()}
    with transaction() as connection:
        master = {
            item["nse_symbol"]: item["isin"]
            for item in rows(connection, "SELECT nse_symbol, isin FROM security")
        }
        # The master was pruned to the universe, so past members that have since left the index
        # are resolved through NSE's full equity list, which is cached whole (symbols as of today;
        # a company renamed since its membership stays unresolved).
        for item in _full_master():
            master.setdefault(item.symbol, item.isin)
        for as_of, source, symbols in snapshots(index_code):
            if len(symbols) < 400:
                logger.warning(f"{source}: only {len(symbols)} symbols read; skipped")
                continue
            execute(
                connection,
                "DELETE FROM index_membership WHERE index_code = :i AND as_of = :d",
                {"i": index_code, "d": as_of},
            )
            execute_many(
                connection,
                "INSERT INTO index_membership (index_code, as_of, symbol, isin, source) VALUES (:i, :d, :s, :isin, :src)",
                [
                    {"i": index_code, "d": as_of, "s": symbol, "isin": master.get(symbol), "src": source}
                    for symbol in symbols
                ],
            )
            unresolved = [s for s in symbols if s not in master]
            report["unresolved"][str(as_of)] = len(unresolved)
            report["snapshots"].append(
                {"as_of": str(as_of), "symbols": len(symbols), "unresolved": len(unresolved)}
            )
        newest = rows(
            connection,
            """
            SELECT c.isin, s.nse_symbol AS symbol, c.snapshot_date FROM index_constituent_snapshot c JOIN security s USING (isin)
             WHERE c.index_code = :i AND c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot WHERE index_code = :i)
            """,
            {"i": index_code},
        )
        if newest:
            as_of = newest[0]["snapshot_date"]
            execute(
                connection,
                "DELETE FROM index_membership WHERE index_code = :i AND as_of = :d",
                {"i": index_code, "d": as_of},
            )
            execute_many(
                connection,
                "INSERT INTO index_membership (index_code, as_of, symbol, isin, source) VALUES (:i, :d, :s, :isin, 'index_constituent_snapshot')",
                [{"i": index_code, "d": as_of, "s": item["symbol"], "isin": item["isin"]} for item in newest],
            )
            report["snapshots"].append({"as_of": str(as_of), "symbols": len(newest), "unresolved": 0})
    return report
