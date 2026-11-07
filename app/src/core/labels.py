"""Glosario de etiquetas por perfil de contexto (ADR 0021, sección 13.3 del plan).

Solo cambia el **texto visible**: los códigos de rol (`learner`, `instructor`, `admin`), las tablas,
las rutas de la API y los identificadores no cambian con el perfil. `generic` es P0 y el valor por
omisión; `academic` y `corporate` son una mejora P2 con etiquetas propuestas por el glosario de
diseño, pendientes de validar con el dueño (DEF-23 y DEF-24).

`GET /me` devuelve `role_labels` y `role_short_labels` ya resueltos por la API: la interfaz los usa
cuando existen y cae en este glosario cuando no (modo `fixtures` o roles sin etiqueta).
"""

from dataclasses import dataclass

from clients.models import Role
from core.config import ContextProfile, get_settings


@dataclass(frozen=True)
class Glossary:
    role: dict[Role, str]
    """Etiqueta larga del rol («Administrador»)."""
    role_short: dict[Role, str]
    """Etiqueta del menú superior («Admin»)."""
    evaluator: str
    group: str
    syllabus: str


GLOSSARIES: dict[ContextProfile, Glossary] = {
    "generic": Glossary(
        role={"learner": "Aprendiz", "instructor": "Instructor", "admin": "Administrador"},
        role_short={"learner": "Aprendiz", "instructor": "Instructor", "admin": "Admin"},
        evaluator="Evaluador",
        group="Grupo",
        syllabus="Contenido del curso",
    ),
    "academic": Glossary(
        role={"learner": "Estudiante", "instructor": "Docente", "admin": "Administrador"},
        role_short={"learner": "Estudiante", "instructor": "Docente", "admin": "Admin"},
        evaluator="Evaluador",
        group="Cohorte",
        syllabus="Syllabus",
    ),
    "corporate": Glossary(
        role={"learner": "Colaborador", "instructor": "Capacitador", "admin": "Administrador"},
        role_short={"learner": "Colaborador", "instructor": "Capacitador", "admin": "Admin"},
        evaluator="Evaluador",
        group="Equipo",
        syllabus="Programa de formación",
    ),
}


def glossary(profile: ContextProfile | None = None) -> Glossary:
    """Glosario del perfil pedido o, por omisión, el de `APP_CONTEXT_PROFILE`."""
    return GLOSSARIES[profile or get_settings().app_context_profile]


def role_label(
    role: Role,
    *,
    short: bool = False,
    api_labels: dict[Role, str] | None = None,
) -> str:
    """Etiqueta visible de un rol: la de la API si llegó, y si no, la del glosario."""
    if api_labels and role in api_labels:
        return api_labels[role]
    entries = glossary().role_short if short else glossary().role
    return entries[role]
