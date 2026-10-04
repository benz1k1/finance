"""
The one HTTP client the ingester uses (spec §82.1).

Paced on purpose: NSE's filing-feed host started answering "Access Denied" after about sixty
quick requests, so request *starts* to a host group are spaced ``min_interval`` apart, and a
denial stops the whole run instead of being retried. A 404 is an answer ("no file for that
date"), not an error.

A timeout is not a denial, but ten in a row are treated as one (see ``_transport_failure``).

Thread-safe: several workers may share one ``Fetcher``. The spacing is global across them, so
adding workers raises throughput only as far as the interval allows, and after the first denial
every other worker's next request fails fast without touching the network.
"""

import threading
import time
from dataclasses import dataclass

import httpx
from loguru import logger

from equity_engine.config import INGEST_MIN_INTERVAL_SECONDS, INGEST_TIMEOUT_SECONDS, INGEST_USER_AGENT
from equity_engine.sources.registry import Source

_REFERER = {
    "nse_archive": "https://www.nseindia.com/",
    "nse_api": "https://www.nseindia.com/reports/asm",
}
# NSE's JSON feeds answer only to a session that has loaded a page first.
_NSE_SESSION_PAGE = "https://www.nseindia.com/reports/asm"


class SourceBlocked(RuntimeError):
    """The host refused the request. Stop; do not retry in this run."""


@dataclass(frozen=True)
class Fetched:
    found: bool
    content: bytes


# After this many transport failures in a row the host is treated as not answering.
_MAX_CONSECUTIVE_FAILURES = 10


def _new_client() -> httpx.Client:
    return httpx.Client(
        timeout=INGEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={
            "User-Agent": INGEST_USER_AGENT,
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )


class Fetcher:
    def __init__(self, archive_interval: float = INGEST_MIN_INTERVAL_SECONDS) -> None:
        """``archive_interval`` spaces requests to the archive host, which has tolerated a few
        requests a second. The filing-feed host has not, and always keeps the configured pace."""
        self._client = _new_client()
        self._failures = 0
        self._interval = {"nse_archive": archive_interval, "nse_api": INGEST_MIN_INTERVAL_SECONDS}
        self._lock = threading.Lock()
        self._session_lock = threading.Lock()
        self._next_start: dict[str, float] = {}
        self._nse_session_ready = False
        self._blocked: SourceBlocked | None = None
        self.requests_made = 0

    def close(self) -> None:
        self._client.close()

    def _pace(self, host_group: str) -> None:
        """Reserve the next start slot for this host group, then wait for it."""
        with self._lock:
            if self._blocked is not None:
                raise self._blocked
            start = max(time.monotonic(), self._next_start.get(host_group, 0.0))
            self._next_start[host_group] = start + self._interval[host_group]
            self.requests_made += 1
        wait = start - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def _request(self, host_group: str, url: str) -> httpx.Response:
        self._pace(host_group)
        client = self._client
        try:
            response = client.get(url, headers={"Referer": _REFERER[host_group]})
        except httpx.TransportError:
            self._transport_failure(client)
            raise
        with self._lock:
            self._failures = 0
        if response.status_code in (401, 403, 429):
            blocked = SourceBlocked(
                f"{response.status_code} from {url}. The host is refusing this client; "
                f"wait before running again. Nothing was cached for this request."
            )
            with self._lock:
                self._blocked = blocked
            raise blocked
        return response

    def _transport_failure(self, failed_client: httpx.Client) -> None:
        """A timeout or dropped connection. The pooled connections may be dead (on 2026-10-01
        every request on a long-running client timed out for eight minutes while a fresh
        connection to the same host answered at once), so the next request gets a new client.
        The old one is left for in-flight requests to finish on. Ten failures in a row stop
        the run: the host is not answering and more requests would only wait."""
        with self._lock:
            self._failures += 1
            if self._client is failed_client:
                self._client = _new_client()
                if failed_client.cookies:
                    self._nse_session_ready = False
            if self._failures >= _MAX_CONSECUTIVE_FAILURES and self._blocked is None:
                self._blocked = SourceBlocked(
                    f"{self._failures} requests in a row failed in transit; the host is not answering. "
                    f"Nothing was cached for them. Run again later."
                )
                raise self._blocked

    def get(self, source: Source, url: str) -> Fetched:
        if source.host_group == "nse_api":
            with self._session_lock:
                if not self._nse_session_ready:
                    self._request("nse_api", _NSE_SESSION_PAGE).raise_for_status()
                    self._nse_session_ready = True
        response = self._request(source.host_group, url)
        if response.status_code == 404:
            return Fetched(found=False, content=b"")
        response.raise_for_status()
        logger.info(f"fetched {source.source_id} {len(response.content)} bytes from {url}")
        return Fetched(found=True, content=response.content)
