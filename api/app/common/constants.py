"""Constantes y enumeraciones compartidas. Los valores coinciden con los CHECK de la base."""

from enum import StrEnum


class RoleCode(StrEnum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class CourseStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class BloomLevel(StrEnum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class EnrollmentStatus(StrEnum):
    ENROLLED = "enrolled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class StepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ResourceType(StrEnum):
    VIDEO = "video"
    TEXT = "text"


class AssessmentType(StrEnum):
    TOPIC = "topic"
    FINAL = "final"


class LlmCallStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
