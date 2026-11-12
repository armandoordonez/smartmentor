"""Cliente de fixtures: documentos fijos y un eco mínimo del estado de la sesión de demostración."""

import pytest
from support import FIXTURES_DIR

from clients.base import ApiError
from clients.fixtures import SCENARIOS, SCENARIOS_BY_KEY, FixturesClient
from clients.jobs import wait_for_job
from clients.models import ProfileUpdate


def test_every_scenario_points_to_existing_fixture_files() -> None:
    for scenario in SCENARIOS:
        for name in (scenario.me, scenario.profile, scenario.consents, scenario.enrollments):
            assert (FIXTURES_DIR / f"{name}.json").is_file(), (scenario.key, name)


def test_scenarios_cover_the_three_roles() -> None:
    assert {scenario.role for scenario in SCENARIOS} == {"learner", "instructor", "admin"}


@pytest.mark.parametrize("key", list(SCENARIOS_BY_KEY))
def test_every_scenario_loads_a_user_whose_default_role_is_one_of_theirs(key: str) -> None:
    me = FixturesClient(key).get_me()
    assert me.default_role in me.roles
    assert me.default_role == SCENARIOS_BY_KEY[key].role or key == "learner_in_path"


def test_new_learner_requires_consent_until_granting_it() -> None:
    client = FixturesClient("learner_new")
    assert client.get_me().requires_consent
    client.grant_consent("data_processing", "1.0")
    me = client.get_me()
    assert not me.requires_consent
    assert me.consent_status.data_processing.granted
    assert not me.is_new_user


def test_revoking_data_consent_requires_it_again() -> None:
    client = FixturesClient("learner")
    client.revoke_consent("data_processing")
    assert client.get_me().requires_consent


def test_catalog_has_six_paths_in_two_sections() -> None:
    page = FixturesClient("learner").list_learning_paths()
    assert page.total == 6
    assert [c.section for c in page.items].count("applied_ai") == 3
    assert page.items[0].tags == ["recommended"]


def test_catalog_pagination_slices_the_items() -> None:
    page = FixturesClient("learner").list_learning_paths(limit=2, offset=4)
    assert [card.id for card in page.items] == [5, 6]


def test_enrolling_returns_next_action_complete_profile() -> None:
    client = FixturesClient("learner")
    enrollment = client.create_enrollment(2)
    assert enrollment.learning_path.name == "Estadística para ciencia de datos"
    assert enrollment.next_action.type == "complete_profile"
    assert enrollment.next_action.screen == "E2"
    assert client.list_enrollments().total == 1


def test_enrolling_twice_conflicts() -> None:
    client = FixturesClient("learner_in_path")
    with pytest.raises(ApiError) as caught:
        client.create_enrollment(1)
    assert caught.value.code == "ENROLLMENT_ALREADY_EXISTS"


def test_unpublished_path_is_refused() -> None:
    with pytest.raises(ApiError) as caught:
        FixturesClient("learner").create_enrollment(999)
    assert caught.value.code == "LEARNING_PATH_NOT_PUBLISHED"


def test_unknown_enrollment_is_404() -> None:
    with pytest.raises(ApiError) as caught:
        FixturesClient("learner").get_enrollment(12345)
    assert caught.value.status == 404


def test_profile_update_is_echoed_and_updates_completeness() -> None:
    client = FixturesClient("learner_new")
    client.update_profile(ProfileUpdate(description="Hola, soy nuevo"))
    assert client.get_profile().description == "Hola, soy nuevo"
    assert client.get_me().profile_completeness.description


def test_sessions_do_not_share_state() -> None:
    first, second = FixturesClient("learner_new"), FixturesClient("learner_new")
    first.grant_consent("data_processing", "1.0")
    assert second.get_me().requires_consent


def test_job_runs_first_and_succeeds_on_the_next_poll() -> None:
    client = FixturesClient("learner_in_path")
    accepted = client.submit_diagnostic(7, idempotency_key="k")
    job = wait_for_job(client, accepted.job_id, sleep=lambda _: None)
    assert job.status == "succeeded"
    # Como la API real: el trabajo no trae `next_action`; la inscripción sí cambia.
    assert job.next_action is None
    assert client.get_enrollment(7).next_action.type == "confirm_objective"


def test_missing_fixture_file_is_a_404(tmp_path: object) -> None:
    from pathlib import Path

    with pytest.raises(ApiError):
        FixturesClient("learner", directory=Path(str(tmp_path)))
