"""AD5: el listado de inscripciones lee nombre y consentimiento en lote, no por fila (B-056).

Antes de B-056, `GET /enrollments` hacía dos consultas (usuario y consentimiento) por cada
inscripción de la página y, contra Neon (~1 s por consulta), AD5 superaba el límite de 10 s de la
app. Aquí se cuentan solo las sentencias sobre `users` y `consents`: son las que el lote reemplaza y
no deben crecer con el número de inscripciones. (El resto de la petición, p. ej. la vista de cada
inscripción, tiene su propio presupuesto y no es objeto de esta prueba.)
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import ClientFactory
from tests.integration.learning.helpers import (
    API,
    instructor_client,
    learner_client,
    publish_path,
)
from tests.integration.query_counter import count_queries

pytestmark = pytest.mark.integration


def _identity_statements(statements: list[str]) -> list[str]:
    return [s for s in statements if " users" in s.lower() or " consents" in s.lower()]


async def _enroll(
    admin: httpx.AsyncClient,
    client_for: ClientFactory,
    engine: AsyncEngine,
    path_id: int,
    name: str,
    *,
    pilot_consent: bool,
) -> dict[str, object]:
    learner = await learner_client(client_for, engine, name)
    me = (await learner.get(f"{API}/me")).json()
    if pilot_consent:
        granted = await learner.post(
            f"{API}/me/consents",
            json={"consent_type": "pilot_research", "document_version": "1.0"},
        )
        assert granted.status_code in (200, 201), granted.text
    created = await admin.post(
        f"{API}/enrollments", json={"user_id": me["id"], "learning_path_id": path_id}
    )
    assert created.status_code == 201, created.text
    return {"id": created.json()["id"], "full_name": me["full_name"], "pilot": pilot_consent}


async def test_admin_enrollment_list_identity_reads_do_not_grow_with_the_page(
    client: httpx.AsyncClient,
    client_for: ClientFactory,
    engine: AsyncEngine,
) -> None:
    instructor = await instructor_client(client_for, engine)
    path = await publish_path(instructor)
    listing = f"{API}/enrollments"

    await _enroll(client, client_for, engine, path.path_id, "uno", pilot_consent=True)
    with count_queries(engine) as one:
        first = await client.get(listing)
    assert first.status_code == 200, first.text
    assert first.json()["total"] == 1

    expected = [
        await _enroll(client, client_for, engine, path.path_id, name, pilot_consent=pilot)
        for name, pilot in (("dos", False), ("tres", True), ("cuatro", False), ("cinco", True))
    ]
    with count_queries(engine) as many:
        page = await client.get(listing)
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 5

    one_reads = _identity_statements(one.statements)
    many_reads = _identity_statements(many.statements)
    # Cinco inscripciones piden lo mismo a `users` y `consents` que una (la autenticación incluida).
    assert len(many_reads) == len(one_reads), "\n".join(many_reads)
    # La respuesta no cambia: cada fila trae su nombre y su consentimiento del piloto.
    by_id = {row["id"]: row for row in page.json()["items"]}
    for row in expected:
        assert by_id[row["id"]]["full_name"] == row["full_name"]
        assert by_id[row["id"]]["pilot_consent"] is row["pilot"]
