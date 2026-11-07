"""Componentes de la sección 5.5 de `app/CLAUDE.md`, cada uno en una mini-aplicación `AppTest`.

Cada componente recibe sus datos por parámetro y devuelve lo que eligió la persona; aquí se verifica
lo que dibuja, lo que devuelve y que el estado va escrito además del color.
"""

import re

from apptest import plain
from streamlit.testing.v1 import AppTest


def run(script: object) -> AppTest:
    at = AppTest.from_function(script, default_timeout=20)  # type: ignore[arg-type]
    at.run()
    assert [e.value for e in at.exception] == []
    return at


def badges(at: AppTest) -> set[str]:
    """Textos de los `st.badge`, que AppTest ve como Markdown `:color-badge[texto]`."""
    found = (re.fullmatch(r":[a-z]+-badge\[(.*)\]", e.value) for e in at.markdown)
    return {match.group(1) for match in found if match}


def texts(at: AppTest) -> list[str]:
    values = [plain(e.value) for e in [*at.markdown, *at.caption, *at.subheader, *at.error]]
    return values + [plain(b.label) for b in at.button]


# --- loading_steps -------------------------------------------------------------------------------


def _loading() -> None:
    import streamlit as st

    from components.loading_steps import LoadingStep, render_loading_steps

    result = render_loading_steps(
        "Calculando tu nivel y proponiendo tu objetivo",
        [
            LoadingStep("Calificar tus respuestas del diagnóstico", "done"),
            LoadingStep("Combinar el resultado con tu perfil", "running"),
            LoadingStep("Proponer tu objetivo de aprendizaje", "pending"),
        ],
        "menos de 20 segundos",
        key="u1a",
    )
    st.session_state["result"] = result


def test_loading_steps_show_three_states_in_words() -> None:
    at = run(_loading)
    shown = texts(at)
    assert "Listo · Calificar tus respuestas del diagnóstico" in shown
    assert "En curso · Combinar el resultado con tu perfil" in shown
    assert "Pendiente · Proponer tu objetivo de aprendizaje" in shown
    assert "Tiempo estimado: menos de 20 segundos" in shown
    assert "Si tarda más: tu avance está guardado; puedes volver a tu ruta." in shown
    assert not at.button  # sin error no hay botones


def _loading_failed() -> None:
    import streamlit as st

    from components.loading_steps import LoadingStep, render_loading_steps

    st.session_state["result"] = render_loading_steps(
        "Calificando",
        [LoadingStep("Calificar", "failed")],
        "menos de 20 segundos",
        key="u1c",
        error_message="No pudimos calificar tu respuesta corta.",
    )


def test_loading_steps_failure_offers_retry_and_back() -> None:
    at = run(_loading_failed)
    assert at.error[0].value == "No pudimos calificar tu respuesta corta."
    assert [b.label for b in at.button] == ["Reintentar", "Volver a mi ruta"]
    at.button(key="loading-retry-u1c").click().run()
    assert at.session_state["result"] == "retry"
    at.button(key="loading-back-u1c").click().run()
    assert at.session_state["result"] == "back"


# --- objective_editor ----------------------------------------------------------------------------


def _objective() -> None:
    import streamlit as st

    from components.objective_editor import ObjectiveDraft, render_objective_editor

    draft = ObjectiveDraft("Aplicar", "modelos de clasificación", "")
    st.session_state["result"] = render_objective_editor(
        draft, key="e4b", topics_count=4, pass_threshold=80
    )


def test_objective_editor_disables_save_without_criterion() -> None:
    at = run(_objective)
    assert at.button(key="e4b-save").disabled
    assert "Con este objetivo tu ruta tiene 4 temas." in texts(at)
    assert any("El 80 % para obtener el badge" in t for t in texts(at))


def test_objective_editor_builds_the_preview_and_enables_save() -> None:
    at = run(_objective)
    at.text_input(key="e4b-criterion").set_value("evaluando su desempeño con F1").run()
    assert not at.button(key="e4b-save").disabled
    assert "Aplicar modelos de clasificación evaluando su desempeño con F1." in texts(at)
    at.button(key="e4b-save").click().run()
    result = at.session_state["result"]
    assert result.save
    assert result.draft.criterion == "evaluando su desempeño con F1"


