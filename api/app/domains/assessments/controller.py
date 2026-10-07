"""Endpoints de evaluaciones: /diagnostics, /assessment-attempts y /badges."""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.auth.dependencies import require_roles
from app.auth.policies import STAFF
from app.common.controller import build_crud_router
from app.domains.assessments.dependencies import (
    get_assessment_attempt_service,
    get_badge_service,
    get_diagnostic_service,
)
from app.domains.assessments.entities import AssessmentAttempt, Badge, Diagnostic
from app.domains.assessments.schemas import (
    AssessmentAttemptCreate,
    AssessmentAttemptResponse,
    AssessmentAttemptUpdate,
    BadgeCreate,
    BadgeResponse,
    BadgeUpdate,
    DiagnosticCreate,
    DiagnosticResponse,
    DiagnosticUpdate,
)


def enrollment_filter(enrollment_id: Annotated[int | None, Query()] = None) -> dict[str, Any]:
    return {"enrollment_id": enrollment_id}


def attempt_filters(
    enrollment_id: Annotated[int | None, Query()] = None,
    path_step_id: Annotated[int | None, Query()] = None,
    assessment_type: Annotated[str | None, Query()] = None,
    passed: Annotated[bool | None, Query()] = None,
) -> dict[str, Any]:
    return {
        "enrollment_id": enrollment_id,
        "path_step_id": path_step_id,
        "assessment_type": assessment_type,
        "passed": passed,
    }


routers: list[APIRouter] = [
    build_crud_router(
        prefix="/diagnostics",
        read_guard=require_roles(*STAFF),
        write_guard=require_roles(*STAFF),
        tag="diagnostics",
        get_service=get_diagnostic_service,
        entity_cls=Diagnostic,
        create_schema=DiagnosticCreate,
        update_schema=DiagnosticUpdate,
        response_schema=DiagnosticResponse,
        filters=enrollment_filter,
    ),
    build_crud_router(
        prefix="/assessment-attempts",
        read_guard=require_roles(*STAFF),
        write_guard=require_roles(*STAFF),
        tag="assessment-attempts",
        get_service=get_assessment_attempt_service,
        entity_cls=AssessmentAttempt,
        create_schema=AssessmentAttemptCreate,
        update_schema=AssessmentAttemptUpdate,
        response_schema=AssessmentAttemptResponse,
        filters=attempt_filters,
    ),
    build_crud_router(
        prefix="/badges",
        read_guard=require_roles(*STAFF),
        write_guard=require_roles(*STAFF),
        tag="badges",
        get_service=get_badge_service,
        entity_cls=Badge,
        create_schema=BadgeCreate,
        update_schema=BadgeUpdate,
        response_schema=BadgeResponse,
        filters=enrollment_filter,
    ),
]
