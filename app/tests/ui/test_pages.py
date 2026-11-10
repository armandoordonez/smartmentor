"""Páginas de esta parte con `AppTest` sobre el modo `fixtures`.

Cada pantalla con frame en Figma v3 se compara con `estructura-pantallas.json`: sus textos tienen
que aparecer en la página, en el mismo orden. Las diferencias aceptadas se declaran aquí.
"""

from typing import Any

import pytest
from apptest import button, header_texts, new_app, page_texts, session_of, signed_in
from figma_compare import figma_texts, missing_in_order
from streamlit.testing.v1 import AppTest

from clients.base import ApiError

CATALOG = "pages/learner/catalog.py"
PROFILE = "pages/learner/onboarding_profile.py"
RESUME = "pages/learner/onboarding_resume.py"
MY_PROFILE = "pages/learner/my_profile.py"
RIGHTS = "pages/common/data_rights.py"
CONSENT = "pages/common/consent.py"


def assert_no_exception(at: AppTest) -> None:
    assert [e.value for e in at.exception] == []


def assert_matches_figma(
    at: AppTest, screen: str, *, accepted: tuple[str, ...] = (), skip_brand: bool = False
) -> None:
    """Todos los textos del frame aparecen en orden, salvo los aceptados (con su motivo)."""
    assert_no_exception(at)
    missing = missing_in_order(figma_texts(screen, skip_brand=skip_brand), page_texts(at))
    assert missing == list(accepted), f"{screen}: faltan o desordenados {missing}"


# --- A1 · Selector de rol (solo fixtures) ------------------------------------------------------


def test_a1_role_selector_is_the_first_screen_without_a_session() -> None:
    at = new_app().run()
    assert_no_exception(at)
    texts = page_texts(at, skip_header=False)
    assert "¿Cómo quieres entrar?" in texts
    for expected in ("Soy aprendiz", "Soy instructor", "Soy admin"):
        assert expected in texts
    assert [b.label for b in at.button][:3] == [
        "Entrar como aprendiz",
        "Entrar como instructor",
        "Entrar como admin",
    ]
    # No hay botones «(Demo del prototipo)»: los reemplazan los escenarios de datos.
    assert not [b for b in at.button if "Demo" in b.label]


def test_a1_texts_follow_figma() -> None:
    at = new_app().run()
    texts = page_texts(at, skip_header=False)
    # Sin la marca previa al título y con el aviso de Ley 1581 al final.
    missing = missing_in_order(figma_texts("A1"), texts)
    # «Demo: acceso a una página sin permiso (403)» es un botón de demostración que no se construye.
    assert missing == ["Demo: acceso a una página sin permiso (403)"]


def test_a1_entering_as_learner_opens_the_catalog() -> None:
    at = new_app().run()
    button(at, "Entrar como aprendiz").click().run()
    assert_no_exception(at)
    assert session_of(at).active_role == "learner"
    assert "Rutas" in page_texts(at)


def test_a1_scenarios_cover_first_login() -> None:
    at = new_app().run()
    at.button(key="scenario-learner_new").click().run()
    assert_no_exception(at)
    assert session_of(at).me is not None
    assert session_of(at).me.requires_consent  # type: ignore[union-attr]


# --- Barra superior, menú por rol y cambio de perfil (CU-35) -----------------------------------


def test_learner_header_has_role_badge_and_menu_links() -> None:
    at = signed_in("learner")
    texts = header_texts(at)
    assert "SmartMentor" in texts
    assert "Aprendiz" in texts
    assert {"Rutas", "Mi perfil"} <= set(texts)
    assert "Cerrar sesión" in texts
    # Un solo rol: el menú de la cuenta no ofrece cambiar de perfil.
    assert not [b for b in at.button if b.key and b.key.startswith("switch-role-")]


def test_multi_role_user_switches_profile_from_the_account_menu() -> None:
    at = signed_in("instructor")
    assert session_of(at).active_role == "instructor"
    assert "Instructor" in header_texts(at)
    switch = at.button(key="switch-role-learner")
    assert switch.label == "Aprendiz"
    switch.click().run()
    assert_no_exception(at)
    assert session_of(at).active_role == "learner"
    assert "Aprendiz" in header_texts(at)
    assert "Rutas" in page_texts(at)
    # La API autoriza por la unión de roles: el cambio no toca al usuario.
    assert session_of(at).me.roles == ["instructor", "learner"]  # type: ignore[union-attr]


def test_admin_can_switch_to_the_other_two_profiles() -> None:
    at = signed_in("admin")
    keys = {b.key for b in at.button if b.key and b.key.startswith("switch-role-")}
    assert keys == {"switch-role-instructor", "switch-role-learner"}


