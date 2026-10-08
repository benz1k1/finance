"""
The engine interface (spec §85). An engine is a pure function of a :class:`Snapshot` — everything
the universe looked like as of one trade date — returning one :class:`Signal` per security that
fired. Engines never touch the database themselves; the snapshot loads each dataset once, lazily,
and every engine in the run shares it.

Stages (§85): EARLY → EMERGING → CONFIRMED → MATURE, and REVERSING when a confirmed signal breaks.
Direction: BULL and BEAR are opportunity and risk signals; GATE removes the security from any
stance (investability, distress, manipulation) and is shown as the reason, never hidden (§118).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

import orjson
from sqlalchemy import Connection

from equity_engine.db import rows
from equity_engine.service import exclusions
from equity_engine.universe import in_universe_as_of

BULL, BEAR, GATE = "BULL", "BEAR", "GATE"
EARLY, EMERGING, CONFIRMED, MATURE, REVERSING = "EARLY", "EMERGING", "CONFIRMED", "MATURE", "REVERSING"
STAGES = (EARLY, EMERGING, CONFIRMED, MATURE, REVERSING)


@dataclass(frozen=True)
class Signal:
    isin: str
    symbol: str
    signal_type: str
    direction: str
    stage: str
    strength: float  # 0–1
    headline: str
    evidence: dict[str, Any]
    invalidation: str
    percentile: float | None = None
    price_at: Decimal | None = None


class Engine(Protocol):
    key: str
    version: str

    def evaluate(self, snap: "Snapshot") -> list[Signal]: ...


def _f(value: Any) -> float | None:
    return None if value is None else float(value)


def percentile_of(values: list[float], value: float) -> float:
    """Empirical percentile (0–100) of ``value`` within ``values``."""
    if not values:
        return 50.0
    below = sum(1 for other in values if other < value)
    return round(100.0 * below / len(values), 2)


# Rolling price features for every security as of one date, computed once per run. Windows are
# in trading rows (rn = 1 is the as-of day); 420 calendar days covers 252 trading rows plus the
# 20-row look-back used for the 200-day average's slope.
_PRICE_FEATURES = (
    """
    WITH raw AS (
        SELECT isin, symbol, trade_date, close AS raw_close, turnover, deliv_pct, market_cap,
               row_number() OVER (PARTITION BY isin ORDER BY trade_date DESC) AS rn
          FROM price_daily
         WHERE trade_date <= :d AND trade_date > CAST(:d AS date) - 420 AND series IN ('EQ', 'SM')
           AND """
    + in_universe_as_of("price_daily.isin")
    + """
    ),
    -- Adjustment (spec §84): a bonus, split or consolidation with an ex-date after the row's day
    -- and on or before the as-of day puts the old close on today's share basis. Computed, never
    -- stored, so the same rows serve any as-of date.
    p AS (
        SELECT r.isin, r.symbol, r.trade_date, r.turnover, r.deliv_pct, r.market_cap, r.rn, r.raw_close,
               r.raw_close * coalesce((
                   SELECT exp(sum(ln(a.adjust_factor)))
                     FROM (SELECT DISTINCT ex_date, adjust_factor FROM corporate_action
                            WHERE symbol = r.symbol AND adjust_factor IS NOT NULL
                              AND ex_date > r.trade_date AND ex_date <= :d) a), 1) AS close
          FROM raw r
    ),
    cur AS (SELECT isin, symbol, close, raw_close, turnover, deliv_pct, market_cap FROM p WHERE rn = 1 AND trade_date = :d),
    agg AS (
        SELECT isin,
               count(*)                                                   AS n,
               avg(close)    FILTER (WHERE rn <= 50)                      AS sma50,
               avg(close)    FILTER (WHERE rn <= 200)                     AS sma200,
               avg(close)    FILTER (WHERE rn BETWEEN 21 AND 220)         AS sma200_prev,
               max(close)    FILTER (WHERE rn <= 252)                     AS hi252,
               min(close)    FILTER (WHERE rn <= 252)                     AS lo252,
               max(close)    FILTER (WHERE rn = 22)                       AS c1m,
               max(close)    FILTER (WHERE rn = 64)                       AS c3m,
               max(close)    FILTER (WHERE rn = 127)                      AS c6m,
               max(close)    FILTER (WHERE rn = 253)                      AS c12m,
               avg(turnover) FILTER (WHERE rn <= 20)                      AS t20,
               avg(turnover) FILTER (WHERE rn <= 120)                     AS t120,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY turnover)  FILTER (WHERE rn <= 60)  AS med_t60,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY deliv_pct) FILTER (WHERE rn <= 20)  AS med_d20,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY deliv_pct) FILTER (WHERE rn <= 60)  AS med_d60,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY deliv_pct) FILTER (WHERE rn <= 120) AS med_d120
          FROM p GROUP BY isin
    )
    SELECT cur.*, agg.n, agg.sma50, agg.sma200, agg.sma200_prev, agg.hi252, agg.lo252,
           agg.c1m, agg.c3m, agg.c6m, agg.c12m, agg.t20, agg.t120, agg.med_t60,
           agg.med_d20, agg.med_d60, agg.med_d120
      FROM cur JOIN agg USING (isin)