# --- rubric_result -------------------------------------------------------------------------------


def _rubric() -> None:
    from components.rubric_result import CriterionView, RubricView, render_rubric_result

    render_rubric_result(
        RubricView(
            criteria=(
                CriterionView("Relaciona el umbral con el costo", True, "Menciona el fraude."),
                CriterionView("Nombra la sensibilidad", True, ""),
                CriterionView("Justifica con datos del caso", False, "No da la proporción."),
            ),
            criteria_met=2,
            criteria_total=3,
            min_met=2,
            is_correct=True,
            graded_by="IA",
        ),
        key="e7",
    )


def test_rubric_result_states_each_criterion_in_words() -> None:
    shown = texts(run(_rubric))
    assert "Puntaje: 2 de 3 criterios · calificado con IA según la rúbrica" in shown
    assert "Cuenta como correcta: cumple 2 de 3 criterios (mínimo 2)." in shown
    assert "Cumple · Relaciona el umbral con el costo" in shown
    assert "No cumple · Justifica con datos del caso" in shown


# --- attempt_history -----------------------------------------------------------------------------


def _history() -> None:
    from components.attempt_history import AttemptRow, render_attempt_history

    render_attempt_history(
        [
            AttemptRow(1, 60, 3, 5),
            AttemptRow(2, 60, 3, 5),
            AttemptRow(3, 40, 2, 5, extra_grant=True),
        ],
        key="e7c",
        pass_threshold=70,
        exhausted=True,
    )


def test_attempt_history_lists_attempts_and_flags_exhausted() -> None:
    at = run(_history)
    shown = texts(at)
    assert "Historial de intentos" in shown
    assert "Intento 1" in shown
    assert "60 % · 3 de 5" in shown
    assert "Intento 3 · intento extra" in shown
    assert "Necesitas 70 % para aprobar." in shown
    assert "Intentos agotados" in badges(at)


# --- topic_graph ---------------------------------------------------------------------------------


def test_topic_graph_dot_uses_tokens_and_escapes_text() -> None:
    from components.topic_graph import GraphEdge, GraphNode, build_dot
    from core.styles import token

    dot = build_dot(
        [
            GraphNode(1, 'Intro "ML"', "Bloom · Comprender"),
            GraphNode(2, "Regresión", "Bloom · Aplicar", state="corrected"),
            GraphNode(3, "Árboles", "Bloom · Aplicar", state="added"),
        ],
        [GraphEdge(1, 2), GraphEdge(2, 3)],
    )
    assert 'Intro \\"ML\\"' in dot
    assert "t1 -> t2;" in dot
    assert "Corregido" in dot
    assert "Agregado por ti" in dot
    assert "Sin cambios" in dot
    assert token("learner-soft") in dot  # el color sale de tokens.css


def _graph() -> None:
    from components.topic_graph import GraphEdge, GraphNode, render_topic_graph

    render_topic_graph(
        [GraphNode(1, "Intro", "Bloom · Comprender"), GraphNode(2, "Regresión", "Bloom · Aplicar")],
        [GraphEdge(1, 2)],
        validated=True,
    )


def test_topic_graph_renders_validation_status() -> None:
    at = run(_graph)
    assert any("Sin ciclos · validado" in text for text in badges(at))
    assert len(at.get("graphviz_chart")) == 1


# --- video_feedback ------------------------------------------------------------------------------


def _feedback() -> None:
    import streamlit as st

    from components.video_feedback import render_video_feedback

    st.session_state["result"] = render_video_feedback(key="e6")


def test_video_feedback_needs_a_rating_and_returns_the_comment() -> None:
    at = run(_feedback)
    shown = texts(at)
    assert "¿Te sirvió este video?" in shown
    assert "Tu instructor ve tu calificación y tu comentario sin tu nombre." in shown
    assert at.button(key="e6-submit").disabled
    at.get("button_group")[0].set_value("audio_issue").run()
    at.text_area(key="e6-comment").set_value("  Se corta a los 3 min  ").run()
    at.button(key="e6-submit").click().run()
    result = at.session_state["result"]
    assert (result.rating, result.comment, result.submit) == (
        "audio_issue",
        "Se corta a los 3 min",
        True,
    )


# --- annotation_form -----------------------------------------------------------------------------