def test_roles_without_built_pages_land_on_coming_soon() -> None:
    at = signed_in("instructor")
    assert_no_exception(at)
    assert "Próximamente" in page_texts(at)


def test_logout_returns_to_the_role_selector() -> None:
    at = signed_in("learner")
    at.button(key="logout").click().run()
    assert_no_exception(at)
    assert session_of(at).me is None
    assert "¿Cómo quieres entrar?" in page_texts(at, skip_header=False)


def test_styles_are_injected_once_per_run_with_the_role_container() -> None:
    at = signed_in("learner")
    htmls = list(at.get("html"))
    assert len(htmls) == 1
    assert "--learner-accent" in htmls[0].proto.body
    assert "/* roles.css */" in htmls[0].proto.body


# --- A6 · 403 y A7 · Sesión expirada -----------------------------------------------------------


def _fail_profile(at: AppTest, error: ApiError) -> None:
    client = session_of(at).fixtures_client
    assert client is not None

    def boom() -> Any:
        raise error

    client.get_profile = boom  # type: ignore[method-assign]


def test_a6_forbidden_screen() -> None:
    at = signed_in("learner")
    _fail_profile(at, ApiError(403, "INSUFFICIENT_ROLE"))
    at.switch_page(MY_PROFILE).run()
    assert_no_exception(at)
    texts = page_texts(at, skip_header=False)
    assert "403" in texts
    assert "No tienes permiso para ver esta página" in texts
    assert any("Tu rol (Aprendiz) no puede acceder a «Mi perfil»" in t for t in texts)
    assert [b.label for b in at.button if b.key and b.key.startswith("status-")] == [
        "Volver a mi inicio",
        "Cambiar de cuenta",
    ]
    # Figma A6: marca, 403, título y botones en orden. Diferencia aceptada: el texto nombra la
    # página real en lugar de «Panel de instructor».
    missing = missing_in_order(figma_texts("A6"), texts)
    assert len(missing) == 1
    assert missing[0].startswith("Tu rol (Aprendiz) no puede acceder al Panel de instructor")


def test_a6_back_home_goes_to_the_role_home() -> None:
    at = signed_in("learner")
    _fail_profile(at, ApiError(403, "INSUFFICIENT_ROLE"))
    at.switch_page(MY_PROFILE).run()
    at.button(key="status-primary").click().run()
    assert_no_exception(at)
    assert "Rutas" in page_texts(at)


def test_a7_session_expired_screen_and_new_login() -> None:
    at = signed_in("learner")
    _fail_profile(at, ApiError(401, "TOKEN_EXPIRED"))
    at.switch_page(MY_PROFILE).run()
    assert_no_exception(at)
    texts = page_texts(at, skip_header=False)
    assert "Tu sesión expiró" in texts
    # Figma A7: título, explicación de los 30 minutos y botones.
    assert any("30 minutos sin actividad" in t for t in texts)
    assert [b.label for b in at.button if b.key and b.key.startswith("status-")] == [
        "Iniciar sesión",
        "Cambiar de cuenta",
    ]
    at.button(key="status-primary").click().run()
    assert session_of(at).me is None  # vuelve al selector: en `api` redirigiría al login


def test_action_errors_that_are_not_global_stay_inside_the_screen() -> None:
    at = signed_in("learner")
    _fail_profile(at, ApiError(404, "NOT_FOUND"))
    at.switch_page(MY_PROFILE).run()
    assert_no_exception(at)
    assert at.error
    assert "No encontramos lo que buscas." in at.error[0].value


# --- A3 · A3b · A3c: primer ingreso y consentimiento -------------------------------------------


def test_first_login_only_shows_the_consent_screens() -> None:
    at = signed_in("learner_new")
    assert_no_exception(at)
    texts = page_texts(at)
    assert "Tus autorizaciones" in texts
    header = header_texts(at)
    assert "Rutas" not in header  # sin menú hasta aceptar
    assert button(at, "Continuar").disabled


def test_a3_data_consent_is_required_to_continue() -> None:
    at = signed_in("learner_new")
    assert at.button(key="consent-terms-submit").disabled
    at.checkbox(key="consent-terms-data").check().run()
    assert not at.button(key="consent-terms-submit").disabled
    assert at.checkbox(key="consent-terms-pilot").value is False  # el piloto es opcional


def test_a3_accepting_enters_the_platform() -> None:
    at = signed_in("learner_new")
    at.checkbox(key="consent-terms-data").check().run()
    at.button(key="consent-terms-submit").click().run()
    assert_no_exception(at)
    me = session_of(at).me
    assert me is not None
    assert not me.requires_consent
    assert not me.consent_status.pilot_research.granted
    assert "Rutas" in page_texts(at)
    assert "Rutas" in header_texts(at)


