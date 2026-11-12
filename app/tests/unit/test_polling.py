"""El sondeo desde un fragmento no deja pasar un 401 como traceback."""

import pytest
import streamlit as st

from clients.base import ApiError
from clients.models import Job
from core import polling

JOB = Job(job_id="j1", job_type="syllabus.structure", status="running", ingested=False)


def test_returns_the_job_when_the_call_works() -> None:
    assert polling.poll_job_or_rerun(lambda: JOB) is JOB


def test_expired_token_asks_for_a_full_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_rerun() -> None:
        calls.append("rerun")
        raise RuntimeError("rerun")  # `st.rerun` interrumpe la ejecución

    monkeypatch.setattr(st, "rerun", fake_rerun)

    def expired() -> Job:
        raise ApiError(401, "TOKEN_EXPIRED", "access token missing or expired")

    with pytest.raises(RuntimeError, match="rerun"):
        polling.poll_job_or_rerun(expired)
    assert calls == ["rerun"]


def test_other_errors_are_shown_and_polling_goes_on(monkeypatch: pytest.MonkeyPatch) -> None:
    shown: list[ApiError] = []
    monkeypatch.setattr(polling, "show_staff_error", shown.append)

    def broken() -> Job:
        raise ApiError(404, "COURSE_NOT_FOUND", "no existe")

    assert polling.poll_job_or_rerun(broken) is None
    assert [error.code for error in shown] == ["COURSE_NOT_FOUND"]
