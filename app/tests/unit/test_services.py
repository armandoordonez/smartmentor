"""Servicios: solo presentan datos de la API, sin reglas de negocio."""

import json

import pytest
from support import FIXTURES_DIR

from clients.base import ApiError
from clients.fixtures import FixturesClient
from clients.models import LearningPathCard
from components.formatting import approx_duration, duration, initials, percent, percent_points
from services.assessment import rubric_view
from services.catalog import card_view, load_catalog, open_path
from services.profile import resume_values, save_description, save_resume
from services.staff_content import (
    video_link_markdown,
    video_thumbnail_markdown,
    youtube_thumbnail_url,
    youtube_watch_url,
)


def test_catalog_groups_the_cards_in_two_sections_with_figma_meta() -> None:
    view = load_catalog(FixturesClient("learner"))
    assert [c.name for c in view.paths] == [
        "Fundamentos de Machine Learning",
        "Estadística para ciencia de datos",
        "Python para análisis de datos",
    ]
    assert [c.meta for c in view.paths] == [
        "5 temas · ~8 h · Intermedio",
        "5 temas · ~6 h · Básico",
        "4 temas · ~5 h · Básico",
    ]
    assert [c.meta for c in view.applied_ai] == [
        "5 temas · ~3 h 35 min · Básico",
        "5 temas · ~3 h 30 min · Básico",
        "4 temas · ~3 h · Básico",
    ]
    assert view.applied_ai[0].tag_text == "NUEVO · ANTHROPIC"
    assert not view.is_empty


def test_card_without_tags_has_no_eyebrow() -> None:
    card = LearningPathCard(id=9, name="X", topics_count=1, estimated_minutes=30, level="advanced")
    assert card_view(card).tag_text is None
    assert card_view(card).meta == "1 temas · ~30 min · Avanzado"


def test_open_path_returns_the_existing_enrollment_on_conflict() -> None:
    client = FixturesClient("learner_in_path")
    assert open_path(client, 1).id == 7


def test_open_path_propagates_other_errors() -> None:
    with pytest.raises(ApiError) as caught:
        open_path(FixturesClient("learner"), 999)
    assert caught.value.code == "LEARNING_PATH_NOT_PUBLISHED"


def test_saving_the_description_keeps_the_resume() -> None:
    client = FixturesClient("learner")
    profile = client.get_profile()
    saved = save_description(client, profile, "  Nueva  ")
    assert saved.description == "Nueva"
    assert saved.job_title == "Analista de datos"
    assert saved.tools == ["Excel", "SQL", "Python"]


def test_saving_the_resume_keeps_the_description() -> None:
    client = FixturesClient("learner")
    profile = client.get_profile()
    values = resume_values(profile)
    saved = save_resume(
        client,
        profile,
        type(values)(
            education_level="postgraduate",
            qualification_title="",
            job_title="Líder",
            experience_band="more_than_5_years",
            tools=("R",),
            languages=(("en", "C1"),),
        ),
    )
    assert saved.description == profile.description
    assert saved.qualification_title is None
    assert (saved.education_level, saved.job_title) == ("postgraduate", "Líder")
    assert saved.languages[0].cefr_level == "C1"


def test_resume_values_roundtrip() -> None:
    profile = FixturesClient("learner").get_profile()
    values = resume_values(profile)
    assert values.tools == ("Excel", "SQL", "Python")
    assert values.languages == (("en", "B1"),)


def test_rubric_view_derives_the_minimum_from_the_ratio() -> None:
    grading = {
        "item_type": "short_answer",
        "grader": "llm_judge",
        "min_criteria_ratio": 0.6667,
        "is_correct": True,
        "criteria_met": 2,
        "criteria_total": 3,
        "rubric_detail": [
            {"criterion": "A", "met": True, "evidence": "ok"},
            {"criterion": "B", "met": True, "evidence": ""},
            {"criterion": "C", "met": False, "evidence": "falta"},
        ],
    }
    view = rubric_view(grading)
    assert view is not None
    assert (view.criteria_met, view.criteria_total, view.min_met) == (2, 3, 2)
    assert view.graded_by == "IA"
    assert [c.met for c in view.criteria] == [True, True, False]
    assert rubric_view({**grading, "grader": "human"}).graded_by == "un instructor"  # type: ignore[union-attr]


def test_rubric_view_is_none_for_multiple_choice() -> None:
    grading = json.loads((FIXTURES_DIR / "attempt_result.json").read_text(encoding="utf-8"))
    assert rubric_view(grading["answers"][0]["grading"]) is None


def test_formatting_matches_the_design() -> None:
    assert percent(0.92) == "92 %"
    assert percent_points(91.6) == "92 %"
    assert duration(80) == "1 h 20 min"
    assert duration(480) == "8 h"
    assert approx_duration(215) == "~3 h 35 min"
    assert initials("Laura Martínez") == "LM"
    assert initials("") == "?"


def test_video_links_point_to_youtube_and_its_thumbnail() -> None:
    assert youtube_watch_url("dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert (
        youtube_thumbnail_url("dQw4w9WgXcQ") == "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg"
    )
    assert video_thumbnail_markdown("dQw4w9WgXcQ") == (
        "[![Portada del video en YouTube](https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg)]"
        "(https://www.youtube.com/watch?v=dQw4w9WgXcQ)"
    )


def test_video_title_link_escapes_brackets_and_rejects_odd_ids() -> None:
    assert video_link_markdown("Qué es [DW]?", "dQw4w9WgXcQ") == (
        r"[Qué es \[DW\]?](https://www.youtube.com/watch?v=dQw4w9WgXcQ)"
    )
    # Un id que no tiene la forma de YouTube no arma enlaces (ni HTML ni otra URL).
    for odd in ("corto", 'x"><img src=1>', "dQw4w9WgXcQ/../x"):
        assert youtube_watch_url(odd) is None
        assert video_thumbnail_markdown(odd) is None
        assert video_link_markdown("Título", odd) == "Título"


def test_save_resume_accepts_languages_from_a_reloaded_models_module() -> None:
    """Streamlit recarga `clients/models.py` y el perfil de la sesión queda con la clase vieja."""
    from pydantic import BaseModel

    from clients.models import Profile
    from components.resume_form import ResumeValues

    class OldLanguage(BaseModel):  # otra clase con los mismos campos, como tras la recarga
        code: str
        cefr_level: str

    profile = Profile.model_construct(
        **{
            **FixturesClient("learner").get_profile().__dict__,
            "languages": [OldLanguage(code="en", cefr_level="B1")],
        }
    )
    values = ResumeValues(
        education_level="undergraduate",
        qualification_title="Ingeniería industrial",
        job_title="Analista de datos",
        experience_band="1_3_years",
        tools=("Excel", "SQL"),
        languages=(("en", "B1"),),
    )
    saved = save_resume(FixturesClient("learner"), profile, values)
    assert [(lang.code, lang.cefr_level) for lang in saved.languages] == [("en", "B1")]
