"""Constantes del dominio de contenido (los valores coinciden con los CHECK de la base)."""

from enum import StrEnum


class ReviewStatus(StrEnum):
    """`resources.review_status` y `assessment_items.review_status` (plan 5.1)."""

    AUTO_REJECTED = "auto_rejected"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    RETIRED = "retired"


class ResourceType(StrEnum):
    TEXT = "text"
    VIDEO = "video"


class ResourceKind(StrEnum):
    MAIN = "main"
    REMEDIAL = "remedial"
    PERSONAL_EXAMPLE = "personal_example"


class Audience(StrEnum):
    ALL_LEARNERS = "all_learners"
    ENROLLMENT = "enrollment"


class VideoStatus(StrEnum):
    CANDIDATE = "candidate"
    IN_USE = "in_use"
    BACKUP = "backup"
    REJECTED = "rejected"


class VideoOrigin(StrEnum):
    YOUTUBE_API = "youtube_api"
    INSTRUCTOR = "instructor"


class ItemType(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"


class ContentJobType(StrEnum):
    """Tipos de trabajo de `ai/` que ingiere este dominio (ai-service-v1.md, tabla 3)."""

    EXPLAIN_TOPIC = "content.explain_topic"
    CHECK_FAITHFULNESS = "content.check_faithfulness"
    QUIZ_BANK = "items.generate_quiz_bank"
    FINAL_BANK = "items.generate_final_bank"
    DIAGNOSTIC_BANK = "diagnostic.generate_items"
    ITEM_REVIEW = "items.review"
    VIDEO_CANDIDATES = "video.collect_candidates"


MULTIPLE_CHOICE_OPTIONS = 4
RUBRIC_MIN_CRITERIA = 2
RUBRIC_MAX_CRITERIA = 3
RUBRIC_POINTS_TOLERANCE = 0.01
# Un índice de calidad de video con menos calificaciones se muestra como «Midiendo» (ADR 0016).
VIDEO_QUALITY_MIN_RATINGS = 5