"""
)

# Ownership as the market could know it on the as-of date: the newest filing per quarter whose
# broadcast was on or before that date, then the last four quarters per company.
_OWNERSHIP = """
    WITH per_quarter AS (
        SELECT DISTINCT ON (p.symbol, p.period_end)
               p.symbol, p.period_end, p.promoter_pct, p.fii_pct, p.dii_pct, p.total_shareholders
          FROM shareholding_pattern p JOIN shareholding_filing f USING (record_id)
         WHERE f.broadcast_at <= CAST(:d AS date) + 1
         ORDER BY p.symbol, p.period_end, f.broadcast_at DESC
    ),
    ranked AS (
        SELECT q.*, row_number() OVER (PARTITION BY symbol ORDER BY period_end DESC) AS rn
          FROM per_quarter q
    )
    SELECT r.symbol, s.isin, r.period_end, r.promoter_pct, r.fii_pct, r.dii_pct, r.total_shareholders, r.rn
      FROM ranked r JOIN security s ON s.nse_symbol = r.symbol
     WHERE r.rn <= 4
     ORDER BY r.symbol, r.rn
"""

_DEALS = """
    SELECT d.symbol, s.isin,
           sum(d.quantity * d.price) FILTER (WHERE d.side = 'BUY')  AS buy_value,
           sum(d.quantity * d.price) FILTER (WHERE d.side = 'SELL') AS sell_value,
           count(*) AS deals,
           count(DISTINCT d.client_name) FILTER (WHERE d.side = 'BUY') AS buyers
      FROM deal d JOIN security s ON s.nse_symbol = d.symbol
     WHERE d.deal_date <= :d AND d.deal_date > CAST(:d AS date) - 90
     GROUP BY d.symbol, s.isin
"""

# Upper and lower band hits per security over the last 60 sessions, for the manipulation rules.
_CIRCUIT_HITS = """
    SELECT s.isin, count(*) FILTER (WHERE h.side = 'H') AS upper_hits, count(*) FILTER (WHERE h.side = 'L') AS lower_hits
      FROM circuit_hit h JOIN security s ON s.nse_symbol = h.symbol
     WHERE h.trade_date <= :d AND h.trade_date > CAST(:d AS date) - 90
     GROUP BY s.isin
"""

# Corporate actions with an ex-date in the 60 days around the as-of date (past 30, next 30).
_ACTIONS = """
    SELECT DISTINCT ON (s.isin, a.ex_date, a.kind) s.isin, a.symbol, a.ex_date, a.kind, a.purpose, a.amount,
           a.adjust_factor, a.first_seen
      FROM corporate_action a JOIN security s ON s.nse_symbol = a.symbol
     WHERE a.first_seen <= :d AND a.ex_date > CAST(:d AS date) - 30 AND a.ex_date <= CAST(:d AS date) + 30
     ORDER BY s.isin, a.ex_date, a.kind, a.series
"""

# Industry from the newest index constituent file on or before the as-of date, per ISIN.
_INDUSTRY = """
    SELECT DISTINCT ON (c.isin) c.isin, c.industry, c.index_code
      FROM index_constituent_snapshot c
     WHERE c.snapshot_date = (SELECT max(snapshot_date) FROM index_constituent_snapshot WHERE snapshot_date <= :d)
     ORDER BY c.isin, CASE c.index_code WHEN 'nifty500' THEN 0 WHEN 'niftymicrocap250' THEN 1 ELSE 2 END
