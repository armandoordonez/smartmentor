"""Supresión de datos: seudonimización y purga de `_audit` (ADR 0018) contra el esquema real."""

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import ClientFactory, insert_user

pytestmark = pytest.mark.integration

API = "/api/v1"

# Procedimiento de PRUEBA que hace el papel de `purge_user_audit(bigint)` de la base: la versión
# real la debe crear un changeset (pendiente, ver la bitácora F03c). Borra las filas de `_audit`
# que mencionan al titular.
PURGE_SQL = """
CREATE FUNCTION purge_user_audit(p_user bigint) RETURNS void LANGUAGE plpgsql AS $$
DECLARE t text;
BEGIN
    FOR t IN SELECT table_name FROM information_schema.tables
             WHERE table_schema = 'public' AND table_name LIKE '%\\_audit' LOOP
        EXECUTE format(
            'DELETE FROM %I WHERE (record_id = %s AND %L = ''users_audit'') '
            'OR COALESCE(new_data, old_data)->>''user_id'' = %L '
            'OR COALESCE(new_data, old_data)->>''id'' = %L AND %L = ''users_audit''',
            t, p_user, t, p_user::text, p_user::text, t);
    END LOOP;
END $$
"""


@pytest.fixture
async def purge_installed(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.execute(text("DROP FUNCTION IF EXISTS purge_user_audit(bigint)"))
        await conn.execute(text(PURGE_SQL))
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DROP FUNCTION IF EXISTS purge_user_audit(bigint)"))


async def audit_hits(engine: AsyncEngine, needle: str) -> list[str]:
    hits: list[str] = []
    async with engine.connect() as conn:
        tables = (
            await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name LIKE '%\\_audit'"
                )
            )
        ).scalars()
        for table in list(tables):
            count = (
                await conn.execute(
                    text(
                        f"SELECT count(*) FROM {table} "  # noqa: S608  (nombre leído del catálogo)
                        "WHERE old_data::text LIKE :n OR new_data::text LIKE :n"
                    ),
                    {"n": f"%{needle}%"},
                )
            ).scalar_one()
            if count:
                hits.append(table)
    return hits


async def request_deletion(
    engine: AsyncEngine, client_for: ClientFactory
) -> tuple[httpx.AsyncClient, int, int]:
    user_id = await insert_user(
        engine,
        email="persona.borrable@example.org",
        role="learner",
        sub="borrable-sub",
        name="Persona Borrable",
    )
    learner = client_for(sub="borrable-sub", email="persona.borrable@example.org")
    saved = await learner.put(
        f"{API}/me/profile",
        json={"description": "Soy Persona Borrable, analista", "job_title": "Analista"},
    )
    assert saved.status_code == 200, saved.text
    await learner.post(
        f"{API}/me/consents", json={"consent_type": "data_processing", "document_version": "1.0"}
    )
    created = await learner.post(
        f"{API}/me/data-subject-requests",
        json={"request_type": "deletion", "comment": "Quiero salir"},
    )
    assert created.status_code == 201, created.text
    return learner, user_id, int(created.json()["id"])


async def test_without_the_purge_procedure_the_erasure_is_refused_and_nothing_changes(
    client: httpx.AsyncClient, engine: AsyncEngine, client_for: ClientFactory
) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP FUNCTION IF EXISTS purge_user_audit(bigint)"))
    _, user_id, request_id = await request_deletion(engine, client_for)
    refused = await client.patch(
        f"{API}/data-subject-requests/{request_id}", json={"status": "resolved"}
    )
    assert refused.status_code == 503
    assert "purge_user_audit" in refused.json()["detail"]
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT email, active FROM users WHERE id = :u"), {"u": user_id}
            )
        ).one()
    assert row[0] == "persona.borrable@example.org"
    assert row[1] is True
    pending = await client.get(f"{API}/data-subject-requests", params={"status": "pending"})
    assert pending.json()["total"] == 1
    # Pasarla a «en curso» sí se puede mientras tanto.
    moving = await client.patch(
        f"{API}/data-subject-requests/{request_id}", json={"status": "in_progress"}
    )
    assert moving.status_code == 200
    assert moving.json()["erasure"] is None