def _annotation() -> None:
    import streamlit as st

    from components.annotation_form import AnnotationItemView, render_annotation_form

    item = AnnotationItemView(
        item_id=7,
        stem="Si no detectar un fraude es muy costoso, ¿qué harías con el umbral?",
        options=("Subirlo a 0,7", "Bajarlo a 0,3", "Dejarlo en 0,5", "Quitar variables"),
        correct_index=1,
        meta="Tema 3 · Regresión logística · Bloom: Aplicar",
    )
    st.session_state["result"] = render_annotation_form(
        item, evaluator_slot="Evaluador 1 de 2", progress="23 de 60 anotadas", key="d5b"
    )


def test_annotation_form_marks_the_correct_option_and_stays_blind() -> None:
    at = run(_annotation)
    shown = texts(at)
    assert "B. Bajarlo a 0,3  ← correcta" in shown or "B. Bajarlo a 0,3 ← correcta" in shown
    assert any("Anotación ciega: no ves la del otro evaluador" in t for t in shown)
    assert at.button(key="d5b-save").disabled


def test_annotation_form_saves_only_when_rubric_and_verdict_are_complete() -> None:
    at = run(_annotation)
    for code in ("single_correct", "clear_stem", "bloom_ok", "plausible_distractors"):
        at.session_state[f"d5b-7-{code}"] = "Sí"
    at.session_state["d5b-7-verdict"] = "Válida"
    at.run()
    assert not at.button(key="d5b-save").disabled
    at.button(key="d5b-save").click().run()
    result = at.session_state["result"]
    assert result.save
    assert result.verdict == "valid"
    assert all(result.criteria.values())


# --- likert_scale --------------------------------------------------------------------------------


def _likert() -> None:
    import streamlit as st

    from components.likert_scale import (
        EXPERIENCE_ITEMS,
        LikertQuestion,
        render_likert_block,
    )

    st.session_state["result"] = render_likert_block(
        "Tu experiencia",
        [LikertQuestion(code, text) for code, text in EXPERIENCE_ITEMS],
        key="e13a",
    )


def test_likert_block_returns_values_from_1_to_5() -> None:
    at = run(_likert)
    shown = texts(at)
    assert "1 = Totalmente en desacuerdo · 5 = Totalmente de acuerdo" in shown
    assert "Estoy satisfecho con la ruta que seguí." in shown
    assert at.session_state["result"] == {"q1": None, "q2": None, "q3": None}
    at.radio(key="likert-radio-e13a-q2").set_value(4).run()
    assert at.session_state["result"]["q2"] == 4


def test_sus_has_ten_items_in_two_halves() -> None:
    from components.likert_scale import SUS_ITEMS

    assert len(SUS_ITEMS) == 10
    assert SUS_ITEMS[0].startswith("Creo que me gustaría usar")
    assert SUS_ITEMS[5].startswith("Pensé que había demasiada inconsistencia")


# --- table · kpi_cards · levels · path_timeline · quiz_form · badge_card · video_player ----------


def _table() -> None:
    import streamlit as st

    from components.table import Actions, Row, render_table

    clicked = render_table(
        ["Usuario", "Rol", "Estado", ""],
        [3, 2, 2, 2],
        [
            Row(
                "1",
                [
                    "Laura",
                    ("Aprendiz", "blue"),
                    ("Activo", "green"),
                    Actions((("edit", "Editar"),)),
                ],
            )
        ],
        key="users",
    )
    st.session_state["clicked"] = clicked


def test_table_returns_row_and_action() -> None:
    at = run(_table)
    assert "**USUARIO**" in [e.value for e in at.caption]
    assert badges(at) >= {
        "Aprendiz",
        "Activo",
    }
    at.button(key="users-1-edit").click().run()
    assert at.session_state["clicked"] == ("1", "edit")


def _empty_table() -> None:
    from components.table import render_table

    render_table(["A"], [1], [], key="empty")


def test_empty_table_says_so() -> None:
    assert "No hay registros todavía." in [e.value for e in run(_empty_table).caption]


def _kpis() -> None:
    from components.kpi_cards import Kpi, render_kpis

    render_kpis([Kpi("done", "Temas dominados", "5 / 5"), Kpi("saved", "Ahorrados", "1 h 20 min")])


