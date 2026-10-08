"""Arma los servicios de la sesión sobre la fuente de datos configurada.

Con `APP_DATA_SOURCE=sample`, cada sesión del navegador tiene su propia copia de los datos de
ejemplo: lo que hace un usuario de prueba no se ve en otra sesión, pero sí al cambiar de rol en la
misma (p. ej., el docente ve el avance que el estudiante acaba de hacer).
"""

from dataclasses import dataclass

import streamlit as st

from clients.base import SmartMentorClient
from clients.models import User
from clients.sample_data import SampleDataClient
from clients.sample_seed import SampleStore, build_seed
from core.config import get_settings
from core.session import get_session
from services.admin import AdminService
from services.assessment import AssessmentService
from services.catalog import CatalogService
from services.enrollment import EnrollmentService
from services.learning_path import LearningPathService
from services.teacher_dashboard import TeacherService

_STORE_KEY = "sample_store"


@dataclass(frozen=True)
class Services:
    catalog: CatalogService
    enrollment: EnrollmentService
    learning_path: LearningPathService
    assessment: AssessmentService
    teacher: TeacherService
    admin: AdminService


def _sample_store() -> SampleStore:
    if _STORE_KEY not in st.session_state:
        st.session_state[_STORE_KEY] = build_seed()
    store: SampleStore = st.session_state[_STORE_KEY]
    return store


def reset_sample_data() -> None:
    st.session_state.pop(_STORE_KEY, None)


def _client() -> SmartMentorClient:
    session = get_session()
    if session.user_id is None:
        raise RuntimeError("No hay usuario en la sesión")
    match get_settings().app_data_source:
        case "sample":
            return SampleDataClient(_sample_store(), session.user_id)


def get_services() -> Services:
    client = _client()
    return Services(
        catalog=CatalogService(client),
        enrollment=EnrollmentService(client),
        learning_path=LearningPathService(client),
        assessment=AssessmentService(client),
        teacher=TeacherService(client),
        admin=AdminService(client),
    )


def current_user() -> User:
    return _client().me()
