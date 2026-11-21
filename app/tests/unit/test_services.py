"""Servicios: solo presentan datos de la API, sin reglas de negocio."""

import json

import pytest
from support import FIXTURES_DIR

from clients.base import ApiError
from clients.fixtures import FixturesClient
from clients.models import (
    AssessmentItem,
    CourseSummary,
    Enrollment,
    LearningPathCard,
    NextAction,
    Page,
    PathDetail,
    PathSavings,
)
from components.formatting import approx_duration, duration, initials, percent, percent_points
from services.assessment import grading_rubric_step, rubric_criteria_count, rubric_view
from services.catalog import card_view, load_catalog, open_path
from services.learning import continue_label, passed_next_label, progress_line, savings_label
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
    card = LearningPathCard(
        id=9,
        name="X",
        course=CourseSummary(id=1, name="X"),
        topic_count=1,
        estimated_minutes=30,
        level="advanced",
    )
    assert card_view(card).tag_text is None
    assert card_view(card).meta == "1 tema · ~30 min · Avanzado"


# Tarjeta tal como la devuelve la API real (`GET /learning-paths`, 11-nov-2026): sin nivel, sin
# secciones ni etiquetas, la descripción dentro de `course` y 0 minutos si los temas no los tienen.
API_CARD = {
    "id": 2,
    "name": "Extraccion Y Almacenamiento De Datos",
    "group_label": "2026-2",
    "course": {"id": 2, "name": "Extraccion Y Almacenamiento De Datos", "description": "Curso."},
    "topics": [
        {"id": 4, "name": "Arquitecturas", "estimated_minutes": None, "is_mandatory": False},
        {"id": 5, "name": "ETL/ELT", "estimated_minutes": None, "is_mandatory": False},
        {"id": 6, "name": "Extracción web", "estimated_minutes": None, "is_mandatory": False},
    ],
    "topic_count": 3,
    "estimated_minutes": 0,
    "enrolled": True,
}


def test_card_from_the_real_api_omits_what_the_api_does_not_send() -> None:
    view = card_view(LearningPathCard.model_validate(API_CARD))
    assert view.meta == "3 temas"
    assert view.description == "Curso."
    assert view.tag_text is None
    assert view.cta_label == "Continuar ruta"


def test_catalog_from_the_real_api_goes_in_paths() -> None:
    page = Page[LearningPathCard].model_validate(
        {"items": [API_CARD], "total": 1, "limit": 100, "offset": 0}
    )
    client = FixturesClient("learner")
    client.list_learning_paths = lambda **_: page  # type: ignore[method-assign]
    view = load_catalog(client)
    assert [c.name for c in view.paths] == [API_CARD["name"]]
    assert view.applied_ai == []


def test_open_path_returns_the_existing_enrollment_on_conflict() -> None:
    client = FixturesClient("learner_in_path")
    assert open_path(client, 1).id == 7


def test_open_path_skips_the_post_when_the_catalog_says_it_is_enrolled() -> None:
    client = FixturesClient("learner_in_path")
    posted: list[int] = []

    def fail_create(path_id: int, *_: object, **__: object) -> Enrollment:
        posted.append(path_id)
        raise AssertionError("no debe inscribir de nuevo")

    client.create_enrollment = fail_create  # type: ignore[method-assign]
    assert open_path(client, 1, enrolled=True).id == 7
    assert posted == []


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
            {"criterion": "A", "met": True, "evidence": "ok", "reason": "Se cumple."},
            {"criterion": "B", "met": True, "evidence": ""},
            {"criterion": "C", "met": False, "evidence": "falta", "reason": None},
        ],
    }
    view = rubric_view(grading)
    assert view is not None
    assert [c.reason for c in view.criteria] == ["Se cumple.", "", ""]
    assert [c.evidence for c in view.criteria] == ["ok", "", "falta"]
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


# --- E5: ahorro y botón «Continuar» (B-039) -----------------------------------------------------


def _path_doc() -> PathDetail:
    raw = (FIXTURES_DIR / "learner" / "path.json").read_text(encoding="utf-8")
    return PathDetail.model_validate(json.loads(raw))


