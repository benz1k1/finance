"""The company timeline (spec §31): everything the exchange knows about one company, in one
chronology — announcements, results filings, corporate actions, board meetings, rating actions,
bulk/block deals and the engine's own stance changes. Each entry links to its source."""

from typing import Any

from sqlalchemy import Connection

from equity_engine.db import rows

_TIMELINE = """
    SELECT * FROM (
        SELECT d.broadcast_at AS at, 'DOCUMENT' AS kind, d.event_kind AS subkind, d.category AS title, left(d.summary, 300) AS detail,
               d.attachment_url AS link
          FROM document d WHERE d.symbol = :symbol
        UNION ALL
        SELECT f.broadcast_at, 'RESULTS', CASE WHEN f.consolidated THEN 'CONSOLIDATED' ELSE 'STANDALONE' END,
               'Results for the quarter ended ' || to_char(f.period_end, 'DD-Mon-YYYY'),
               CASE WHEN q.q_revenue IS NOT NULL THEN 'Revenue ₹' || to_char(q.q_revenue / 1e7, 'FM999,999,990') || ' cr, PAT ₹' || to_char(q.q_pat / 1e7, 'FM999,999,990') || ' cr' ELSE 'XBRL not loaded yet' END,
               f.xbrl_url
          FROM fin_filing f LEFT JOIN fin_quarter q USING (filing_id) WHERE f.symbol = :symbol
        UNION ALL
        SELECT CAST(a.ex_date AS timestamptz), 'ACTION', a.kind, a.purpose,
               'Ex-date ' || to_char(a.ex_date, 'DD-Mon-YYYY') || coalesce('; record date ' || to_char(a.record_date, 'DD-Mon-YYYY'), '') || '; announced ' || to_char(a.first_seen, 'DD-Mon-YYYY'),
               NULL
          FROM (SELECT DISTINCT ON (ex_date, purpose) * FROM corporate_action WHERE symbol = :symbol ORDER BY ex_date, purpose, series) a
        UNION ALL
        SELECT CAST(m.meeting_date AS timestamptz), 'MEETING', upper(replace(m.purpose, ' ', '_')), 'Board meeting: ' || m.purpose, left(m.description, 300), NULL
          FROM board_meeting m WHERE m.symbol = :symbol
        UNION ALL
        SELECT r.broadcast_at, 'RATING', upper(r.action), r.agency || ': ' || r.rating || coalesce(' (' || r.outlook || ')', ''),
               coalesce('Earlier ' || r.rating_earlier, ''), NULL
          FROM credit_rating r WHERE r.symbol = :symbol
        UNION ALL
        SELECT CAST(x.deal_date AS timestamptz), 'DEAL', x.kind || '_' || x.side, x.client_name || ' ' || lower(x.side) || 's ' || to_char(x.quantity, 'FM999,999,999,990') || ' at ₹' || to_char(x.price, 'FM999,990.00'),
               '₹' || to_char(x.quantity * x.price / 1e7, 'FM999,990.0') || ' cr', NULL
          FROM deal x WHERE x.symbol = :symbol AND x.quantity * x.price >= 10000000
        UNION ALL
        SELECT CAST(st.as_of AS timestamptz), 'STANCE', st.stance, 'Stance ' || st.stance || ' (' || st.conviction || ')',
               coalesce(st.gate, 'bull ' || st.bull_count || ' / bear ' || st.bear_count), NULL
          FROM stance st JOIN engine_run r USING (run_id)
         WHERE st.symbol = :symbol AND r.kind = 'LIVE' AND r.finished_at IS NOT NULL
           AND r.run_id IN (SELECT DISTINCT ON (as_of) run_id FROM engine_run WHERE kind = 'LIVE' AND finished_at IS NOT NULL ORDER BY as_of, started_at DESC)
    ) t
    WHERE (:kinds = '' OR t.kind = ANY(string_to_array(:kinds, ',')))
    ORDER BY t.at DESC
    LIMIT :limit
"""

KINDS = ("DOCUMENT", "RESULTS", "ACTION", "MEETING", "RATING", "DEAL", "STANCE")


def for_symbol(connection: Connection, symbol: str, kinds: list[str], limit: int) -> list[dict[str, Any]]:
    return rows(connection, _TIMELINE, {"symbol": symbol, "kinds": ",".join(kinds), "limit": limit})
