"""Reglas de arquitectura de `app/CLAUDE.md`, verificadas sobre el código fuente."""

import ast
import re
from pathlib import Path

from support import SRC_DIR

from clients.models import ROLES
from core import navigation

COMPONENTS = sorted((SRC_DIR / "components").glob("*.py"))
FORBIDDEN_IN_COMPONENTS = ("session_state", "get_session", "unsafe_allow_html")
FORBIDDEN_MODULES = (
    "clients.api",
    "clients.fixtures",
    "clients.base",
    "services",
    "core.container",
)
OLD_VOCABULARY = re.compile(r"\b(student|teacher|estudiante|docente)s?\b", re.IGNORECASE)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_there_are_components() -> None:
    assert {p.stem for p in COMPONENTS} >= {
        "loading_steps", "consent_form", "resume_form", "objective_editor", "rubric_result",
        "attempt_history", "topic_graph", "video_feedback", "annotation_form", "likert_scale",
        "table", "kpi_cards", "badge_card", "course_card", "path_timeline", "quiz_form", "levels",
    }  # fmt: skip


def _attributes_and_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.keyword) and node.arg:
            found.add(node.arg)
    return found


def test_components_do_not_touch_session_or_html() -> None:
    for path in COMPONENTS:
        used = _attributes_and_names(path)
        for forbidden in FORBIDDEN_IN_COMPONENTS:
            assert forbidden not in used, f"{path.name} usa {forbidden}"


def test_components_do_not_import_clients_or_services() -> None:
    for path in COMPONENTS:
        for module in _imports(path):
            assert not module.startswith(FORBIDDEN_MODULES), f"{path.name} importa {module}"


def test_services_and_clients_do_not_draw_widgets() -> None:
    for folder in ("services", "clients"):
        for path in (SRC_DIR / folder).glob("*.py"):
            if folder == "clients" and path.name == "fixtures.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    assert node.value.id != "st", f"{path.name} usa st.{node.attr}"


def test_pages_do_not_call_the_api_client_directly() -> None:
    for path in (SRC_DIR / "pages").rglob("*.py"):
        for module in _imports(path):
            assert module not in {"clients.api", "clients.fixtures"} or path.name == (
                "demo_role_selector.py"
            ), f"{path.name} importa {module}"
        assert "httpx" not in path.read_text(encoding="utf-8")


def test_no_old_role_vocabulary_in_code() -> None:
    """Sección 13 del plan: `learner`, `instructor`, `admin`; nunca `student` ni `teacher`."""
    for path in SRC_DIR.rglob("*.py"):
        if path.name == "labels.py":  # los perfiles `academic` y `corporate` rotulan «Estudiante»
            continue
        text = path.read_text(encoding="utf-8")
        assert not OLD_VOCABULARY.search(text), path.relative_to(SRC_DIR)


def test_pages_are_in_role_folders() -> None:
    folders = {p.name for p in (SRC_DIR / "pages").iterdir() if p.is_dir()}
    assert folders <= {"common", "learner", "instructor", "admin"}


def test_every_navigation_target_is_a_planned_page_and_existing_pages_are_planned() -> None:
    planned = {spec.path for spec in navigation.PAGES}
    for path in SRC_DIR.glob("pages/*/*.py"):
        assert path.relative_to(SRC_DIR).as_posix() in planned, f"{path.name} no está en PAGES"
    for path in navigation.SCREEN_PAGES.values():
        assert path in planned


def test_page_paths_and_urls_are_unique() -> None:
    paths = [spec.path for spec in navigation.PAGES]
    urls = [spec.url_path for spec in navigation.PAGES]
    assert len(set(paths)) == len(paths)
    assert len(set(urls)) == len(urls)


def test_menu_roles_are_valid_and_home_exists_for_every_role() -> None:
    for spec in navigation.PAGES:
        assert spec.menu_role is None or spec.menu_role in ROLES
    for role in ROLES:
        assert (SRC_DIR / navigation.home_for(role)).is_file()


def test_learner_menu_lists_only_pages_that_exist() -> None:
    links = navigation.menu_links("learner")
    assert ("pages/learner/catalog.py", "Rutas") in links
    assert ("pages/learner/my_profile.py", "Mi perfil") in links
    for path, _ in links:
        assert (SRC_DIR / path).is_file()
