"""HTTP schemas of ``/v1`` (``docs/contracts/ai-service-v1.md``)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ports.jobs import JobStatus


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobRefsBody(Strict):
    course_id: int | None = Field(default=None, ge=1)
    topic_id: int | None = Field(default=None, ge=1)
    enrollment_id: int | None = Field(default=None, ge=1)


class CreateJobRequest(Strict):
    job_type: str = Field(min_length=1, max_length=60)
    idempotency_key: str = Field(min_length=1, max_length=200)
    input: dict[str, Any]
    refs: JobRefsBody = Field(default_factory=JobRefsBody)
    requested_by: Literal["api", "eval"] = "api"


class JobCreatedResponse(BaseModel):
    job_id: UUID
    job_type: str
    status: JobStatus
    created_at: datetime


class JobErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool


class JobSummary(BaseModel):
    job_id: UUID
    job_type: str
    status: JobStatus
    contract: str | None
    error: JobErrorBody | None
    attempts: int
    refs: JobRefsBody
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobResponse(JobSummary):
    result: dict[str, Any] | None
    cost_usd: float | None


class JobListResponse(BaseModel):
    items: list[JobSummary]
    total: int
    limit: int
    offset: int


class PromptVersionBody(BaseModel):
    version: int
    sha256: str
    calls: int
    invalid_output_rate: float | None
    system: str | None = None
    user: str | None = None


class PromptBody(BaseModel):
    id: str
    name_es: str
    task: str
    current_version: int
    model_tier: str
    temperature: float
    output_schema: str
    contract: str
    screens: list[str]
    versions: list[PromptVersionBody]


class PromptCatalogResponse(BaseModel):
    schema_version: str = "v1"
    prompts: list[PromptBody]


class HealthResponse(BaseModel):
    status: str
