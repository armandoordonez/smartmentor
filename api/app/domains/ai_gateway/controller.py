"""`GET /jobs/{id}`: estado de un trabajo de IA; si terminó, la API ingiere el resultado."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import require_roles
from app.auth.policies import ANY_ROLE
from app.domains.ai_gateway.dependencies import JobServiceDep
from app.domains.ai_gateway.schemas import JobResponse
from app.domains.identity.authentication import CurrentUser

router = APIRouter(tags=["jobs"])

AnyUser = Annotated[CurrentUser, Depends(require_roles(*ANY_ROLE))]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, user: AnyUser, service: JobServiceDep) -> JobResponse:
    """Consulta el trabajo (la app lo hace cada 2 s, U1x).

    Si `ai/` terminó, la API valida el resultado y lo escribe en una transacción idempotente en
    esta misma petición. Un trabajo fallido responde `502 AI_TASK_FAILED` (con `retryable`) o
    `503 AI_BUDGET_EXCEEDED`. Un trabajo ajeno responde `404 JOB_NOT_FOUND`.
    """
    view = await service.get(str(job_id), user)
    return JobResponse(
        job_id=view.job_id,
        job_type=view.job_type,
        status=view.status,
        progress_label=view.progress_label,
        ingested=view.ingested,
    )


routers: list[APIRouter] = [router]
