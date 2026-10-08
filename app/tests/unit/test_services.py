"""Servicios de la interfaz sobre los datos de ejemplo."""

from clients.sample_data import SampleDataClient
from clients.sample_seed import build_seed
from services.admin import AdminService
from services.assessment import AssessmentService
from services.catalog import CatalogService
from services.learning_path import LearningPathService


def test_catalog_marks_enrolled_paths() -> None:
    cards = CatalogService(SampleDataClient(build_seed(), 1)).list_path_cards()
    assert {c.path.id: c.enrollment is not None for c in cards} == {1: True, 2: False, 3: False}


def test_path_view_matches_the_design_state() -> None:
    client = SampleDataClient(build_seed(), 1)
    service = LearningPathService(client)
    view = service.path_view(client.list_my_enrollments()[0])
    assert (view.done_count, view.skipped_count, len(view.steps)) == (2, 1, 5)
    assert view.current is not None and view.current.topic.title == "Regresión logística"
    assert view.progress.saved_minutes == 80

    overview = service.progress_overview()
    assert (overview.done_topics, overview.total_topics, overview.saved_minutes) == (2, 5, 80)


def test_badge_slots_list_earned_badges_first() -> None:
    slots = AssessmentService(SampleDataClient(build_seed(), 4)).badge_slots()
    assert slots[0].badge is not None and slots[0].path.id == 1
    assert all(s.badge is None for s in slots[1:])


def test_metrics_compare_with_their_target() -> None:
    views = {
        v.metric.key: v.meets_target
        for v in AdminService(SampleDataClient(build_seed(), 3)).metrics()
    }
    assert views["syllabus_f1"] is True
    assert views["diagnostic_auc"] is False
    assert views["attempts_per_topic"] is True
    assert views["cost_per_student_path"] is None
