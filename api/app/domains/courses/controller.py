"""Endpoints de cursos: /courses, /topics y /topic-prerequisites."""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.auth.dependencies import require_roles
from app.auth.policies import ANY_ROLE, STAFF
from app.common.controller import build_crud_router
from app.domains.courses.dependencies import (
    get_course_service,
    get_topic_prerequisite_service,
    get_topic_service,
)
from app.domains.courses.entities import Course, Topic, TopicPrerequisite
from app.domains.courses.schemas import (
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    TopicCreate,
    TopicPrerequisiteCreate,
    TopicPrerequisiteResponse,
    TopicPrerequisiteUpdate,
    TopicResponse,
    TopicUpdate,
)


def course_filters(
    owner_user_id: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return {"owner_user_id": owner_user_id, "status": status}


def topic_filters(course_id: Annotated[int | None, Query()] = None) -> dict[str, Any]:
    return {"course_id": course_id}


def prerequisite_filters(
    topic_id: Annotated[int | None, Query()] = None,
    prerequisite_topic_id: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    return {"topic_id": topic_id, "prerequisite_topic_id": prerequisite_topic_id}


routers: list[APIRouter] = [
    build_crud_router(
        prefix="/courses",
        read_guard=require_roles(*ANY_ROLE),
        write_guard=require_roles(*STAFF),
        tag="courses",
        get_service=get_course_service,
        entity_cls=Course,
        create_schema=CourseCreate,
        update_schema=CourseUpdate,
        response_schema=CourseResponse,
        filters=course_filters,
    ),
    build_crud_router(
        prefix="/topics",
        read_guard=require_roles(*ANY_ROLE),
        write_guard=require_roles(*STAFF),
        tag="topics",
        get_service=get_topic_service,
        entity_cls=Topic,
        create_schema=TopicCreate,
        update_schema=TopicUpdate,
        response_schema=TopicResponse,
        filters=topic_filters,
    ),
    build_crud_router(
        prefix="/topic-prerequisites",
        read_guard=require_roles(*ANY_ROLE),
        write_guard=require_roles(*STAFF),
        tag="topic-prerequisites",
        get_service=get_topic_prerequisite_service,
        entity_cls=TopicPrerequisite,
        create_schema=TopicPrerequisiteCreate,
        update_schema=TopicPrerequisiteUpdate,
        response_schema=TopicPrerequisiteResponse,
        filters=prerequisite_filters,
    ),
]
