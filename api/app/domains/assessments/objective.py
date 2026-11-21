"""Verbos de Bloom permitidos en el objetivo personal (E4, E4b; B-033).

La lista son los seis niveles de la taxonomía revisada (Anderson y Krathwohl) más los verbos de
acción habituales de cada nivel. Incluye los que la IA propone con más frecuencia («Construir»,
«Implementar», «Diseñar»), porque son verbos de Bloom válidos y no tiene sentido rechazar la
propuesta de la IA cuando el aprendiz la confirma sin cambios. La app ofrece la misma lista en
`app/src/components/theme.py` (`BLOOM_ACTION_VERBS`) y el contrato la documenta en
`docs/contracts/api-v2.md`.

La comparación ignora mayúsculas y tildes; lo que se guarda es la forma canónica de la lista.
"""

import unicodedata

from app.common.constants import BloomLevel
from app.domains.learning_paths.entities import Enrollment

BLOOM_VERBS_BY_LEVEL: dict[BloomLevel, tuple[str, ...]] = {
    BloomLevel.REMEMBER: (
        "Recordar",
        "Identificar",
        "Reconocer",
        "Definir",
        "Enumerar",
        "Listar",
        "Nombrar",
    ),
    BloomLevel.UNDERSTAND: (
        "Comprender",
        "Explicar",
        "Describir",
        "Interpretar",
        "Resumir",
        "Clasificar",
        "Ejemplificar",
    ),
    BloomLevel.APPLY: (
        "Aplicar",
        "Implementar",
        "Ejecutar",
        "Usar",
        "Utilizar",
        "Resolver",
        "Calcular",
        "Demostrar",
    ),
    BloomLevel.ANALYZE: (
        "Analizar",
        "Comparar",
        "Contrastar",
        "Diferenciar",
        "Distinguir",
        "Examinar",
        "Organizar",
    ),
    BloomLevel.EVALUATE: (
        "Evaluar",
        "Justificar",
        "Valorar",
        "Juzgar",
        "Criticar",
        "Argumentar",
        "Verificar",
    ),
    BloomLevel.CREATE: (
        "Crear",
        "Diseñar",
        "Construir",
        "Desarrollar",
        "Formular",
        "Planificar",
        "Proponer",
        "Producir",
        "Generar",
    ),
}

ALLOWED_BLOOM_VERBS: tuple[str, ...] = tuple(
    verb for verbs in BLOOM_VERBS_BY_LEVEL.values() for verb in verbs
)


def _key(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.strip().casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


_CANONICAL: dict[str, str] = {_key(verb): verb for verb in ALLOWED_BLOOM_VERBS}


def canonical_bloom_verb(text: str) -> str | None:
    """La forma canónica del verbo («aplicar» → «Aplicar») o `None` si no está en la lista."""
    return _CANONICAL.get(_key(text))


def normalize_proposal(bloom_verb: str, content: str) -> tuple[str, str]:
    """Ajusta el verbo que propone la IA a la lista sin cambiar el enunciado.

    - Un verbo de la lista se guarda en su forma canónica.
    - Un verbo compuesto («Construir y evaluar») conserva el primero, si está en la lista, y el
      resto pasa al inicio del contenido («y evaluar un modelo…»): el enunciado queda igual.
    - Si el primer verbo no está en la lista, la propuesta queda como vino; al confirmarla sin
      cambios la API la acepta porque es la propuesta guardada (ver `confirm_objective`).
    """
    verb = bloom_verb.strip()
    exact = canonical_bloom_verb(verb)
    if exact is not None:
        return exact, content
    first, _, rest = verb.partition(" ")
    leading = canonical_bloom_verb(first)
    if leading is None:
        return verb, content
    return leading, f"{rest.strip()} {content}".strip()


def objective_proposal(enrollment: Enrollment) -> dict[str, str] | None:
    """La propuesta guardada (`bloom_verb`, `content`, `criterion`, `origin`) o `None`.

    Las inscripciones anteriores al changeset `v2.0.1-006` sin propuesta guardada usan el objetivo
    actual mientras no lo haya editado el aprendiz; si lo editó, la propuesta original se perdió.
    """
    stored = (
        enrollment.objective_proposal_bloom_verb,
        enrollment.objective_proposal_content,
        enrollment.objective_proposal_criterion,
        enrollment.objective_proposal_origin,
    )
    if not all(stored[:3]) and enrollment.objective_origin != "learner_edited":
        stored = (
            enrollment.objective_bloom_verb,
            enrollment.objective_content,
            enrollment.objective_criterion,
            enrollment.objective_origin,
        )
    verb, content, criterion, origin = stored
    if not (verb and content and criterion):
        return None
    return {
        "bloom_verb": verb,
        "content": content,
        "criterion": criterion,
        "origin": origin or "llm_proposed",
    }