def test_a3_accepting_with_pilot_records_both_consents() -> None:
    at = signed_in("learner_new")
    at.checkbox(key="consent-terms-data").check()
    at.checkbox(key="consent-terms-pilot").check().run()
    at.button(key="consent-terms-submit").click().run()
    me = session_of(at).me
    assert me is not None
    assert me.consent_status.pilot_research.granted


def test_a3b_informed_consent_follows_figma() -> None:
    at = signed_in("learner_new")
    at.button(key="consent-terms-read").click().run()
    assert_no_exception(at)
    # Diferencia aceptada: el texto sobre la fecha del piloto sale de PILOT_WINDOW_TEXT (C-03).
    assert_matches_figma(at, "A3b", skip_brand=True)
    assert [b.label for b in at.button][1:3] == ["Volver", "Continuar"]


def test_a3b_decision_travels_back_to_the_checkbox() -> None:
    at = signed_in("learner_new")
    at.button(key="consent-terms-read").click().run()
    at.radio(key="consent-informed-decision").set_value(
        "Acepto participar en el piloto y el uso anónimo de mis datos"
    ).run()
    at.button(key="consent-informed-continue").click().run()
    assert_no_exception(at)
    assert "Tus autorizaciones" in page_texts(at)
    assert at.checkbox(key="consent-terms-pilot").value is True


def test_a3b_back_button_returns_without_changing_the_choice() -> None:
    at = signed_in("learner_new")
    at.button(key="consent-terms-read").click().run()
    at.button(key="consent-informed-back").click().run()
    assert "Tus autorizaciones" in page_texts(at)
    assert at.checkbox(key="consent-terms-pilot").value is False


def test_a3c_rights_follow_figma_and_use_the_organization_name() -> None:
    at = signed_in("learner_new")
    at.button(key="consent-terms-read").click().run()
    at.button(key="consent-informed-rights").click().run()
    assert_no_exception(at)
    texts = page_texts(at)
    assert "Tus datos y tus derechos" in texts
    assert any("La organización responsable es la responsable" in t for t in texts)
    # Figma dice «la universidad»; el texto usa ORGANIZATION_NAME (ADR 0021): diferencia aceptada.
    missing = missing_in_order(figma_texts("A3c", skip_brand=True), texts)
    assert all("universidad" in text for text in missing)
    assert len(missing) <= 2


def test_a3c_back_button_returns_to_consent() -> None:
    at = signed_in("learner_new")
    at.switch_page(RIGHTS).run()
    at.button(key="back-to-consent").click().run()
    assert_no_exception(at)
    assert "Tus autorizaciones" in page_texts(at)


def test_consent_page_for_someone_who_already_accepted_is_a_summary() -> None:
    at = signed_in("learner")
    at.switch_page(CONSENT).run()
    assert_no_exception(at)
    assert "Ya aceptaste el tratamiento de tus datos." in [s.value for s in at.success]


# --- E1 · Catálogo -----------------------------------------------------------------------------


def test_e1_catalog_follows_figma() -> None:
    at = signed_in("learner")
    assert_matches_figma(at, "E1")


def test_e1_has_six_open_buttons_and_no_more_than_three_columns_per_row() -> None:
    at = signed_in("learner")
    assert len([b for b in at.button if b.label == "Ver ruta"]) == 6
    rows = list(at.columns)
    assert len(rows) == 6  # dos filas de tres columnas


def test_e1_open_path_enrolls_and_follows_next_action_to_profile() -> None:
    at = signed_in("learner")
    at.button(key="open-path-1").click().run()
    assert_no_exception(at)
    session = session_of(at)
    assert session.selected_path_id == 1
    assert session.selected_enrollment_id == 101
    assert "Cuéntanos sobre ti" in page_texts(at)


def test_e1_open_path_with_existing_enrollment_does_not_duplicate_it() -> None:
    at = signed_in("learner_in_path")
    at.button(key="open-path-1").click().run()
    assert_no_exception(at)
    assert session_of(at).selected_enrollment_id == 7
    # El `next_action` (E6) ya tiene página (F07b): la interfaz navega al tema.
    assert "QUIZ DEL TEMA" in page_texts(at)


def test_e1_has_tags_as_eyebrows() -> None:
    at = signed_in("learner")
    texts = page_texts(at)
    for tag in ("RECOMENDADA PARA TI", "NUEVA", "POPULAR", "NUEVO · ANTHROPIC", "NUEVO · GOOGLE"):
        assert tag in texts


def test_e1_api_error_is_shown_without_technical_detail() -> None:
    at = signed_in("learner")
    client = session_of(at).fixtures_client
    assert client is not None

    def boom(**_: Any) -> Any:
        raise ApiError(500, "INTERNAL_ERROR", "Traceback: boom")

    client.list_learning_paths = boom  # type: ignore[method-assign]
    at.switch_page(CATALOG).run()
    assert_no_exception(at)
    assert "Traceback" not in at.error[0].value


