"""Contexto de request y logging estructurado (JSON)."""
from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
username_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("username", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
            "user": username_ctx.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key in ("module", "action", "duration_ms", "status_code", "path", "method"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(handler.formatter, JsonFormatter) for handler in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    logging.getLogger("uvicorn.access").disabled = True