"""

_LISTINGS = (
    "SELECT isin, nse_symbol AS symbol, listing_date, segment FROM security WHERE listing_date IS NOT NULL"
)

# Canonical quarters known on the as-of date (spec §84): the newest broadcast per (symbol,
# period_end, consolidated) wins over revisions; consolidated is preferred over standalone for a
# quarter when the company files both. Newest quarter first, at most 16 per company.
_FUNDAMENTALS = """
    WITH known AS (
        SELECT DISTINCT ON (q.symbol, q.period_end, q.consolidated) q.*
          FROM fin_quarter q
         WHERE q.broadcast_at <= CAST(:d AS date) + 1 AND q.period_end > CAST(:d AS date) - 1600
         ORDER BY q.symbol, q.period_end, q.consolidated, q.broadcast_at DESC
    ),
    preferred AS (
        SELECT DISTINCT ON (k.symbol, k.period_end) k.*
          FROM known k ORDER BY k.symbol, k.period_end, k.consolidated DESC
    ),
    ranked AS (
        SELECT p.*, row_number() OVER (PARTITION BY p.symbol ORDER BY p.period_end DESC) AS rn FROM preferred p
    )
    SELECT r.*, s.isin FROM ranked r JOIN security s ON s.nse_symbol = r.symbol WHERE r.rn <= 16
     ORDER BY r.symbol, r.period_end DESC
"""

# Close before and three sessions after each company's newest results broadcast (§58). A
# broadcast after the 15:30 close counts from the next session.
_RESULTS_REACTION = """
    WITH newest AS (
        SELECT DISTINCT ON (f.symbol) f.symbol, f.broadcast_at, f.period_end,
               CAST(f.broadcast_at AT TIME ZONE 'Asia/Kolkata' AS date)
                 + CASE WHEN CAST(f.broadcast_at AT TIME ZONE 'Asia/Kolkata' AS time) >= TIME '15:30' THEN 1 ELSE 0 END AS first_session
          FROM fin_filing f
         WHERE f.broadcast_at <= CAST(:d AS date) + 1 AND f.broadcast_at > CAST(:d AS date) - 45
         ORDER BY f.symbol, f.broadcast_at DESC
    )
    SELECT n.symbol, s.isin, n.period_end, n.broadcast_at,
           (SELECT close FROM price_daily p WHERE p.isin = s.isin AND p.trade_date < n.first_session ORDER BY p.trade_date DESC LIMIT 1) AS close_before,
           (SELECT close FROM price_daily p WHERE p.isin = s.isin AND p.trade_date >= n.first_session AND p.trade_date <= :d
             ORDER BY p.trade_date OFFSET 2 LIMIT 1) AS close_after
      FROM newest n JOIN security s ON s.nse_symbol = n.symbol
"""

# Derivatives (§70): the newest F&O day on or before as-of, with the figures five sessions earlier.
_DERIVATIVES = """
    WITH latest AS (SELECT max(trade_date) AS d FROM derivative_oi WHERE trade_date <= :d),
         prior AS (SELECT max(trade_date) AS d FROM derivative_oi WHERE trade_date < (SELECT d FROM latest) - 6)
    SELECT s.isin, n.symbol, n.trade_date, n.futures_oi, n.futures_oi_change, n.basis_pct, n.pcr_oi, n.underlying_close,
           o.futures_oi AS futures_oi_prior, o.underlying_close AS underlying_close_prior
      FROM derivative_oi n
      JOIN security s ON s.nse_symbol = n.symbol
      LEFT JOIN derivative_oi o ON o.symbol = n.symbol AND o.trade_date = (SELECT d FROM prior)
     WHERE n.trade_date = (SELECT d FROM latest)
"""

# Documents of the last 45 days by kind (§30, §35, §37), and board meetings in the next 21 days.
_DOCUMENTS = """
    SELECT s.isin, d.symbol, d.event_kind, d.category, d.summary, d.broadcast_at, d.attachment_url
      FROM document d JOIN security s ON s.nse_symbol = d.symbol
     WHERE d.broadcast_at <= CAST(:d AS date) + 1 AND d.broadcast_at > CAST(:d AS date) - 45
       AND d.event_kind IN ('ORDER_WIN', 'ACQUISITION', 'BUYBACK', 'FUND_RAISE', 'GOVERNANCE', 'REGULATORY', 'RATING', 'PLEDGE')
