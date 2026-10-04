"""
Phase 3 document pipeline (spec §83, §32, §33, §56, §71, §117 brands).

Two steps, both resumable and both idempotent:

1. ``fetch_texts`` — download the PDF behind announcements of the chosen kinds (through the
   paced Fetcher, cached for good like every file) and store the text pypdf reads from them.
2. ``extract`` — when ``llm.enabled`` is true, read each text with Claude using structured
   outputs and store the reading: tone, guidance, KPIs, risks, brands, a summary. The reading is
   evidence for the engines; numbers shown on a page always come from the database (§52).

Document diff (§71) needs only step 1: consecutive annual reports of a company are compared as
text. Everything else reads the extraction.
"""

from collections import Counter
from typing import Any

import orjson
from loguru import logger
from pydantic import BaseModel, Field
from pypdf import PdfReader
from sqlalchemy import Connection

from equity_engine.config import LLM_API_KEY, LLM_ENABLED, LLM_MODEL
from equity_engine.db import execute, execute_many, rows, transaction
from equity_engine.service.ingest import _download_documents
from equity_engine.sources import bronze
from equity_engine.sources.http import Fetcher
from equity_engine.sources.registry import BY_ID
from equity_engine.universe import in_universe

PROMPT_VERSION = "1"
MAX_TEXT_CHARS = 180_000  # about 45k tokens of PDF text per document
FETCHABLE_KINDS = ("INVESTOR_MEET", "PRESS_RELEASE", "RESULTS", "ACQUISITION", "ORDER_WIN", "ANNUAL_REPORT")


def pdf_text(content: bytes) -> tuple[int, str]:
    reader = PdfReader(__import__("io").BytesIO(content))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return len(pages), "\f".join(pages)


def fetch_texts(
    fetcher: Fetcher | None, kinds: list[str], limit: int, workers: int = 1, symbol: str | None = None
) -> Counter[str]:
    """Announcements of ``kinds`` with an attachment and no text yet, newest first."""
    source = BY_ID["nse_announcement_pdf"]
    with transaction() as connection:
        pending = rows(
            connection,
            """
            SELECT d.document_id, d.symbol, d.broadcast_at, d.attachment_url FROM document d
             WHERE d.event_kind = ANY(:kinds) AND d.attachment_url IS NOT NULL AND d.attachment_url LIKE '%.pdf'
               AND EXISTS (SELECT 1 FROM security s WHERE s.nse_symbol = d.symbol AND """
            + in_universe("s.isin")
            + """)
               AND (coalesce(d.attachment_kb, 0) BETWEEN 1 AND 15000)
               AND (CAST(:symbol AS text) IS NULL OR d.symbol = CAST(:symbol AS text))
               AND NOT EXISTS (SELECT 1 FROM document_text t WHERE t.document_id = d.document_id)
             ORDER BY d.broadcast_at DESC LIMIT :limit
            """,
            {"kinds": kinds, "limit": limit, "symbol": symbol},
        )
    jobs = [
        (bronze.document_path(source, item["broadcast_at"].year, item["attachment_url"]), item)
        for item in pending
    ]
    tally: Counter[str] = Counter()
    if fetcher is not None:
        tally += _download_documents(
            source, [(path, item["attachment_url"]) for path, item in jobs], fetcher, workers
        )
    for path, item in jobs:
        if not path.is_file():
            tally["NOT_CACHED"] += 1
            continue
        try:
            pages, text = pdf_text(path.read_bytes())
        except Exception as broken:  # pypdf raises many exception types for damaged files
            logger.warning(f"announcement PDF {path.name} ({item['symbol']}) unreadable: {broken!r}")
            tally["UNREADABLE"] += 1
            continue
        if len(text.strip()) < 200:
            tally["NO_TEXT"] += 1  # scanned image, no text layer
            continue
        with transaction() as connection:
            raw = bronze.register(connection, source, item["broadcast_at"].date(), path)
            execute(
                connection,
                """
                INSERT INTO document_text (document_id, pages, characters, text, raw_id)
                VALUES (:document_id, :pages, :characters, :text, :raw_id)
                ON CONFLICT (document_id) DO UPDATE SET pages = EXCLUDED.pages, characters = EXCLUDED.characters,
                    text = EXCLUDED.text, raw_id = EXCLUDED.raw_id, extracted_at = now()
                """,
                {
                    "document_id": item["document_id"],
                    "pages": pages,
                    "characters": len(text),
                    "text": text[: MAX_TEXT_CHARS * 2],
                    "raw_id": raw["raw_id"],
                },
            )
        tally["TEXT"] += 1
    return tally


# ------------------------------------------------------------------ LLM reading


class Guidance(BaseModel):
    metric: str = Field(
        description="What management guided on: revenue, margin, capex, volumes, order inflow …"
    )
    direction: str = Field(description="UP, DOWN, FLAT or WITHDRAWN")
    horizon: str = Field(description="The period the guidance refers to, as stated, e.g. FY27 or H2")
    quote: str = Field(description="The sentence it comes from, verbatim")


class Kpi(BaseModel):
    name: str
    value: float
    unit: str = Field(description="%, INR crore, units, MW, tonnes … as stated")
    period: str
    quote: str