def test_savings_without_minutes_is_not_shown_as_zero() -> None:
    """El syllabus suele dejar `estimated_minutes` en null: la API suma 0 aunque haya omitidos."""
    path = _path_doc()
    unknown = path.model_copy(update={"savings": PathSavings(skipped_topics=1, skipped_minutes=0)})
    enrollment = FixturesClient("learner_path").list_enrollments().items[0]
    assert savings_label(unknown) == "—"
    assert "ahorro" not in progress_line(enrollment, unknown)
    assert "1 omitido por tu diagnóstico" in progress_line(enrollment, unknown)
    assert savings_label(path) == "1 h 20 min"
    assert "(ahorro 1 h 20 min)" in progress_line(enrollment, path)
    none = path.model_copy(update={"savings": PathSavings(skipped_topics=0, skipped_minutes=0)})
    assert savings_label(none) == "—"  # B-052: nunca «0 min» falso, igual que con omitidos


@pytest.mark.parametrize(
    ("action", "attempts_used", "expected"),
    [
        (NextAction(type="study_topic", step_id=813), 0, "Continuar tema"),
        (NextAction(type="continue_attempt", step_id=813, attempt_id=9), 0, "Continuar tema"),
        (NextAction(type="take_final"), 0, "Presentar evaluación final"),
        (NextAction(type="take_final"), 1, "Reintentar evaluación final"),
        (NextAction(type="continue_attempt", attempt_id=9), 0, "Continuar evaluación final"),
        (NextAction(type="review_final", attempt_id=9), 1, "Ver resultado de la evaluación final"),
        (NextAction(type="answer_survey"), 1, "Ver badge"),
        (NextAction(type="view_badge"), 1, "Ver badge"),
    ],
)
def test_continue_label_follows_the_next_action(
    action: NextAction, attempts_used: int, expected: str
) -> None:
    path = _path_doc()
    final = path.final.model_copy(update={"attempts_used": attempts_used})
    assert continue_label(action, path.model_copy(update={"final": final}), fixed=False) == expected


def test_fixed_path_names_the_next_topic() -> None:
    path = _path_doc()
    label = continue_label(NextAction(type="study_topic", step_id=813), path, fixed=True)
    assert label == "Continuar con Regresión logística"
    final = continue_label(NextAction(type="take_final"), path, fixed=True)
    assert final == "Presentar evaluación final"


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (NextAction(type="study_topic", step_id=814), "Siguiente tema"),
        (NextAction(type="continue_attempt", step_id=814, attempt_id=9), "Siguiente tema"),
        (NextAction(type="take_final"), "Presentar evaluación final"),
        (NextAction(type="view_badge"), "Ver badge"),
        (NextAction(type="none"), "Continuar"),
    ],
)
def test_passed_next_label_only_says_next_topic_when_there_is_one(
    action: NextAction, expected: str
) -> None:
    assert passed_next_label(action) == expected


# --- B-052 · pasos de «Calificando» --------------------------------------------------------------


def _short_item(summary: str | None) -> AssessmentItem:
    return AssessmentItem(
        item_id=1,
        topic_id=1,
        stem="Explica.",
        item_type="short_answer",
        rubric_summary=summary,
    )


def test_grading_step_uses_the_real_number_of_criteria_b052() -> None:
    two = _short_item("Se califica con una rúbrica de 2 criterios: (1) a y (2) b.")
    three = _short_item("Se califica con una rúbrica de 3 criterios: (1) a, (2) b y (3) c.")
    assert rubric_criteria_count([two]) == 2
    assert grading_rubric_step([two]) == "Aplicar la rúbrica de 2 criterios a tu respuesta corta"
    assert grading_rubric_step([three]).startswith("Aplicar la rúbrica de 3 criterios")


def test_grading_step_has_no_number_without_the_data_b052() -> None:
    no_summary = _short_item(None)
    free_text = _short_item("Se califica con una rúbrica.")
    assert rubric_criteria_count([no_summary]) is None
    assert grading_rubric_step([]) == "Aplicar la rúbrica a tu respuesta corta"
    assert grading_rubric_step([free_text]) == "Aplicar la rúbrica a tu respuesta corta"
    mixed = [_short_item("rúbrica de 2 criterios"), _short_item("rúbrica de 3 criterios")]
    assert grading_rubric_step(mixed) == "Aplicar la rúbrica a tu respuesta corta"