"""
_MEETINGS = """
    SELECT s.isin, m.symbol, m.meeting_date, m.purpose, m.description
      FROM board_meeting m JOIN security s ON s.nse_symbol = m.symbol
     WHERE m.meeting_date > :d AND m.meeting_date <= CAST(:d AS date) + 21
"""
_RATINGS = """
    SELECT DISTINCT ON (s.isin, r.agency) s.isin, r.symbol, r.agency, r.rating, r.rating_earlier, r.action, r.outlook, r.broadcast_at
      FROM credit_rating r JOIN security s ON s.nse_symbol = r.symbol
     WHERE r.broadcast_at <= CAST(:d AS date) + 1 AND r.broadcast_at > CAST(:d AS date) - 365
     ORDER BY s.isin, r.agency, r.broadcast_at DESC
"""

# LLM readings known on the as-of date, newest first per company (§32).
_EXTRACTIONS = """
    SELECT s.isin, d.symbol, d.document_id, d.event_kind, d.broadcast_at, x.tone, x.guidance, x.kpis, x.risks, x.summary
      FROM document_extraction x JOIN document d USING (document_id) JOIN security s ON s.nse_symbol = d.symbol
     WHERE d.broadcast_at <= CAST(:d AS date) + 1
     ORDER BY s.isin, d.broadcast_at DESC
"""
# Document texts for the diff engine: the two newest of the same kind per company (§71).
_DOCUMENT_TEXTS = """
    SELECT * FROM (
        SELECT s.isin, d.symbol, d.document_id, d.event_kind, d.broadcast_at, t.text,
               row_number() OVER (PARTITION BY s.isin, d.event_kind ORDER BY d.broadcast_at DESC) AS rn
          FROM document_text t JOIN document d USING (document_id) JOIN security s ON s.nse_symbol = d.symbol
         WHERE d.broadcast_at <= CAST(:d AS date) + 1 AND d.event_kind IN ('ANNUAL_REPORT', 'RESULTS', 'INVESTOR_MEET')
    ) r WHERE r.rn <= 2 ORDER BY r.isin, r.event_kind, r.broadcast_at DESC
"""

_ASM = """
    SELECT v.isin, v.list_code, v.stage FROM surveillance_snapshot v
     WHERE v.list_code IN ('ASM_LT', 'ASM_ST')
       AND v.snapshot_date = (SELECT max(snapshot_date) FROM surveillance_snapshot
                               WHERE list_code = v.list_code AND snapshot_date <= :d)
