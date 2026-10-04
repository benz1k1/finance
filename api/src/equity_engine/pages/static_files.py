"""Vendored static assets, served in-process and cached hard (they change only on deploy)."""

from pathlib import Path

from starlette.staticfiles import StaticFiles

CACHE_CONTROL = "public, max-age=31536000, immutable"
STATIC_DIR = Path(__file__).with_name("static")


class CachedStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = CACHE_CONTROL
        return response
