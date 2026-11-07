"""Traducción de errores a respuestas HTTP con formato RFC 9457 (application/problem+json)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.exceptions import DomainError
from app.core.logging import request_id_var

logger = logging.getLogger("app.errors")

PROBLEM_JSON = "application/problem+json"

# Extensiones que el catálogo (docs/contracts/error-codes.md) permite en el cuerpo del error.
ALLOWED_EXTENSIONS = frozenset(
    {"errors", "retryable", "job_id", "cycle", "missing", "attempts_used", "max_attempts"}
)


def problem_response(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
    code: str,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://smartmentor/errors/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "request_id": request_id_var.get(),
    }
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


async def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    status = exc.status_code
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    extra = {k: v for k, v in exc.extra.items() if k in ALLOWED_EXTENSIONS}
    return problem_response(
        request,
        status=status,
        title=exc.title,
        detail=exc.detail,
        code=exc.code,
        extra=extra,
        headers=headers,
    )


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Solo ubicación, mensaje y tipo: nunca se devuelve el valor recibido.
    errors = [
        {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in exc.errors()
    ]
    return problem_response(
        request,
        status=422,
        title="Validation error",
        detail="The request is not valid.",
        code="VALIDATION_ERROR",
        extra={"errors": errors},
    )


async def _http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return problem_response(
        request,
        status=exc.status_code,
        title="HTTP error",
        detail=str(exc.detail),
        code=f"HTTP_{exc.status_code}",
    )


async def _unexpected_error_handler(
    request: Request,
    exc: Exception,  # noqa: ARG001  (firma fija del manejador de Starlette)
) -> JSONResponse:
    logger.exception("unexpected error", extra={"path": request.url.path})
    return problem_response(
        request,
        status=500,
        title="Internal server error",
        detail="An unexpected error occurred.",
        code="INTERNAL_ERROR",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
