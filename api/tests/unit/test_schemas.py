import pytest
from pydantic import ValidationError

from app.domains.assessments.schemas import AssessmentAttemptCreate
from app.domains.content.schemas import ResourceCreate
from app.domains.courses.schemas import TopicCreate
from app.domains.identity.schemas import UserCreate, UserUpdate
from app.domains.learning_paths.schemas import LearningPathCreate


def test_embedding_must_have_the_configured_dimension() -> None:
    with pytest.raises(ValidationError):
        TopicCreate(course_id=1, name="A", embedding=[0.1, 0.2])
    assert TopicCreate(course_id=1, name="A", embedding=[0.0] * 1024).embedding is not None


def test_resource_needs_url_or_content() -> None:
    with pytest.raises(ValidationError):
        ResourceCreate(topic_id=1, resource_type="video")
    assert ResourceCreate(topic_id=1, resource_type="video", url="https://youtu.be/x")


def test_topic_attempt_needs_a_step_and_final_cannot_have_one() -> None:
    with pytest.raises(ValidationError):
        AssessmentAttemptCreate(enrollment_id=1, assessment_type="topic")
    with pytest.raises(ValidationError):
        AssessmentAttemptCreate(enrollment_id=1, assessment_type="final", path_step_id=3)
    assert AssessmentAttemptCreate(enrollment_id=1, assessment_type="topic", path_step_id=3)


def test_thresholds_are_percentages() -> None:
    with pytest.raises(ValidationError):
        LearningPathCreate(course_id=1, name="Ruta", topic_pass_threshold=101)
    path = LearningPathCreate(course_id=1, name="Ruta")
    assert (path.topic_pass_threshold, path.final_pass_threshold, path.max_attempts) == (70, 80, 3)


def test_identity_pair_is_validated_on_create_and_update() -> None:
    with pytest.raises(ValidationError):
        UserCreate(full_name="K", email="k@example.com", identity_provider="keycloak")
    with pytest.raises(ValidationError):
        UserUpdate(identity_subject="abc")
    assert UserUpdate(identity_provider=None, identity_subject=None).model_fields_set == {
        "identity_provider",
        "identity_subject",
    }
