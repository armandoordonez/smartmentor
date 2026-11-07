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


@dataclass(frozen=True)
class CatalogView:
    paths: list[PathCardView]
    applied_ai: list[PathCardView]

    @property
    def is_empty(self) -> bool:
        return not self.paths and not self.applied_ai


def card_view(card: LearningPathCard) -> PathCardView:
    meta = f"{card.topics_count} temas · {approx_duration(card.estimated_minutes)} · "
    meta += PATH_LEVEL_LABEL[card.level]
    tag = PATH_TAG_TEXT[card.tags[0]] if card.tags else None
    return PathCardView(
        path_id=card.id,
        name=card.name,
        meta=meta,
        tag_text=tag,
        description=card.description,
    )


def load_catalog(client: SmartMentorClient) -> CatalogView:
    page = client.list_learning_paths(limit=100)
    paths = [card_view(c) for c in page.items if c.section == "paths"]
    applied = [card_view(c) for c in page.items if c.section == "applied_ai"]
    return CatalogView(paths=paths, applied_ai=applied)


def open_path(client: SmartMentorClient, learning_path_id: int) -> Enrollment:
    """Inscribe a la persona en la ruta o, si ya estaba inscrita, devuelve su inscripción."""
    try:
        return client.create_enrollment(learning_path_id)
    except ApiError as error:
        if error.code != "ENROLLMENT_ALREADY_EXISTS":
            raise
    page = client.list_enrollments(limit=100)
    for enrollment in page.items:
        if enrollment.learning_path.id == learning_path_id:
            return enrollment
    raise ApiError(404, "ENROLLMENT_NOT_FOUND", "existing enrollment not found")
