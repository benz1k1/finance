"""``create_app()`` and the module-level ``app``. One process: FastAPI serving the htmx pages plus
the ``/api`` JSON endpoints, run under Granian. Because ``lifespan=`` is set, ``@app.on_event``
does not run; startup work is in the lifespan."""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from equity_engine.config import DATABASE_SCHEMA, LOG_DIR, LOG_LEVEL
from equity_engine.db import scalar, transaction
from equity_engine.pages.static_files import STATIC_DIR, CachedStaticFiles
from equity_engine.pages.templating import templates
from equity_engine.pages.urls import register_routes


def _configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=LOG_LEVEL)
    logger.add(LOG_DIR / "equity_engine.log", level=LOG_LEVEL, rotation="10 MB", retention=5)
    logger.add(LOG_DIR / "equity_engine_errors.log", level="ERROR", rotation="10 MB", retention=5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    # Fail at startup, not on the first request, when the schema has not been created.
    with transaction() as connection:
        sources = scalar(connection, "SELECT count(*) FROM source_registry")
    logger.info(f"equity_engine ready: schema {DATABASE_SCHEMA}, {sources} sources registered")
    yield


def _wants_html(request: Request) -> bool:
    return not request.url.path.startswith("/api/") and "text/html" in request.headers.get("accept", "")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Equity Engine",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.mount("/static", CachedStaticFiles(directory=str(STATIC_DIR)), name="static")
    register_routes(app)

    def _error(request: Request, message: str, status: int):
        if _wants_html(request):
            return templates.TemplateResponse(request, "error.html", {"message": message}, status_code=status)
        return JSONResponse({"success": False, "error": message}, status_code=status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return _error(request, str(exc.detail), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse({"success": False, "error": exc.errors()}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception(f"unhandled error on {request.method} {request.url.path}: {exc}")
        return _error(request, f"{type(exc).__name__}: {exc}", 500)

    return app


app = create_app()
