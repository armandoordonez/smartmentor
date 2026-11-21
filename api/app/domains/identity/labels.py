"""Glosario de etiquetas visibles de los roles (sección 13.3 del plan, ADR 0021).

Solo cambia el texto que ve la persona: los códigos de rol, las tablas y las rutas no dependen del
perfil de contexto (`APP_CONTEXT_PROFILE`). Solo `generic` es P0; los otros dos son P2 y están aquí
porque cuestan una entrada de diccionario.
"""

from app.common.constants import RoleCode

_LABELS: dict[str, dict[str, str]] = {
    "generic": {
        RoleCode.LEARNER: "Aprendiz",
        RoleCode.INSTRUCTOR: "Instructor",
        RoleCode.ADMIN: "Administrador",
    },
    "academic": {
        RoleCode.LEARNER: "Estudiante",
        RoleCode.INSTRUCTOR: "Docente",
        RoleCode.ADMIN: "Administrador",
    },
    "corporate": {
        RoleCode.LEARNER: "Colaborador",
        RoleCode.INSTRUCTOR: "Capacitador",
        RoleCode.ADMIN: "Administrador",
    },
}

# Etiqueta corta del menú superior: Figma v3 muestra «Admin».
_SHORT_OVERRIDES = {RoleCode.ADMIN.value: "Admin"}


def role_labels(profile: str) -> dict[str, str]:
    """Etiqueta larga de los tres roles. Un perfil desconocido cae en `generic`."""
    labels = _LABELS.get(profile, _LABELS["generic"])
    return {code.value: labels[code] for code in RoleCode}


def role_short_labels(profile: str) -> dict[str, str]:
    return {**role_labels(profile), **_SHORT_OVERRIDES}