class Risk(BaseModel):
    risk: str
    new_or_changed: bool = Field(description="True when the document presents it as new or worsening")
    quote: str


class Brand(BaseModel):
    brand: str
    category: str = Field(description="Product or service category the brand belongs to")


class Reading(BaseModel):
    tone: str = Field(
        description="POSITIVE, NEUTRAL, NEGATIVE or MIXED — management's tone on the business outlook"
    )
    guidance: list[Guidance]
    kpis: list[Kpi]
    risks: list[Risk]
    brands: list[Brand]
    summary: str = Field(description="Three sentences at most, only facts stated in the document")


_SYSTEM = (
    "You read Indian listed-company disclosures (investor presentations, press releases, results "
    "notes, annual reports). Extract only what the document states; never estimate or infer numbers. "
    "Every guidance, KPI and risk item carries the verbatim sentence it comes from. Brands are "
    "consumer-facing product or service names the company owns, not the company's own name."
)


def extract(limit: int, kinds: list[str] | None = None) -> Counter[str]:
    """Read documents that have text but no extraction, newest first. Requires ``llm.enabled``."""
    if not LLM_ENABLED:
        raise ValueError("LLM extraction is off: set llm.enabled, llm.api_key and llm.model in the env YAML")
    import anthropic  # noqa: PLC0415 — optional feature; the dependency is only needed when enabled

    client = anthropic.Anthropic(api_key=LLM_API_KEY)
    with transaction() as connection:
        pending = rows(
            connection,
            """
            SELECT d.document_id, d.symbol, d.event_kind, d.category, t.text FROM document d JOIN document_text t USING (document_id)
             WHERE (CAST(:kinds AS text[]) IS NULL OR d.event_kind = ANY(CAST(:kinds AS text[])))
               AND NOT EXISTS (SELECT 1 FROM document_extraction x WHERE x.document_id = d.document_id)
             ORDER BY d.broadcast_at DESC LIMIT :limit
            """,
            {"kinds": kinds, "limit": limit},
        )
    tally: Counter[str] = Counter()
    for item in pending:
        text = item["text"][:MAX_TEXT_CHARS]
        try:
            with client.messages.stream(
                model=LLM_MODEL,
                max_tokens=16000,
                system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[
                    {
                        "role": "user",
                        "content": f"Company: {item['symbol']}. Filing category: {item['category']} ({item['event_kind']}).\n\n{text}",
                    }
                ],
                output_config={"format": {"type": "json_schema", "schema": Reading.model_json_schema()}},
            ) as stream:
                message = stream.get_final_message()
        except anthropic.RateLimitError as limited:
            logger.warning(f"rate limited reading {item['document_id']}: {limited}")
            tally["RATE_LIMITED"] += 1
            break
        except anthropic.APIStatusError as failed:
            logger.warning(f"API error reading {item['document_id']}: {failed.status_code} {failed.message}")
            tally["API_ERROR"] += 1
            continue
        if message.stop_reason == "refusal":
            tally["REFUSED"] += 1
            continue
        body = "".join(block.text for block in message.content if block.type == "text")
        reading = Reading.model_validate_json(body)
        with transaction() as connection:
            _store(connection, item, reading, message.model)
        tally["EXTRACTED"] += 1
    return tally


def _store(connection: Connection, item: dict[str, Any], reading: Reading, model: str) -> None:
    execute(
        connection,
        """
        INSERT INTO document_extraction (document_id, model, prompt_version, tone, guidance, kpis, risks, brands, summary)
        VALUES (:document_id, :model, :prompt_version, :tone, CAST(:guidance AS jsonb), CAST(:kpis AS jsonb),
                CAST(:risks AS jsonb), CAST(:brands AS jsonb), :summary)
        ON CONFLICT (document_id) DO UPDATE SET model = EXCLUDED.model, prompt_version = EXCLUDED.prompt_version,
            tone = EXCLUDED.tone, guidance = EXCLUDED.guidance, kpis = EXCLUDED.kpis, risks = EXCLUDED.risks,
            brands = EXCLUDED.brands, summary = EXCLUDED.summary, extracted_at = now()
        """,
        {
            "document_id": item["document_id"],
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "tone": reading.tone if reading.tone in ("POSITIVE", "NEUTRAL", "NEGATIVE", "MIXED") else "MIXED",
            "guidance": orjson.dumps([g.model_dump() for g in reading.guidance]).decode(),
            "kpis": orjson.dumps([k.model_dump() for k in reading.kpis]).decode(),
            "risks": orjson.dumps([r.model_dump() for r in reading.risks]).decode(),
            "brands": orjson.dumps([b.model_dump() for b in reading.brands]).decode(),
            "summary": reading.summary[:2000],
        },
    )
    execute_many(
        connection,
        """
        INSERT INTO company_brand (symbol, brand, category, document_id) VALUES (:symbol, :brand, :category, :document_id)
        ON CONFLICT (symbol, brand) DO UPDATE SET category = EXCLUDED.category, document_id = EXCLUDED.document_id
        """,
        [
            {
                "symbol": item["symbol"],
                "brand": b.brand.strip()[:120],
                "category": b.category.strip()[:120],
                "document_id": item["document_id"],
            }
            for b in reading.brands
            if b.brand.strip()
        ],
    )