# --- E2 · Perfil -------------------------------------------------------------------------------


def test_e2_profile_follows_figma() -> None:
    at = signed_in("learner", page=PROFILE)
    assert_matches_figma(at, "E2")


def test_e2_continue_is_disabled_without_description() -> None:
    at = signed_in("learner", page=PROFILE)
    assert not at.button(key="profile-next").disabled
    at.text_area(key="profile-description").set_value("  ").run()
    assert at.button(key="profile-next").disabled
    at.text_area(key="profile-description").set_value("Soy analista.").run()
    assert not at.button(key="profile-next").disabled


def test_e2_continue_saves_the_description_and_opens_the_resume() -> None:
    at = signed_in("learner", page=PROFILE)
    at.text_area(key="profile-description").set_value("Nueva descripción de prueba.").run()
    at.button(key="profile-next").click().run()
    assert_no_exception(at)
    assert session_of(at).fixtures_client.get_profile().description == (  # type: ignore[union-attr]
        "Nueva descripción de prueba."
    )
    assert "Tu hoja de vida" in page_texts(at)


def test_e2_back_returns_to_the_catalog() -> None:
    at = signed_in("learner", page=PROFILE)
    at.button(key="profile-back").click().run()
    assert "Rutas" in page_texts(at)


# --- E2b · Hoja de vida ------------------------------------------------------------------------


def test_e2b_resume_follows_figma() -> None:
    at = signed_in("learner", page=RESUME)
    assert_matches_figma(at, "E2b")


def test_e2b_save_stores_the_resume_and_keeps_the_description() -> None:
    at = signed_in("learner", page=RESUME)
    at.text_input(key="resume-job").set_value("Líder de datos").run()
    at.get("button_group")[0].set_value(["Excel", "R"]).run()
    button(at, "Guardar y continuar").click().run()
    assert_no_exception(at)
    profile = session_of(at).fixtures_client.get_profile()  # type: ignore[union-attr]
    assert profile.job_title == "Líder de datos"
    assert profile.tools == ["Excel", "R"]
    assert profile.description and profile.description.startswith("Soy ingeniera industrial")
    assert [s.value for s in at.success] == ["Listo: tu perfil quedó guardado."]


def test_e2b_later_does_not_save() -> None:
    at = signed_in("learner", page=RESUME)
    at.text_input(key="resume-job").set_value("Otro cargo").run()
    button(at, "Completar más tarde").click().run()
    assert_no_exception(at)
    profile = session_of(at).fixtures_client.get_profile()  # type: ignore[union-attr]
    assert profile.job_title == "Analista de datos"


def test_e2b_adds_a_custom_tool_through_the_popover() -> None:
    at = signed_in("learner", page=RESUME)
    at.text_input(key="resume-new-tool").set_value("Looker").run()
    at.button(key="resume-add-tool").click().run()
    assert_no_exception(at)
    assert session_of(at).extra_tools == ["Looker"]
    assert "Looker" in at.get("button_group")[0].options


def test_e2b_shows_the_level_weights() -> None:
    at = signed_in("learner", page=RESUME)
    texts = page_texts(at)
    for expected in ("Evaluación diagnóstica", "80 %", "Hoja de vida", "10 %"):
        assert expected in texts


# --- E15 · Mi perfil ---------------------------------------------------------------------------


def test_e15_my_profile_follows_figma() -> None:
    at = signed_in("learner", page=MY_PROFILE)
    assert_matches_figma(at, "E15")


def test_e15_save_updates_description_and_resume_together() -> None:
    at = signed_in("learner", page=MY_PROFILE)
    at.text_area(key="profile-description").set_value("Descripción actualizada.").run()
    at.text_input(key="my-profile-title").set_value("Ingeniería de sistemas").run()
    at.button(key="my-profile-save").click().run()
    assert_no_exception(at)
    profile = session_of(at).fixtures_client.get_profile()  # type: ignore[union-attr]
    assert profile.description == "Descripción actualizada."
    assert profile.qualification_title == "Ingeniería de sistemas"
    assert [s.value for s in at.success] == ["Guardamos tu perfil."]


def test_e15_menu_links_to_my_profile() -> None:
    at = signed_in("learner")
    assert "Mi perfil" in header_texts(at)


@pytest.mark.parametrize("scenario", ["learner", "learner_in_path"])
def test_learner_scenarios_open_without_exceptions(scenario: str) -> None:
    for page in (CATALOG, PROFILE, RESUME, MY_PROFILE, RIGHTS):
        at = signed_in(scenario, page=page)
        assert_no_exception(at)