async def test_resolving_a_deletion_pseudonymizes_the_person_and_leaves_no_trace_in_the_audit(
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    client_for: ClientFactory,
    purge_installed: None,
) -> None:
    _, user_id, request_id = await request_deletion(engine, client_for)
    assert await audit_hits(engine, "persona.borrable")  # antes de la supresión sí hay rastro

    resolved = await client.patch(
        f"{API}/data-subject-requests/{request_id}",
        json={"status": "resolved", "note": "Atendida"},
    )
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["status"] == "resolved"
    assert body["details"] is None  # el texto libre del titular no se conserva
    assert body["resolved_at"] is not None
    assert body["erasure"] == {
        "pseudonymized": True,
        "audit_purged": True,
        "identity_provider_action_required": True,
    }

    async with engine.connect() as conn:
        user = (
            await conn.execute(
                text("SELECT full_name, email, identity_subject, active FROM users WHERE id = :u"),
                {"u": user_id},
            )
        ).one()
        profile = (
            await conn.execute(
                text("SELECT description, job_title FROM user_profiles WHERE user_id = :u"),
                {"u": user_id},
            )
        ).one()
        consent_open = (
            await conn.execute(
                text("SELECT count(*) FROM consents WHERE user_id = :u AND revoked_at IS NULL"),
                {"u": user_id},
            )
        ).scalar_one()
    assert user[0] == "Usuario eliminado"
    assert user[1].endswith("@deleted.invalid")
    assert user[2] is None
    assert user[3] is False
    assert profile == (None, None)
    assert consent_open == 0
    for needle in ("persona.borrable", "Persona Borrable", "borrable-sub", "analista"):
        assert await audit_hits(engine, needle) == [], needle

    again = await client.patch(
        f"{API}/data-subject-requests/{request_id}", json={"status": "resolved"}
    )
    assert again.status_code == 409
    assert again.json()["code"] == "INVALID_STATE_TRANSITION"


async def test_only_deletions_erase_and_rejecting_changes_no_personal_data(
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    client_for: ClientFactory,
    purge_installed: None,
) -> None:
    learner, user_id, request_id = await request_deletion(engine, client_for)
    access = await learner.post(f"{API}/me/data-subject-requests", json={"request_type": "access"})
    resolved = await client.patch(
        f"{API}/data-subject-requests/{access.json()['id']}", json={"status": "resolved"}
    )
    assert resolved.json()["erasure"] is None
    rejected = await client.patch(
        f"{API}/data-subject-requests/{request_id}",
        json={"status": "rejected", "note": "No procede"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    async with engine.connect() as conn:
        active = (
            await conn.execute(text("SELECT active FROM users WHERE id = :u"), {"u": user_id})
        ).scalar_one()
    assert active is True
    listed = await client.get(f"{API}/data-subject-requests", params={"request_type": "access"})
    assert listed.json()["total"] == 1


async def test_the_admin_cannot_erase_themselves_and_only_the_admin_reaches_the_routes(
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    client_for: ClientFactory,
    bare_client: httpx.AsyncClient,
    purge_installed: None,
) -> None:
    admin_mine = await client.post(
        f"{API}/me/data-subject-requests", json={"request_type": "deletion"}
    )
    assert admin_mine.status_code == 201
    own = await client.patch(
        f"{API}/data-subject-requests/{admin_mine.json()['id']}", json={"status": "resolved"}
    )
    assert own.status_code == 409

    learner, _, request_id = await request_deletion(engine, client_for)
    for who in (learner,):
        assert (await who.get(f"{API}/data-subject-requests")).status_code == 403
        denied = await who.patch(
            f"{API}/data-subject-requests/{request_id}", json={"status": "resolved"}
        )
        assert denied.status_code == 403
    assert (await bare_client.get(f"{API}/data-subject-requests")).status_code == 401
    missing = await client.patch(f"{API}/data-subject-requests/99999", json={"status": "rejected"})
    assert missing.status_code == 404
    invalid = await client.patch(f"{API}/data-subject-requests/{request_id}", json={"status": "x"})
    assert invalid.status_code == 422
