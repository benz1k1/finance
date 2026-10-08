"""
One-time online lookup of a deal counterparty's public metadata (spec §65). Source: Wikipedia's
search and page-summary APIs — structured, free, and honest about absence. A hit is accepted only
when the page title shares the client's distinctive words, because a bare search for "Graviton
Research Capital" returns a science-fiction novel. Every response is cached under
``raw/_reference/client_meta/`` and never fetched twice (the project's cache rule); the result,
found or not, is written once to ``client_meta`` and never overwritten.
"""

import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import orjson
from loguru import logger
from sqlalchemy import Connection

from equity_engine.config import RAW_DIR
from equity_engine.db import execute, rows, transaction

CACHE_DIR = Path(RAW_DIR) / "_reference" / "client_meta"
SEARCH_URL = "https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=5&srsearch={q}"
SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
USER_AGENT = "EquityEngine/1.0 (https://github.com/benz1k1/finance; personal research tool) httpx"  # Wikipedia requires a contact
INTERVAL_SECONDS = 0.6

# Words that say nothing about who the client is; dropped from the query and the match test.
NOISE = {
    "LIMITED",
    "LTD",
    "PRIVATE",
    "PVT",
    "LLP",
    "LLC",
    "INC",
    "PLC",
    "CO",
    "COMPANY",
    "THE",
    "OF",
    "AND",
    "A/C",
    "ODI",
    "FPI",
    "MAURITIUS",
    "SINGAPORE",
    "PTE",
    "SA",
    "SE",
    "AG",
    "NV",
    "FUND",
    "FUNDS",
    "TRUST",
    "TRUSTEE",
    "TRUSTEES",
    "SCHEME",
    "SERIES",
    "ACCOUNT",
    "ON",
    "FOR",
    "AS",
    "ITS",
    "ETF",
    "INDIA",
    "INDIAN",
    "EQUITY",
    "SECURITIES",
    "CAPITAL",
    "MARKETS",
    "INVESTMENT",
    "INVESTMENTS",
    "MANAGEMENT",
    "HOLDINGS",
    "GLOBAL",
    "INTERNATIONAL",
    "EMERGING",
    "MUTUAL",
    "LIFE",
    "INSURANCE",
    "ASSET",
    "PORTFOLIO",
    "OPPORTUNITIES",
    "GROWTH",
    "SMALL",
    "CAP",
    "SMALLCAP",
    "MIDCAP",
    "MICROCAP",
    "VALUE",
    "SELECT",
    "FOCUSED",
    "FLEXI",
    "I",
    "II",
    "III",
    "IV",
}


def significant_words(name: str) -> list[str]:
    words = re.split(r"[^A-Z0-9]+", name.upper())
    return [w for w in words if w and w not in NOISE and not w.isdigit() and len(w) > 1]


def search_query(name: str) -> str:
    """The client's distinctive words plus a hint, so 'SBI MUTUAL FUND' finds the fund house."""
    words = significant_words(name)
    base = " ".join(words[:4]) if words else name
    upper = name.upper()
    hint = " mutual fund" if "MUTUAL FUND" in upper else (" insurance" if "INSURANCE" in upper else "")
    return (base + hint).strip()


def relevant(name: str, title: str) -> bool:
    """A page is about the client when its title carries the client's first distinctive word and
    every distinctive word of the title appears in the client's name: 'Tower Research Capital' is
    accepted for TOWER RESEARCH CAPITAL MARKETS INDIA, 'Societe Generale Ghana' is not accepted for
    SOCIETE GENERALE (Ghana is not in the name). The kind of entity must agree too."""
    wanted = significant_words(name)
    title_words = significant_words(title)
    if not wanted or not title_words:
        return False
    name_words = set(wanted) | set(re.split(r"[^A-Z0-9]+", name.upper()))
    if wanted[0] not in set(title_words) | set(re.split(r"[^A-Z0-9]+", title.upper())):
        return False
    if any(w not in name_words for w in title_words):
        return False
    upper_name, upper_title = name.upper(), title.upper()
    if "MUTUAL FUND" in upper_name and not any(
        w in upper_title for w in ("MUTUAL FUND", "ASSET MANAGEMENT", "FUND", "AMC")
    ):
        return False
    if "INSURANCE" in upper_name and "INSURANCE" not in upper_title and "ASSURANCE" not in upper_title:
        return False
    if "BANK" in upper_name.split() and "BANK" not in upper_title.split():
        return False
    return True


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:120] or "client"