"""


@dataclass
class Snapshot:
    """The universe as of one trade date. Datasets load on first use and are shared by every engine."""

    connection: Connection
    as_of: date
    _prices: list[dict[str, Any]] | None = field(default=None, repr=False)
    _ownership: dict[str, list[dict[str, Any]]] | None = field(default=None, repr=False)
    _deals: list[dict[str, Any]] | None = field(default=None, repr=False)
    _excluded: dict[str, list[str]] | None = field(default=None, repr=False)
    _asm: dict[str, str] | None = field(default=None, repr=False)
    _other_close: dict[str, Any] | None = field(default=None, repr=False)
    _symbols: dict[str, str] | None = field(default=None, repr=False)
    _hits: dict[str, dict[str, int]] | None = field(default=None, repr=False)
    _actions: list[dict[str, Any]] | None = field(default=None, repr=False)
    _industry: dict[str, dict[str, Any]] | None = field(default=None, repr=False)
    _listings: list[dict[str, Any]] | None = field(default=None, repr=False)
    _fundamentals: dict[str, list[dict[str, Any]]] | None = field(default=None, repr=False)
    _reactions: list[dict[str, Any]] | None = field(default=None, repr=False)
    _derivatives: list[dict[str, Any]] | None = field(default=None, repr=False)
    _documents: list[dict[str, Any]] | None = field(default=None, repr=False)
    _meetings: list[dict[str, Any]] | None = field(default=None, repr=False)
    _ratings: list[dict[str, Any]] | None = field(default=None, repr=False)
    _extractions: dict[str, list[dict[str, Any]]] | None = field(default=None, repr=False)
    _texts: dict[str, list[dict[str, Any]]] | None = field(default=None, repr=False)
    _universe: set[str] | None = field(default=None, repr=False)
    _global: dict[str, Any] | None = field(default=None, repr=False)
    _pe_reference: dict[str, dict[str, list[float]]] | None = field(default=None, repr=False)

    @property
    def prices(self) -> list[dict[str, Any]]:
        if self._prices is None:
            found = rows(self.connection, _PRICE_FEATURES, {"d": self.as_of})
            for item in found:
                for key, value in item.items():
                    if isinstance(value, Decimal):
                        item[key] = float(value)
                    elif key in ("close", "market_cap", "turnover") and value is not None:
                        item[key] = float(value)
            self._prices = found
        return self._prices

    @property
    def price_by_isin(self) -> dict[str, dict[str, Any]]:
        return {item["isin"]: item for item in self.prices}

    @property
    def ownership(self) -> dict[str, list[dict[str, Any]]]:
        """Per ISIN, newest quarter first (at most four)."""
        if self._ownership is None:
            grouped: dict[str, list[dict[str, Any]]] = {}
            for item in rows(self.connection, _OWNERSHIP, {"d": self.as_of}):
                for key in ("promoter_pct", "fii_pct", "dii_pct"):
                    item[key] = _f(item[key])
                grouped.setdefault(item["isin"], []).append(item)
            self._ownership = grouped
        return self._ownership

    @property
    def deals(self) -> list[dict[str, Any]]:
        if self._deals is None:
            found = rows(self.connection, _DEALS, {"d": self.as_of})
            for item in found:
                item["buy_value"] = float(item["buy_value"] or 0)
                item["sell_value"] = float(item["sell_value"] or 0)
            self._deals = found
        return self._deals

    @property
    def excluded(self) -> dict[str, list[str]]:
        if self._excluded is None:
            self._excluded = {
                item["isin"]: list(item["labels"])
                for item in exclusions.excluded(self.connection, self.as_of)
            }
        return self._excluded

    @property
    def asm(self) -> dict[str, str]:
        if self._asm is None:
            self._asm = {
                item["isin"]: f"{item['list_code']} {item['stage']}"
                for item in rows(self.connection, _ASM, {"d": self.as_of})
            }
        return self._asm

    @property
    def universe(self) -> set[str]:
        """ISINs in the universe (spec §119): every signal outside it is dropped by the runner."""
        if self._universe is None:
            self._universe = {
                item["isin"]
                for item in rows(
                    self.connection,
                    "SELECT isin FROM security s WHERE " + in_universe_as_of("s.isin"),
                    {"d": self.as_of},
                )
            }
        return self._universe

    @property
    def circuit_hits(self) -> dict[str, dict[str, int]]:
        if self._hits is None:
            self._hits = {
                item["isin"]: item for item in rows(self.connection, _CIRCUIT_HITS, {"d": self.as_of})
            }
        return self._hits

    @property
    def actions(self) -> list[dict[str, Any]]:
        """Corporate actions known on the as-of date with ex-dates within 30 days either side."""
        if self._actions is None:
            found = rows(self.connection, _ACTIONS, {"d": self.as_of})
            for item in found:
                for key in ("amount", "adjust_factor"):
                    item[key] = _f(item[key])
            self._actions = found
        return self._actions

    @property
    def industry(self) -> dict[str, dict[str, Any]]:
        if self._industry is None:
            self._industry = {
                item["isin"]: item for item in rows(self.connection, _INDUSTRY, {"d": self.as_of})
            }
        return self._industry

    @property
    def listings(self) -> list[dict[str, Any]]:
        if self._listings is None:
            self._listings = rows(self.connection, _LISTINGS)
        return self._listings

    @property
    def fundamentals(self) -> dict[str, list[dict[str, Any]]]:
        """Per ISIN, canonical quarters newest first (spec §5), floats, as known on the as-of date."""
        if self._fundamentals is None:
            grouped: dict[str, list[dict[str, Any]]] = {}
            for item in rows(self.connection, _FUNDAMENTALS, {"d": self.as_of}):
                for key, value in item.items():
                    if isinstance(value, Decimal):
                        item[key] = float(value)
                grouped.setdefault(item["isin"], []).append(item)
            self._fundamentals = grouped
        return self._fundamentals

    @property
    def results_reactions(self) -> list[dict[str, Any]]:
        if self._reactions is None:
            found = rows(self.connection, _RESULTS_REACTION, {"d": self.as_of})
            for item in found:
                item["close_before"] = _f(item["close_before"])
                item["close_after"] = _f(item["close_after"])
            self._reactions = found
        return self._reactions

    @property
    def derivatives(self) -> list[dict[str, Any]]:
        if self._derivatives is None:
            found = rows(self.connection, _DERIVATIVES, {"d": self.as_of})
            for item in found:
                for key in ("basis_pct", "pcr_oi", "underlying_close", "underlying_close_prior"):
                    item[key] = _f(item[key])
            self._derivatives = found
        return self._derivatives

    @property
    def documents(self) -> list[dict[str, Any]]:
        if self._documents is None:
            self._documents = rows(self.connection, _DOCUMENTS, {"d": self.as_of})
        return self._documents

    @property
    def meetings(self) -> list[dict[str, Any]]:
        if self._meetings is None:
            self._meetings = rows(self.connection, _MEETINGS, {"d": self.as_of})
        return self._meetings

    @property
    def ratings(self) -> list[dict[str, Any]]:
        if self._ratings is None:
            self._ratings = rows(self.connection, _RATINGS, {"d": self.as_of})
        return self._ratings

    @property
    def extractions(self) -> dict[str, list[dict[str, Any]]]:
        if self._extractions is None:
            grouped: dict[str, list[dict[str, Any]]] = {}
            for item in rows(self.connection, _EXTRACTIONS, {"d": self.as_of}):
                for key in ("guidance", "kpis", "risks"):
                    if isinstance(item[key], str):
                        item[key] = orjson.loads(item[key])
                grouped.setdefault(item["isin"], []).append(item)
            self._extractions = grouped
        return self._extractions

    def extraction_for(self, document_id: str) -> dict[str, Any] | None:
        for readings in self.extractions.values():
            for reading in readings:
                if reading["document_id"] == document_id:
                    return reading
        return None

    @property
    def document_texts(self) -> dict[str, list[dict[str, Any]]]:
        """Per ISIN, the newest two texts of the newest kind that has two (newest first)."""
        if self._texts is None:
            grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for item in rows(self.connection, _DOCUMENT_TEXTS, {"d": self.as_of}):
                grouped.setdefault((item["isin"], item["event_kind"]), []).append(item)
            by_isin: dict[str, list[dict[str, Any]]] = {}
            for (isin, _kind), texts in sorted(
                grouped.items(), key=lambda kv: kv[1][0]["broadcast_at"], reverse=True
            ):
                if len(texts) == 2 and isin not in by_isin:
                    by_isin[isin] = texts
            self._texts = by_isin
        return self._texts

    @property
    def global_context(self) -> dict[str, Any]:
        """The world on the as-of date (spec §120): per-index returns, median 3-month return, stress flag."""
        if self._global is None:
            from equity_engine.service import (
                global_markets,  # noqa: PLC0415 — circular: service imports engines
            )

            self._global = global_markets.context(self.connection, self.as_of)
        return self._global

    @property
    def market_median_3m_pct(self) -> float | None:
        """The median 3-month return of the priced universe, from the same price features."""
        returns = [(p["close"] / p["c3m"] - 1) * 100 for p in self.prices if p.get("c3m")]
        if not returns:
            return None
        returns.sort()
        middle = len(returns) // 2
        return returns[middle] if len(returns) % 2 else (returns[middle - 1] + returns[middle]) / 2

    @property
    def pe_reference(self) -> dict[str, dict[str, list[float]]]:
        """Per ISIN, the company's P/E on past stress dates, expansion dates and all sampled dates
        (spec §121), computed point in time: the close on the date × shares outstanding known then,
        over the TTM profit broadcast by then. Dates come from the regime rows of earlier runs,
        one per calendar month."""
        if self._pe_reference is None:
            self._pe_reference = _pe_reference(self.connection, self.as_of, self.fundamentals)
        return self._pe_reference

    def close(self, isin: str) -> Decimal | None:
        """The close actually printed on the as-of day (unadjusted), for the ledger's price_at."""
        found = self.price_by_isin.get(isin)
        if found is not None:
            return Decimal(str(found["raw_close"]))
        other = self.any_series_close.get(isin)
        return None if other is None else Decimal(str(other))

    @property
    def any_series_close(self) -> dict[str, Any]:
        """Close on the as-of date for securities outside EQ/SM (trade-for-trade series), so a gate
        on one of them still carries a price."""
        if self._other_close is None:
            self._other_close = {
                item["isin"]: item["close"]
                for item in rows(
                    self.connection,
                    "SELECT isin, close FROM price_daily WHERE trade_date = :d AND series NOT IN ('EQ', 'SM')",
                    {"d": self.as_of},
                )
            }
        return self._other_close

    def symbol_of(self, isin: str) -> str:
        if self._symbols is None:
            self._symbols = {
                item["isin"]: item["nse_symbol"]
                for item in rows(self.connection, "SELECT isin, nse_symbol FROM security")
            }
        return self._symbols.get(isin, isin)


