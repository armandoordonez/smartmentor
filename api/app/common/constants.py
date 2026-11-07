"""Constantes y enumeraciones compartidas. Los valores coinciden con los CHECK de la base."""

from enum import StrEnum


class RoleCode(StrEnum):
    """Roles de la plataforma (sección 13 del plan). Sin rol `evaluator`: se asigna por curso."""

    ADMIN = "admin"
    INSTRUCTOR = "instructor"
    LEARNER = "learner"


# Orden de mayor a menor privilegio: define `roles` y `default_role` de GET /me (CU-35).
ROLE_PRIVILEGE_ORDER: tuple[RoleCode, ...] = (
    RoleCode.ADMIN,
    RoleCode.INSTRUCTOR,
    RoleCode.LEARNER,
)


class CourseStatus(StrEnum):
    DRAFT = "draft"
    EXTRACTING = "extracting"
    EXTRACTION_FAILED = "extraction_failed"
    IN_REVIEW = "in_review"
    GENERATING_CONTENT = "generating_content"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class BloomLevel(StrEnum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class SyllabusSourceType(StrEnum):
    PDF = "pdf"
    TEXT = "text"


class TopicOrigin(StrEnum):
    LLM = "llm"
    INSTRUCTOR = "instructor"


class TopicReviewStatus(StrEnum):
    UNCHANGED = "unchanged"
    CORRECTED = "corrected"
    ADDED = "added"
    DELETED = "deleted"


class ConsentType(StrEnum):
    DATA_PROCESSING = "data_processing"
    PILOT_RESEARCH = "pilot_research"


class DataSubjectRequestType(StrEnum):
    DELETION = "deletion"
    ACCESS = "access"
    RECTIFICATION = "rectification"


class DataSubjectRequestStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class EducationLevel(StrEnum):
    SECONDARY = "secondary"
    TECHNICAL = "technical"
    UNDERGRADUATE = "undergraduate"
    POSTGRADUATE = "postgraduate"
    OTHER = "other"
    NONE = "none"


class ExperienceBand(StrEnum):
    NONE = "none"
    LESS_THAN_1_YEAR = "less_than_1_year"
    ONE_TO_THREE_YEARS = "1_3_years"
    THREE_TO_FIVE_YEARS = "3_5_years"
    MORE_THAN_5_YEARS = "more_than_5_years"


class LearningPathStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class JobType(StrEnum):
    """Tipos de trabajo de `ai/` (docs/contracts/ai-service-v1.md, tabla 3)."""

    SYLLABUS_STRUCTURE = "syllabus.structure"
    COURSE_GENERATE_CONTENT = "course.generate_content"