def test_kpi_cards_show_label_and_value() -> None:
    at = run(_kpis)
    assert [(m.label, m.value) for m in at.metric] == [
        ("Temas dominados", "5 / 5"),
        ("Ahorrados", "1 h 20 min"),
    ]


def _levels() -> None:
    from components.levels import LevelRow, render_levels

    render_levels(
        [
            LevelRow(1, "Introducción", 92, "mastered"),
            LevelRow(2, "Regresión lineal", 64, "to_reinforce"),
            LevelRow(3, "Regresión logística", 38, "to_learn"),
        ]
    )


def test_levels_write_the_state_next_to_the_percentage() -> None:
    at = run(_levels)
    markdown = [e.value for e in at.markdown]
    assert "**92 %**" in markdown
    shown = badges(at)
    assert shown == {
        "Dominado",
        "Por reforzar",
        "Por aprender",
    }


def _timeline() -> None:
    import streamlit as st

    from components.path_timeline import StepView, render_path_timeline

    st.session_state["opened"] = render_path_timeline(
        [
            StepView(811, 1, "Fundamentos", "skipped", "skipped_mastered", "Ya lo dominas", False),
            StepView(812, 2, "Regresión lineal", "pending", "weak_prerequisite", "90 min"),
        ]
    )


def test_path_timeline_shows_reason_status_and_opens_a_step() -> None:
    at = run(_timeline)
    captions = [e.value for e in at.caption]
    assert "Omitido: ya lo dominas · Ya lo dominas" in captions
    assert "Incluido: prerrequisito débil · 90 min" in captions
    assert len(at.button) == 1  # el paso omitido no se abre
    at.button(key="open-step-812").click().run()
    assert at.session_state["opened"] == 812


def _quiz() -> None:
    import streamlit as st

    from components.quiz_form import render_options

    st.session_state["choice"] = render_options(
        stem="¿Qué valores devuelve la sigmoide?",
        options=["Entre 0 y 1", "Entre -1 y 1"],
        key="q1",
        allow_dont_know=True,
    )


def test_quiz_options_include_dont_know() -> None:
    at = run(_quiz)
    assert at.radio[0].options == ["Entre 0 y 1", "Entre -1 y 1", "No lo sé"]
    assert at.session_state["choice"] is None
    at.radio[0].set_value("No lo sé").run()
    assert at.session_state["choice"] == -1
    at.radio[0].set_value("Entre -1 y 1").run()
    assert at.session_state["choice"] == 1


def _review() -> None:
    from components.quiz_form import render_answer_review

    render_answer_review(
        number=3, stem="¿Qué métrica?", correct=False, explanation="La sensibilidad."
    )


def test_answer_review_states_if_it_was_correct() -> None:
    at = run(_review)
    assert badges(at) == {"Incorrecta"}
    assert "**Pregunta 3** · ¿Qué métrica?" in [e.value for e in at.markdown]


def _badges() -> None:
    from components.badge_card import render_badge_hero, render_badge_slot

    render_badge_hero("¡Ruta completada!", "Obtuviste 88 % en la evaluación final.")
    render_badge_slot("Fundamentos de ML", "Obtenida el 7 nov 2026", obtained=True, key="a")
    render_badge_slot("Estadística", "Aprueba los 5 temas", obtained=False, key="b")


def test_badge_slots_say_obtained_or_locked() -> None:
    at = run(_badges)
    assert badges(at) == {
        "Obtenida",
        "Bloqueada",
    }
    assert at.header[0].value == "¡Ruta completada!"


def _video() -> None:
    from components.video_player import render_video

    render_video(title="Regresión logística explicada", duration_label="11 min")


def test_video_box_shows_title_and_duration_without_url() -> None:
    at = run(_video)
    assert any("11 min" in e.value for e in at.markdown)
    assert "Regresión logística explicada" in [e.value for e in at.caption]


def _role_card() -> None:
    from components.role_card import render_role_card

    render_role_card(
        role="admin",
        badge_label="Admin",
        title="Soy admin",
        description="Administra usuarios.",
        permissions="Cuentas creadas solo por otro admin",
        cta_label="Entrar como admin",
        key="admin",
    )


def test_role_card_has_an_enter_button() -> None:
    at = run(_role_card)
    assert at.button(key="enter-admin").label == "Entrar como admin"
    assert badges(at) == {"Admin"}