# ------------------------------------------------------------------ P/E history (spec §121)

_REGIME_DATES = """
    SELECT DISTINCT ON (date_trunc('month', m.as_of)) m.as_of, m.median_return_3m_pct
      FROM market_regime m JOIN engine_run r USING (run_id)
     WHERE r.finished_at IS NOT NULL AND m.as_of < :d AND m.median_return_3m_pct IS NOT NULL
     ORDER BY date_trunc('month', m.as_of), m.as_of DESC
"""
_CLOSES_AT = """
    SELECT p.isin, p.trade_date, p.close FROM price_daily p
     WHERE p.trade_date = ANY(:dates) AND p.series IN ('EQ', 'SM')
"""
_SHARES = """
    SELECT s.isin, p.period_end, f.broadcast_at, p.total_shares
      FROM shareholding_pattern p JOIN shareholding_filing f USING (record_id) JOIN security s ON s.nse_symbol = p.symbol
     WHERE p.total_shares IS NOT NULL AND f.broadcast_at <= CAST(:d AS date) + 1
     ORDER BY s.isin, f.broadcast_at
"""
STRESS_MEDIAN_3M = -10.0
EXPANSION_MEDIAN_3M = 10.0


def _pe_reference(
    connection: Connection, as_of: date, fundamentals: dict[str, list[dict[str, Any]]]
) -> dict[str, dict[str, list[float]]]:
    dates = rows(connection, _REGIME_DATES, {"d": as_of})
    if not dates:
        return {}
    kind_of = {
        r["as_of"]: (
            "stress"
            if float(r["median_return_3m_pct"]) <= STRESS_MEDIAN_3M
            else "expansion"
            if float(r["median_return_3m_pct"]) >= EXPANSION_MEDIAN_3M
            else "normal"
        )
        for r in dates
    }
    closes: dict[str, dict[date, float]] = {}
    for r in rows(connection, _CLOSES_AT, {"dates": list(kind_of)}):
        closes.setdefault(r["isin"], {})[r["trade_date"]] = float(r["close"])
    shares: dict[str, list[tuple[Any, float]]] = {}
    for r in rows(connection, _SHARES, {"d": as_of}):
        shares.setdefault(r["isin"], []).append((r["broadcast_at"], float(r["total_shares"])))
    out: dict[str, dict[str, list[float]]] = {}
    for isin, history in fundamentals.items():
        own_shares = shares.get(isin)
        own_closes = closes.get(isin)
        if not own_shares or not own_closes:
            continue
        quarters = sorted(history, key=lambda q: q["period_end"], reverse=True)
        ref = {"stress": [], "expansion": [], "all": []}
        for day, kind in kind_of.items():
            close = own_closes.get(day)
            if close is None:
                continue
            known = [q for q in quarters if q["broadcast_at"].date() <= day]
            if len(known) < 4 or any(q.get("q_pat") is None for q in known[:4]):
                continue
            ttm = float(sum(q["q_pat"] for q in known[:4]))
            if ttm <= 0:
                continue
            # shares outstanding as last disclosed on or before the date; else the earliest disclosure
            before = [n for at, n in own_shares if at.date() <= day]
            count = before[-1] if before else own_shares[0][1]
            pe = close * count / ttm
            ref["all"].append(pe)
            if kind != "normal":
                ref[kind].append(pe)
        if ref["all"]:
            out[isin] = ref
    return out
