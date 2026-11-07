"""HTTP errors as RFC 9457 problem details (``application/problem+json``).

Codes come from ``docs/contracts/error-codes.md``. ``detail`` is English for whoever debugs and
never carries personal data, SQL, traces or secrets.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

logger = logging.getLogger("app.errors")

PROBLEM_JSON = "application/problem+json"


class ApiError(Exception):
    """An error with a stable ``code`` that becomes a problem+json response."""

    def __init__(
        self,
        status: int,
        code: str,
        detail: str,
        *,
        title: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.title = title or code.replace("_", " ").capitalize()
        self.extra = extra or {}


def problem_body(
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    instance: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": f"https://smartmentor/errors/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        "code": code,
        "request_id": request_id_var.get(),
    }
    if extra:
        body.update(extra)
    return body


def problem_response(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = problem_body(
        status=status,
        code=code,
        title=title,
        detail=detail,
        instance=request.url.path,
        extra=extra,
    )
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def validation_errors(errors: Any) -> list[dict[str, Any]]:
    """Location, message and type only: the received value is never echoed back."""
    return [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in errors]


async def _api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):  # pragma: no cover - registered only for ApiError
        raise exc
    headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
    return problem_response(
        request,
        status=exc.status,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        extra=exc.extra,
        headers=headers,
    )


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # pragma: no cover
        raise exc
    return problem_response(
        request,
        status=422,
        code="VALIDATION_ERROR",
        title="Validation error",
        detail="The request is not valid.",
        extra={"errors": validation_errors(exc.errors())},
    )


async def _http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover
        raise exc
    code = {404: "NOT_FOUND", 413: "PAYLOAD_TOO_LARGE", 415: "UNSUPPORTED_MEDIA_TYPE"}.get(
        exc.status_code, f"HTTP_{exc.status_code}"
    )
    return problem_response(
        request, status=exc.status_code, code=code, title="HTTP error", detail=str(exc.detail)
    )


async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unexpected error: %s",
        exc.__class__.__name__,
        exc_info=exc,
        extra={"path": request.url.path},
    )
    return problem_response(
        request,
        status=500,
        code="INTERNAL_ERROR",
        title="Internal server error",
        detail="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
