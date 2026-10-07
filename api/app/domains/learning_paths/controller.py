"""Endpoints de rutas: /learning-paths, /enrollments y /path-steps."""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.auth.dependencies import require_roles
from app.auth.policies import ANY_ROLE, STAFF
from app.common.controller import build_crud_router
from app.domains.learning_paths.dependencies import (
    get_enrollment_service,
    get_learning_path_service,
    get_path_step_service,
)
from app.domains.learning_paths.entities import Enrollment, LearningPath, PathStep
from app.domains.learning_paths.schemas import (
    EnrollmentCreate,
    EnrollmentResponse,
    EnrollmentUpdate,
    LearningPathCreate,
    LearningPathResponse,
    LearningPathUpdate,
    PathStepCreate,
    PathStepResponse,
    PathStepUpdate,
)


def learning_path_filters(course_id: Annotated[int | None, Query()] = None) -> dict[str, Any]:
    return {"course_id": course_id}


def enrollment_filters(
    user_id: Annotated[int | None, Query()] = None,
    learning_path_id: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return {"user_id": user_id, "learning_path_id": learning_path_id, "status": status}


def path_step_filters(
    enrollment_id: Annotated[int | None, Query()] = None,
    topic_id: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return {"enrollment_id": enrollment_id, "topic_id": topic_id, "status": status}


routers: list[APIRouter] = [
    build_crud_router(
        prefix="/learning-paths",
        read_guard=require_roles(*ANY_ROLE),
        write_guard=require_roles(*STAFF),
        tag="learning-paths",
        get_service=get_learning_path_service,
        entity_cls=LearningPath,
        create_schema=LearningPathCreate,
        update_schema=LearningPathUpdate,
        response_schema=LearningPathResponse,
        filters=learning_path_filters,
    ),
    build_crud_router(
        prefix="/enrollments",
        read_guard=require_roles(*STAFF),
        write_guard=require_roles(*STAFF),
        tag="enrollments",
        get_service=get_enrollment_service,
        entity_cls=Enrollment,
        create_schema=EnrollmentCreate,
        update_schema=EnrollmentUpdate,
        response_schema=EnrollmentResponse,
        filters=enrollment_filters,
    ),
    build_crud_router(
        prefix="/path-steps",
        read_guard=require_roles(*STAFF),
        write_guard=require_roles(*STAFF),
        tag="path-steps",
        get_service=get_path_step_service,
        entity_cls=PathStep,
        create_schema=PathStepCreate,
        update_schema=PathStepUpdate,
        response_schema=PathStepResponse,
        filters=path_step_filters,
    ),
]
