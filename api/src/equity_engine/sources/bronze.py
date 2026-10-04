"""
Bronze: the permanent cache of downloaded files (spec §79, §83).

Three rules, all of which exist because the exchanges block clients that ask twice:

1. **A file on disk is never fetched again.** The cache is consulted before any request, and it
   is the disk that is consulted, not the database — so dropping and recreating the schema
   costs no network at all.
2. **A file on disk is never overwritten or deleted.** ``store`` refuses if the path exists.
3. **A known-absent date is remembered.** A weekday with no file is a market holiday; an empty
   ``<filename>.absent`` marker stops the next run asking for it again.

Layout: ``raw/<source_id>/<yyyy>/<server filename>`` for daily, monthly and document files, and
``raw/<source_id>/<yyyy>/<yyyy-mm-dd>__<server filename>`` for snapshots, whose server filename
carries no date. A document's year is the year of the period it reports. ``raw/_reference/`` holds files kept for later phases with no parser yet.
"""

import hashlib
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Connection

from equity_engine.config import RAW_DIR
from equity_engine.db import execute, row
from equity_engine.ids import new_id
from equity_engine.sources.registry import Source


class IncompleteDocument(ValueError):
    """A document that arrived truncated. It is not cached, so a later run fetches it again."""


def path_for(source: Source, day: date) -> Path:
    name = source.filename(day)
    if source.kind == "snapshot":
        name = f"{day.isoformat()}__{name}"
    return RAW_DIR / source.source_id / f"{day.year}" / name


def _absent_marker(source: Source, day: date) -> Path:
    path = path_for(source, day)
    return path.with_name(path.name + ".absent")


def document_path(source: Source, year: int, url: str) -> Path:
    """Where the document behind ``url`` is cached: the server's own filename, under the year of
    the period it reports. Filenames carry the filing id and timestamp, so they are unique."""
    name = url.rsplit("/", 1)[-1]
    if not name or name == "-":
        raise ValueError(f"{source.source_id}: no filename in {url!r}")
    return RAW_DIR / source.source_id / f"{year}" / name


def store_document(source: Source, path: Path, content: bytes) -> Path:
    """``store`` for a document source. Same rules: genuine content only, never overwritten."""
    if not content.lstrip(b"\xef\xbb\xbf \r\n\t").startswith(source.magic):
        raise ValueError(
            f"{source.source_id} {path.name}: the response does not look like the expected file "
            f"(starts {content[:40]!r}). Not cached."
        )
    terminator = b"%%EOF" if source.magic == b"%PDF" else b"xbrl>"
    if terminator not in content[-2048:]:
        # A transfer cut off part-way arrives as a normal response. Cached, it would be a
        # permanently broken file, because cached files are never fetched again.
        raise IncompleteDocument(
            f"{source.source_id} {path.name}: truncated ({len(content)} bytes). Not cached."
        )
    if path.exists():
        raise FileExistsError(f"{path} is already cached; cached files are never overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.{os.getpid()}.part")
    partial.write_bytes(content)
    os.replace(partial, path)
    return path


def cached(source: Source, day: date) -> Path | None:
    path = path_for(source, day)
    return path if path.is_file() else None


def is_absent(source: Source, day: date) -> bool:
    return _absent_marker(source, day).is_file()


def mark_absent(source: Source, day: date) -> None:
    marker = _absent_marker(source, day)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()


def store(source: Source, day: date, content: bytes) -> Path:
    """Write a freshly downloaded file. Atomic, and never over an existing one."""
    if not content.startswith(source.magic):
        raise ValueError(
            f"{source.source_id} {day}: the response does not look like the expected file "
            f"(starts {content[:40]!r}, expected {source.magic!r}). Not cached."
        )
    path = path_for(source, day)
    if path.exists():
        raise FileExistsError(f"{path} is already cached; cached files are never overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.{os.getpid()}.part")
    partial.write_bytes(content)
    os.replace(partial, path)
    return path


def register(connection: Connection, source: Source, day: date, path: Path) -> dict[str, Any]:
    """The ``raw_file`` row for a cached file, created from the file on disk when missing."""
    relative = str(path.relative_to(RAW_DIR))
    found = row(connection, "SELECT raw_id, sha256 FROM raw_file WHERE path = :p", {"p": relative})
    if found is not None:
        return found
    content = path.read_bytes()
    created = {
        "raw_id": new_id(),
        "source_id": source.source_id,
        "logical_date": day,
        "path": relative,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
        "fetched_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
    }
    execute(
        connection,
        "INSERT INTO raw_file (raw_id, source_id, logical_date, path, sha256, size_bytes, fetched_at) "
        "VALUES (:raw_id, :source_id, :logical_date, :path, :sha256, :size_bytes, :fetched_at)",
        created,
    )
    return created


def cached_months(source: Source) -> list[date]:
    """Every month this monthly source has a file for, oldest first, as first-of-month dates."""
    prefix, _, suffix = source.filename_template.partition("{yyyy_mm}")
    found = []
    for path in (RAW_DIR / source.source_id).glob("*/*"):
        name = path.name
        if path.is_file() and name.startswith(prefix) and name.endswith(suffix) and suffix:
            found.append(date.fromisoformat(name[len(prefix) : len(name) - len(suffix)] + "-01"))
    return sorted(found)


def cached_dates(source: Source) -> list[date]:
    """Every date this snapshot source has a file for, oldest first (read from disk)."""
    root = RAW_DIR / source.source_id
    suffix = f"__{source.filename_template}"
    found = [
        date.fromisoformat(path.name[:10])
        for path in root.glob("*/*")
        if path.is_file() and path.name.endswith(suffix)
    ]
    return sorted(found)
