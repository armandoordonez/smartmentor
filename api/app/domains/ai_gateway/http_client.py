"""`HttpAiService`: adaptador HTTP del puerto hacia `ai/` (docs/contracts/ai-service-v1.md).

Autenticación de servicio a servicio con *client credentials* de Keycloak (ADR 0014). Reenvía el
`X-Request-ID` de la petición en curso. Un fallo de red o un 5xx se traduce a
`503 AI_SERVICE_UNAVAILABLE` (reintentable); un 404 de trabajo, a `JOB_NOT_FOUND`.
"""

import logging
import time
from datetime import datetime
from typing import Any, Protocol

import httpx

from app.core.logging import request_id_var
from app.domains.ai_gateway.entities import AiJobError, JobRef, JobRefs, JobStatus
from app.domains.ai_gateway.exceptions import (
    AiBudgetExceededError,
    AiJobNotFoundError,
    AiServiceUnavailableError,
)

logger = logging.getLogger("app.ai_gateway")

TOKEN_SAFETY_MARGIN_SECONDS = 30


class TokenProvider(Protocol):
    async def token(self) -> str: ...


class ClientCredentialsTokenProvider:
    """Obtiene y cachea el token de servicio de Keycloak hasta poco antes de que venza."""

    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        client: httpx.AsyncClient,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = client
        self._token: str | None = None
        self._expires_at = 0.0

    async def token(self) -> str:
        if self._token is not None and time.monotonic() < self._expires_at:
            return self._token
        try:
            response = await self._client.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("could not obtain the AI service token")
            raise AiServiceUnavailableError("Could not authenticate with the AI service.") from exc
        self._token = str(body["access_token"])
        lifetime = max(int(body.get("expires_in", 60)) - TOKEN_SAFETY_MARGIN_SECONDS, 1)
        self._expires_at = time.monotonic() + lifetime
        return self._token


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def parse_job(body: dict[str, Any]) -> JobStatus:
    error = body.get("error")
    refs = body.get("refs") or {}
    return JobStatus(
        job_id=str(body["job_id"]),
        job_type=str(body["job_type"]),
        status=str(body["status"]),
        contract=body.get("contract"),
        result=body.get("result"),
        error=(
            AiJobError(
                code=str(error["code"]),
                message=str(error.get("message", "")),
                retryable=bool(error.get("retryable", False)),
            )
            if error
            else None
        ),
        attempts=int(body.get("attempts") or 0),
        cost_usd=body.get("cost_usd"),
        refs=JobRefs(
            course_id=refs.get("course_id"),
            topic_id=refs.get("topic_id"),
            enrollment_id=refs.get("enrollment_id"),
        ),
        created_at=_parse_dt(body.get("created_at")),
        started_at=_parse_dt(body.get("started_at")),
        finished_at=_parse_dt(body.get("finished_at")),
    )


class HttpAiService:
    def __init__(self, client: httpx.AsyncClient, tokens: TokenProvider | None = None) -> None:
        self._client = client
        self._tokens = tokens

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        headers: dict[str, str] = {}
        request_id = request_id_var.get()
        if request_id:
            headers["X-Request-ID"] = request_id
        if self._tokens is not None:
            headers["Authorization"] = f"Bearer {await self._tokens.token()}"
        try:
            response = await self._client.request(
                method, path, json=json, params=params, headers=headers
            )
        except httpx.HTTPError as exc:
            logger.error("the AI service is unreachable")
            raise AiServiceUnavailableError from exc
        if response.status_code >= 500:
            code = _problem_code(response)
            if code == "BUDGET_EXCEEDED":
                raise AiBudgetExceededError()
            logger.error("the AI service answered %s", response.status_code)
            raise AiServiceUnavailableError
        return response

    async def submit_job(
        self,
        job_type: str,
        input: dict[str, Any],
        idempotency_key: str,
        refs: JobRefs | None = None,
    ) -> JobRef:
        response = await self._request(
            "POST",
            "/v1/jobs",
            json={
                "job_type": job_type,
                "idempotency_key": idempotency_key,
                "input": input,
                "refs": (refs or JobRefs()).as_dict(),
                "requested_by": "api",
            },
        )
        if response.status_code not in (200, 202):
            raise AiServiceUnavailableError(
                f"The AI service rejected the job ({_problem_code(response)})."
            )
        body = response.json()
        return JobRef(
            job_id=str(body["job_id"]),
            job_type=str(body["job_type"]),
            status=str(body["status"]),
            created_at=_parse_dt(body.get("created_at")),
        )

    async def get_job(self, job_id: str) -> JobStatus:
        response = await self._request("GET", f"/v1/jobs/{job_id}")
        if response.status_code == 404:
            raise AiJobNotFoundError(job_id)
        if response.status_code != 200:
            raise AiServiceUnavailableError
        return parse_job(response.json())

    async def list_jobs(
        self,
        *,
        job_type: str | None = None,
        status: str | None = None,
        course_id: int | None = None,
        limit: int = 100,
    ) -> list[JobStatus]:
        params = {
            key: value
            for key, value in {
                "job_type": job_type,
                "status": status,
                "course_id": course_id,
                "limit": min(limit, 100),
            }.items()
            if value is not None
        }
        response = await self._request("GET", "/v1/jobs", params=params)
        if response.status_code != 200:
            raise AiServiceUnavailableError
        return [parse_job(item) for item in response.json().get("items", [])]

    async def run_task(
        self,
        task: str,
        input: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request("POST", f"/v1/tasks/{task}", json=input)
        if response.status_code != 200:
            raise AiServiceUnavailableError(
                f"The AI task {task} failed ({_problem_code(response)})."
            )
        body: dict[str, Any] = response.json()
        return body


def _problem_code(response: httpx.Response) -> str:
    try:
        return str(response.json().get("code", f"HTTP_{response.status_code}"))
    except ValueError:
        return f"HTTP_{response.status_code}"
