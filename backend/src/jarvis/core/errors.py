"""Exception hierarchy, retry helper and centralized FastAPI error handlers.

Design rules:
* Every error that reaches a client is rendered through one envelope:
  ``{"error": {"code", "message", "correlation_id", "details"?}}``.
* Clients only ever see the *public* message. Internal messages go to the logs.
* Anything unexpected fails closed with a generic 500 - never a stack trace.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger(__name__)

CORRELATION_HEADER = "X-Correlation-ID"

# Indirection so tests can replace sleeping without touching asyncio globally.
_sleep = asyncio.sleep


# --------------------------------------------------------------------------- #
# Exception hierarchy
# --------------------------------------------------------------------------- #
class JarvisError(Exception):
    """Base class for all expected, application-level errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    public_message: str = "Internal server error."

    def __init__(self, message: str | None = None, *, details: Mapping[str, Any] | None = None) -> None:
        self.message = message or self.public_message
        self.details: dict[str, Any] = dict(details) if details else {}
        super().__init__(self.message)


class ConfigurationError(JarvisError):
    code = "configuration_error"
    public_message = "Service is misconfigured."


class TradingDisabledError(JarvisError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "trading_disabled"
    public_message = "Live trading is disabled. Only paper trading is available."


class NotFoundError(JarvisError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    public_message = "Resource not found."


class DependencyUnavailableError(JarvisError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "dependency_unavailable"
    public_message = "A required dependency is unavailable."


class DatabaseError(DependencyUnavailableError):
    code = "database_error"
    public_message = "Database operation failed."


class CacheError(DependencyUnavailableError):
    code = "cache_error"
    public_message = "Cache operation failed."


class RetryExhaustedError(DependencyUnavailableError):
    code = "retry_exhausted"
    public_message = "Operation failed after repeated attempts."

    def __init__(self, operation: str, attempts: int) -> None:
        super().__init__(
            f"{operation} failed after {attempts} attempts",
            details={"operation": operation, "attempts": attempts},
        )
        self.operation = operation
        self.attempts = attempts


# --------------------------------------------------------------------------- #
# Retry with exponential backoff
# --------------------------------------------------------------------------- #
async def retry_async[T](
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.25,
    max_delay: float = 5.0,
    factor: float = 2.0,
    jitter: bool = True,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    operation: str = "operation",
) -> T:
    """Run ``func`` up to ``attempts`` times with exponential backoff.

    Delay before retry *n* is ``min(max_delay, base_delay * factor**(n-1))``, with
    "equal jitter" (uniform in the upper half) when ``jitter`` is true.
    Raises :class:`RetryExhaustedError` (chained to the last failure) when all attempts fail.
    Cancellation is never swallowed. Only the exception *type* is logged - messages may
    contain connection details.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except retry_on as exc:
            last_error = exc
            if attempt == attempts:
                break
            delay = min(max_delay, base_delay * factor ** (attempt - 1))
            if jitter:
                delay = random.uniform(delay / 2, delay)
            logger.warning(
                "retry.scheduled",
                operation=operation,
                attempt=attempt,
                max_attempts=attempts,
                delay_seconds=round(delay, 3),
                error_type=type(exc).__name__,
            )
            await _sleep(delay)

    logger.error(
        "retry.exhausted",
        operation=operation,
        attempts=attempts,
        error_type=type(last_error).__name__ if last_error else None,
    )
    raise RetryExhaustedError(operation, attempts) from last_error


# --------------------------------------------------------------------------- #
# Centralized handlers
# --------------------------------------------------------------------------- #
def _correlation_id(request: Request) -> str | None:
    # Read from ASGI scope state: the generic-Exception handler runs *outside* the
    # correlation middleware, where the contextvar has already been reset.
    state = request.scope.get("state") or {}
    value = state.get("correlation_id")
    return value if isinstance(value, str) else None


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    correlation_id = _correlation_id(request)
    error: dict[str, Any] = {"code": code, "message": message, "correlation_id": correlation_id}
    if details:
        error["details"] = details
    response_headers = dict(headers or {})
    if correlation_id:
        response_headers[CORRELATION_HEADER] = correlation_id
    return JSONResponse(status_code=status_code, content={"error": error}, headers=response_headers)


async def jarvis_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, JarvisError)
    log = logger.error if exc.status_code >= 500 else logger.warning
    log(
        "request.app_error",
        error_code=exc.code,
        error_type=type(exc).__name__,
        message=exc.message,
        status_code=exc.status_code,
        path=request.url.path,
    )
    return _error_response(request, status_code=exc.status_code, code=exc.code, message=exc.public_message)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Only location/message/type: never echo submitted input back to the client.
    details = [
        {"loc": [str(part) for part in err.get("loc", ())], "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    logger.info("request.validation_failed", path=request.url.path, error_count=len(details))
    return _error_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="validation_error",
        message="Request validation failed.",
        details=details,
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return _error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=str(exc.detail),
        headers=getattr(exc, "headers", None),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last line of defense: fail closed with a generic 500 and log everything server-side."""
    logger.error(
        "request.unhandled_exception",
        error_type=type(exc).__name__,
        path=request.url.path,
        exc_info=exc,
    )
    return _error_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=JarvisError.code,
        message=JarvisError.public_message,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install the central handlers on ``app``."""
    app.add_exception_handler(JarvisError, jarvis_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
