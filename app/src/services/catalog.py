"""Catálogo de rutas (E1): arma lo que muestra la pantalla a partir de `GET /learning-paths`.

Sin reglas de negocio: solo agrupa las tarjetas en sus dos secciones y arma el texto de cada una.
No usa caché compartida: la etiqueta «Recomendada para ti» es personal.
"""

from dataclasses import dataclass

from clients.base import ApiError, SmartMentorClient
from clients.models import Enrollment, LearningPathCard
from components.course_card import PathCardView
from components.formatting import approx_duration
from components.theme import PATH_LEVEL_LABEL, PATH_TAG_TEXT

OPEN_LABEL = "Ver ruta"
CONTINUE_LABEL = "Continuar ruta"


@dataclass(frozen=True)
class CatalogView:
    paths: list[PathCardView]
    applied_ai: list[PathCardView]
    # Rutas en las que la persona ya está inscrita (`enrolled` del catálogo).
    enrolled_path_ids: frozenset[int] = frozenset()

    @property
    def is_empty(self) -> bool:
        return not self.paths and not self.applied_ai


def card_view(card: LearningPathCard) -> PathCardView:
    """«3 temas · ~8 h · Intermedio». La duración y el nivel se omiten si la API no los da."""
    parts = [f"{card.topic_count} {'tema' if card.topic_count == 1 else 'temas'}"]
    if card.estimated_minutes > 0:
        parts.append(approx_duration(card.estimated_minutes))
    if card.level is not None:
        parts.append(PATH_LEVEL_LABEL[card.level])
    tag = PATH_TAG_TEXT[card.tags[0]] if card.tags else None
    return PathCardView(
        path_id=card.id,
        name=card.name,
        meta=" · ".join(parts),
        tag_text=tag,
        description=card.course.description,
        cta_label=CONTINUE_LABEL if card.enrolled else OPEN_LABEL,
    )


def load_catalog(client: SmartMentorClient) -> CatalogView:
    page = client.list_learning_paths(limit=100)
    paths = [card_view(c) for c in page.items if c.section == "paths"]
    applied = [card_view(c) for c in page.items if c.section == "applied_ai"]
    enrolled = frozenset(c.id for c in page.items if c.enrolled)
    return CatalogView(paths=paths, applied_ai=applied, enrolled_path_ids=enrolled)


def open_path(
    client: SmartMentorClient, learning_path_id: int, *, enrolled: bool = False
) -> Enrollment:
    """Inscribe a la persona en la ruta o, si ya estaba inscrita, devuelve su inscripción.

    Con `enrolled` (el catálogo ya sabe que existe) no se manda el `POST`, que respondería 409.
    """
    if not enrolled:
        try:
            return client.create_enrollment(learning_path_id)
        except ApiError as error:
            if error.code != "ENROLLMENT_ALREADY_EXISTS":
                raise
    page = client.list_enrollments(limit=100)
    for enrollment in page.items:
        if enrollment.learning_path.id == learning_path_id:
            return enrollment
    if enrolled:
        # El catálogo estaba desactualizado: se intenta inscribir de verdad.
        return open_path(client, learning_path_id)
    raise ApiError(404, "ENROLLMENT_NOT_FOUND", "existing enrollment not found")