def _cached_get(client: httpx.Client, key: str, url: str) -> dict[str, Any] | None:
    """Fetch once; the response body is kept on disk for good and served from there afterwards."""
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return orjson.loads(path.read_bytes())
    time.sleep(INTERVAL_SECONDS)
    for attempt in range(6):
        response = client.get(url)
        if response.status_code in (429, 503):
            wait = float(response.headers.get("Retry-After") or 2**attempt)
            logger.warning(f"client meta: {response.status_code} from Wikipedia, waiting {wait:.0f}s")
            time.sleep(wait)
            continue
        break
    if response.status_code == 404:
        payload: dict[str, Any] = {"status": 404}
    else:
        response.raise_for_status()  # 403 means blocked: stop and let the operator see it
        payload = response.json()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(payload))
    return payload


def lookup(client: httpx.Client, name: str) -> dict[str, Any]:
    query = search_query(name)
    slug = _slug(name)
    search = _cached_get(client, f"{slug}.search", SEARCH_URL.format(q=quote(query)))
    hits = (search or {}).get("query", {}).get("search", [])
    record: dict[str, Any] = {
        "client_name": name,
        "found": False,
        "source": "wikipedia",
        "query": query,
        "title": None,
        "description": None,
        "extract": None,
        "url": None,
    }
    for hit in hits:
        if not relevant(name, hit["title"]):
            continue
        summary = _cached_get(
            client, f"{slug}.summary", SUMMARY_URL.format(title=quote(hit["title"].replace(" ", "_")))
        )
        if not summary or summary.get("status") == 404 or summary.get("type") == "disambiguation":
            continue
        record.update(
            found=True,
            title=summary.get("title"),
            description=summary.get("description"),
            extract=(summary.get("extract") or "")[:1200] or None,
            url=(summary.get("content_urls") or {}).get("desktop", {}).get("page"),
        )
        break
    return record


def pending(connection: Connection) -> list[str]:
    return [
        r["client_name"]
        for r in rows(
            connection,
            """
            SELECT d.client_name FROM deal d
             WHERE NOT EXISTS (SELECT 1 FROM client_meta m WHERE m.client_name = d.client_name)
             GROUP BY d.client_name ORDER BY count(*) DESC, d.client_name  -- total order, so shards never overlap
            """,
        )
    ]


def lookup_all(limit: int | None = None, shard: tuple[int, int] = (0, 1)) -> dict[str, int]:
    """Look up every counterparty not yet in client_meta, most active first. Resumable: each name
    is written as soon as it is decided, and the disk cache makes a rerun free. ``shard=(i, n)``
    takes every n-th pending name from i, so n processes can run side by side."""
    with transaction() as connection:
        names = pending(connection)
    index, count = shard
    names = [name for j, name in enumerate(names) if j % count == index]
    if limit:
        names = names[:limit]
    tally = {"looked_up": 0, "found": 0}
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True) as client:
        for name in names:
            record = lookup(client, name)
            record["looked_up_at"] = datetime.now(UTC)
            with transaction() as connection:
                execute(
                    connection,
                    """
                    INSERT INTO client_meta (client_name, found, title, description, extract, url, source, query, looked_up_at)
                    VALUES (:client_name, :found, :title, :description, :extract, :url, :source, :query, :looked_up_at)
                    ON CONFLICT (client_name) DO NOTHING
                    """,
                    record,
                )
            tally["looked_up"] += 1
            tally["found"] += int(record["found"])
            if tally["looked_up"] % 50 == 0:
                logger.info(f"client meta: {tally['looked_up']} looked up, {tally['found']} found")
    return tally


def for_client(connection: Connection, name: str) -> dict[str, Any] | None:
    found = rows(connection, "SELECT * FROM client_meta WHERE client_name = :n", {"n": name})
    return found[0] if found else None
