"""Perfil y hoja de vida, autorizaciones y solicitudes de derechos (CU-17, CU-18)."""

import pytest

from app.common.constants import ConsentType, DataSubjectRequestType
from app.common.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domains.identity import labels
from app.domains.identity.service import (
    ConsentService,
    DataSubjectRequestService,
    MeService,
    ProfileService,
)
from tests.unit.conftest import current
from tests.unit.fakes import (
    FakeUnitOfWork,
    InMemoryConsents,
    InMemoryDataSubjectRequests,
    InMemoryProfiles,
)


class RecordingListener:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def on_profile_changed(self, user_id: int) -> list[int]:
        self.calls.append(user_id)
        return [7]


def services() -> tuple[ProfileService, ConsentService, RecordingListener, FakeUnitOfWork]:
    uow = FakeUnitOfWork()
    listener = RecordingListener()
    return (
        ProfileService(InMemoryProfiles(), uow, listener),
        ConsentService(InMemoryConsents(), uow),
        listener,
        uow,
    )


COMPLETE_RESUME = {
    "description": "Soy analista de datos en logística.",
    "education_level": "undergraduate",
    "qualification_title": "Ingeniería industrial",
    "job_title": "Analista de datos",
    "experience_band": "1_3_years",
    "tools": ["Excel", "SQL"],
    "languages": [{"code": "es", "cefr_level": "C2"}],
}


async def test_an_empty_profile_is_0_percent() -> None:
    profiles, _, _, _ = services()
    completeness = await profiles.completeness(1)
    assert (completeness.description, completeness.resume, completeness.percent) == (False, False, 0)


async def test_the_description_alone_is_half_the_profile() -> None:
    profiles, _, _, _ = services()
    await profiles.update(1, {"description": "Hola"})
    assert (await profiles.completeness(1)).percent == 50


async def test_a_complete_resume_sets_the_completion_time_and_keeps_it() -> None:
    profiles, _, _, _ = services()
    first, _ = await profiles.update(1, COMPLETE_RESUME)
    assert first.resume_completed_at is not None
    second, _ = await profiles.update(1, {**COMPLETE_RESUME, "job_title": "Líder de datos"})
    assert second.resume_completed_at == first.resume_completed_at
    assert (await profiles.completeness(1)).percent == 100


async def test_removing_a_required_resume_field_clears_the_completion() -> None:
    profiles, _, _, _ = services()
    await profiles.update(1, COMPLETE_RESUME)
    cleared, _ = await profiles.update(1, {**COMPLETE_RESUME, "experience_band": None})
    assert cleared.resume_completed_at is None


async def test_an_invalid_education_level_is_rejected() -> None:
    profiles, _, _, _ = services()
    with pytest.raises(BusinessRuleError):
        await profiles.update(1, {"education_level": "doctor-honoris-causa"})


async def test_changing_the_profile_asks_the_paths_to_recalculate() -> None:
    profiles, _, listener, _ = services()
    _, recalculated = await profiles.update(1, COMPLETE_RESUME)
    assert listener.calls == [1]
    assert recalculated == [7]


async def test_granting_a_consent_is_idempotent() -> None:
    _, consents, _, uow = services()
    first, created = await consents.grant(1, ConsentType.DATA_PROCESSING, "1.0")
    again, created_again = await consents.grant(1, ConsentType.DATA_PROCESSING, "1.0")
    assert created is True
    assert created_again is False
    assert again.id == first.id
    assert uow.commits == 1


async def test_a_new_document_version_replaces_the_one_in_force() -> None:
    _, consents, _, _ = services()
    old, _ = await consents.grant(1, ConsentType.DATA_PROCESSING, "1.0")
    new, created = await consents.grant(1, ConsentType.DATA_PROCESSING, "2.0")
    assert created is True
    assert new.id != old.id
    assert (await consents.status(1))["data_processing"] == new
    all_consents = await consents.list_consents(1)
    assert [c.in_force for c in all_consents] == [False, True]


async def test_revoking_and_granting_again() -> None:
    _, consents, _, _ = services()
    await consents.grant(1, ConsentType.PILOT_RESEARCH, "1.0")
    revoked = await consents.revoke(1, ConsentType.PILOT_RESEARCH)
    assert revoked.revoked_at is not None
    with pytest.raises(ConflictError) as error:
        await consents.revoke(1, ConsentType.PILOT_RESEARCH)
    assert error.value.code == "CONSENT_ALREADY_REVOKED"
    regranted, created = await consents.grant(1, ConsentType.PILOT_RESEARCH, "1.0")
    assert created is True
    assert regranted.in_force


async def test_revoking_something_never_granted_is_404() -> None:
    _, consents, _, _ = services()
    with pytest.raises(NotFoundError):
        await consents.revoke(1, ConsentType.DATA_PROCESSING)


async def test_consents_are_per_user() -> None:
    _, consents, _, _ = services()
    await consents.grant(1, ConsentType.DATA_PROCESSING, "1.0")
    assert await consents.has_data_processing(1) is True
    assert await consents.has_data_processing(2) is False


async def test_data_subject_requests_start_pending() -> None:
    uow = FakeUnitOfWork()
    service = DataSubjectRequestService(InMemoryDataSubjectRequests(), uow)
    created = await service.create(1, DataSubjectRequestType.DELETION, "Quiero salir")
    assert created.status == "pending"
    assert created.request_type == "deletion"
    assert uow.commits == 1


async def test_me_view_requires_consent_until_data_processing_is_granted() -> None:
    profiles, consents, _, _ = services()
    me = MeService(profiles, consents, context="generic")
    user = current(1, "learner")
    assert (await me.view(user)).requires_consent is True
    await consents.grant(1, ConsentType.DATA_PROCESSING, "1.0")
    assert (await me.view(user)).requires_consent is False
    await consents.revoke(1, ConsentType.DATA_PROCESSING)
    assert (await me.view(user)).requires_consent is True


def test_role_labels_come_from_the_glossary_and_always_have_three_roles() -> None:
    assert labels.role_labels("generic") == {
        "learner": "Aprendiz",
        "instructor": "Instructor",
        "admin": "Administrador",
    }
    assert labels.role_short_labels("generic")["admin"] == "Admin"
    assert labels.role_labels("academic")["learner"] == "Estudiante"
    assert labels.role_labels("corporate")["instructor"] == "Capacitador"
    assert labels.role_labels("desconocido") == labels.role_labels("generic")
