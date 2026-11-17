"""Structured JSON logging (structlog) with correlation ids and credential redaction."""

import logging
import re
import sys
import time
import uuid
from collections.abc import Iterator, MutableMapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SERVICE_NAME = "jarvis"
CORRELATION_HEADER = "X-Correlation-ID"
REDACTED = "***REDACTED***"

_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "private_key",
    "cookie",
    "dsn",
)
# scheme://user:password@host  ->  scheme://user:***@host
_URL_CREDENTIALS = re.compile(r"(?P<head>[A-Za-z][A-Za-z0-9+.\-]*://[^/\s:@]*:)(?P<secret>[^@\s/]*)(?P<tail>@)")

correlation_id_var: ContextVar[str | None] = ContextVar("jarvis_correlation_id", default=None)


# --------------------------------------------------------------------------- #
# Correlation id helpers
# --------------------------------------------------------------------------- #
def new_correlation_id() -> str:
    return uuid.uuid4().hex


def get_correlation_id() -> str | None:
    return correlation_id_var.get()


def set_correlation_id(value: str | None) -> Token[str | None]:
    return correlation_id_var.set(value)


@contextmanager
def correlation_context(value: str | None = None) -> Iterator[str]:
    """Bind a correlation id for the duration of the block (used by worker jobs)."""
    cid = value or new_correlation_id()
    token = correlation_id_var.set(cid)
    try:
        yield cid
    finally:
        correlation_id_var.reset(token)


def _accept_or_generate(candidate: str | None) -> str:
    """Honour a client-supplied id only if it is short and harmless (no log injection)."""
    if candidate and _CORRELATION_ID_PATTERN.fullmatch(candidate):
        return candidate
    return new_correlation_id()


# --------------------------------------------------------------------------- #
# Processors
# --------------------------------------------------------------------------- #
def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _URL_CREDENTIALS.sub(rf"\g<head>{REDACTED}\g<tail>", value)
    if isinstance(value, dict):
        return _redact_mapping(value)
    if isinstance(value, list | tuple):
        return [_redact_value(item) for item in value]
    return value


def _redact_mapping(data: MutableMapping[Any, Any]) -> dict[Any, Any]:
    cleaned: dict[Any, Any] = {}
    for key, value in data.items():
        key_text = str(key).lower()
        if any(part in key_text for part in _SENSITIVE_KEY_PARTS):
            cleaned[key] = REDACTED
        else:
            cleaned[key] = _redact_value(value)
    return cleaned


def redact_sensitive(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Mask sensitive keys and ``user:password@`` URL credentials anywhere in the event."""
    return _redact_mapping(event_dict)


def add_correlation_id(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    cid = correlation_id_var.get()
    if cid and "correlation_id" not in event_dict:
        event_dict["correlation_id"] = cid
    return event_dict


def _service_fields(environment: str) -> structlog.typing.Processor:
    def processor(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        event_dict.setdefault("service", SERVICE_NAME)
        event_dict.setdefault("env", environment)
        return event_dict

    return processor


def configure_logging(level: str = "INFO", *, environment: str = "development") -> None:
    """Route structlog *and* stdlib logging (uvicorn, arq, alembic, sqlalchemy) to JSON on stdout."""
    shared: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        add_correlation_id,
        _service_fields(environment),
    ]

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.dict_tracebacks,
            redact_sensitive,  # last step before rendering: scrubs exceptions and foreign records too
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())

    for name in ("uvicorn", "uvicorn.error"):
        framework_logger = logging.getLogger(name)
        framework_logger.handlers.clear()
        framework_logger.propagate = True
    # Request completion is logged (with correlation id) by CorrelationIdMiddleware instead.
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False
    access_logger.disabled = True


# --------------------------------------------------------------------------- #
# ASGI middleware
# --------------------------------------------------------------------------- #
class CorrelationIdMiddleware:
    """Assign/propagate a correlation id per request and log request completion."""

    def __init__(self, app: ASGIApp, header_name: str = CORRELATION_HEADER) -> None:
        self.app = app
        self.header_name = header_name
        self._log = structlog.get_logger("jarvis.http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        cid = _accept_or_generate(Headers(scope=scope).get(self.header_name))
        token = correlation_id_var.set(cid)
        scope.setdefault("state", {})["correlation_id"] = cid
        status_code = 500
        started = time.perf_counter()

        async def send_with_header(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[self.header_name] = cid
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            self._log.info(
                "http.request",
                method=scope.get("method"),
                path=scope.get("path"),
                status_code=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            correlation_id_var.reset(token)
