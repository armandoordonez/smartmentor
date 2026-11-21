"""E9 → E8: «Reintentar evaluación final» con la API simulada con `respx` (B-050 y B-048).

Las pruebas con `FixturesClient` no ven lo que ve la persona con la API real: la inscripción cambia
de `next_action` entre una lectura y otra (`review_final` → `continue_attempt`), un `POST` repetido
con la misma `Idempotency-Key` devuelve la misma respuesta (incluido el `202`) y un intento abierto
responde `409 ATTEMPT_NOT_GRADED` en su resultado. Aquí se simula eso, con el `ApiClient` real.
"""

import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
import respx
from apptest import button, new_app, page_texts, session_of
from learner_support import FINAL, FINAL_RESULT
from streamlit.testing.v1 import AppTest
from support import FIXTURES_DIR
from test_api_mode import API, jwt, logged_in_as

from clients.models import Me
from core.session import AppSession

ENROLLMENT_ID = 7
GRADED = 9100
NEW_ATTEMPT = 9101
JOB_ID = "job-final-prepare"
OPEN_ATTEMPT_TEXT = "Tu evaluación final sigue abierta: retómala donde la dejaste y entrégala."
PREPARING = "Preparando preguntas nuevas para tu evaluación final"
RETRY = "Reintentar evaluación final"


def _doc(name: str) -> Any:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _problem(status: int, code: str) -> httpx.Response:
    body = {"status": status, "code": code, "title": "x", "detail": "x", "request_id": "r1"}
    return httpx.Response(status, json=body, headers={"Content-Type": "application/problem+json"})


class FinalApi:
    """La API de un aprendiz con la final reprobada (E9), con el comportamiento de la real."""

    def __init__(self, *, needs_generation: bool = False) -> None:
        self.needs_generation = needs_generation
        self.open_attempt: int | None = None
        self.generated = False
        self.job_polls = 0
        self.post_keys: list[str] = []
        self.stored: dict[str, httpx.Response] = {}
        self.result_calls: list[int] = []
        self.attempt_calls: list[int] = []
        self.event_batches = 0

    # --- Lo que la API dice -----------------------------------------------------------------

    def next_action(self) -> dict[str, Any]:
        if self.open_attempt is not None:
            return {
                "type": "continue_attempt",
                "attempt_id": self.open_attempt,
                "step_id": None,
                "job_id": None,
                "screen": "E8",
            }
        return {
            "type": "review_final",
            "attempt_id": GRADED,
            "step_id": None,
            "job_id": None,
            "screen": "E9",
        }

    def enrollment(self) -> dict[str, Any]:
        item = dict(_doc("learner/enrollments_final_failed")["items"][0])
        item["next_action"] = self.next_action()
        return item

    # --- Rutas ------------------------------------------------------------------------------

    def _result(self, request: httpx.Request) -> httpx.Response:
        attempt_id = int(request.url.path.split("/")[-2])
        self.result_calls.append(attempt_id)
        if attempt_id == self.open_attempt:
            return _problem(409, "ATTEMPT_NOT_GRADED")
        return httpx.Response(200, json=_doc("learner/attempt_result_final_failed"))

    def _attempt(self, request: httpx.Request) -> httpx.Response:
        self.attempt_calls.append(int(request.url.path.split("/")[-1]))
        return httpx.Response(200, json=_doc("learner/attempt_final_retry"))

    def _create(self, request: httpx.Request) -> httpx.Response:
        key = request.headers["Idempotency-Key"]
        self.post_keys.append(key)
        if key in self.stored:  # misma clave, misma respuesta (api-v2.md, sección 1)
            return self.stored[key]
        if self.needs_generation and not self.generated:
            job = {"job_id": JOB_ID, "status": "queued", "poll_url": f"/api/v1/jobs/{JOB_ID}"}
            response = httpx.Response(202, json=job)
        else:
            self.open_attempt = NEW_ATTEMPT
            response = httpx.Response(201, json=_doc("learner/attempt_final_retry"))
        self.stored[key] = response
        return response

    def _job(self, request: httpx.Request) -> httpx.Response:
        del request
        self.job_polls += 1
        done = self.job_polls >= 2
        self.generated = done
        job = {
            "job_id": JOB_ID,
            "job_type": "items.generate_final_bank",
            "status": "succeeded" if done else "running",
            "progress_label": "Listo" if done else "Generando",
            "ingested": done,
            "next_action": None,
            "error": None,
        }
        return httpx.Response(200, json=job)

    def _events(self, request: httpx.Request) -> httpx.Response:
        self.event_batches += 1
        accepted = len(json.loads(request.content)["events"])
        return httpx.Response(202, json={"accepted": accepted})

    def mount(self) -> None:
        base = f"{API}/api/v1"
        respx.get(f"{base}/learning-paths").mock(
            return_value=httpx.Response(200, json=_doc("learning_paths"))
        )
        respx.get(f"{base}/me/enrollments/{ENROLLMENT_ID}").mock(
            side_effect=lambda _: httpx.Response(200, json=self.enrollment())
        )
        respx.get(f"{base}/me/enrollments/{ENROLLMENT_ID}/path").mock(
            return_value=httpx.Response(200, json=_doc("learner/path_all_passed"))
        )
        respx.get(f"{base}/me/enrollments/{ENROLLMENT_ID}/review-plan").mock(
            return_value=httpx.Response(200, json=_doc("learner/review_plan"))
        )
        respx.get(url__regex=rf"{base}/me/attempts/\d+/result").mock(side_effect=self._result)
        respx.get(url__regex=rf"{base}/me/attempts/\d+").mock(side_effect=self._attempt)
        respx.post(f"{base}/me/enrollments/{ENROLLMENT_ID}/final-attempts").mock(
            side_effect=self._create
        )
        respx.get(f"{base}/jobs/{JOB_ID}").mock(side_effect=self._job)
        respx.post(f"{base}/me/events").mock(side_effect=self._events)


def _app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    """E9 abierto con el `ApiClient` real y el token simulado."""
    monkeypatch.setenv("APP_DATA_SOURCE", "api")
    monkeypatch.setenv("API_BASE_URL", API)
    logged_in_as(monkeypatch, jwt(timedelta(minutes=30)))
    at = new_app()
    me = Me.model_validate(_doc("me_learner"))
    at.session_state["app_session"] = AppSession(me=me, active_role="learner")
    session = session_of_state(at)
    session.selected_enrollment_id = ENROLLMENT_ID
    session.learner.final_attempt_id = GRADED
    at.run()
    at.switch_page(FINAL_RESULT).run()
    return at


def session_of_state(at: AppTest) -> AppSession:
    session = at.session_state["app_session"]
    assert isinstance(session, AppSession)
    return session


def _on_e8_question_one(at: AppTest) -> None:
    assert [e.value for e in at.exception] == []
    texts = page_texts(at, alerts=True)
    assert OPEN_ATTEMPT_TEXT not in texts
    assert "Continuar evaluación final" not in [b.label for b in at.button]
    assert "Evaluación final" in texts
    assert any("Pregunta 1 de 10" in t for t in texts)
    assert session_of(at).learner.final_attempt_id == NEW_ATTEMPT


# --- B-050 · el intento se crea (201) --------------------------------------------------------


@respx.mock
def test_retry_opens_e8_with_the_new_attempt_and_never_asks_its_result_b050(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FinalApi()
    api.mount()
    at = _app(monkeypatch)
    button(at, RETRY).click().run()
    _on_e8_question_one(at)
    assert api.post_keys and len(api.post_keys) == 1
    assert api.result_calls.count(NEW_ATTEMPT) == 0


@respx.mock
def test_e9_reopened_after_the_retry_goes_to_e8_without_a_screen_in_between_b050(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si E9 se ejecuta otra vez con el intento nuevo abierto (como en el navegador, con la API
    lenta), la API ya dice `continue_attempt`: E8 se abre sin la pantalla «sigue abierta» y sin
    pedir el resultado de un intento que no está calificado (409)."""
    api = FinalApi()
    api.mount()
    at = _app(monkeypatch)
    button(at, RETRY).click().run()
    at.switch_page(FINAL_RESULT).run()
    _on_e8_question_one(at)
    assert api.result_calls.count(NEW_ATTEMPT) == 0
    assert len(api.post_keys) == 1


@respx.mock
def test_e9_with_an_open_attempt_in_the_session_goes_to_e8_b050(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E9 recuerda el intento recién creado: abre E8 aunque la inscripción leída esté atrasada."""
    api = FinalApi()
    api.mount()
    at = _app(monkeypatch)
    button(at, RETRY).click().run()
    api.open_attempt = None  # la inscripción leída sigue en `review_final`
    state = session_of(at).learner
    state.pending_final_attempt_id = state.final_attempt_id = NEW_ATTEMPT
    api.result_calls.clear()
    at.switch_page(FINAL_RESULT).run()
    _on_e8_question_one(at)
    assert api.result_calls.count(NEW_ATTEMPT) == 0


# --- B-048 · faltan preguntas sin ver: 202 con un trabajo ------------------------------------


@respx.mock
def test_retry_with_202_waits_for_the_job_and_then_asks_the_attempt_again_b048(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """U1b mientras se generan las preguntas y, al terminar el trabajo, E8 con el intento nuevo."""
    api = FinalApi(needs_generation=True)
    api.mount()
    at = _app(monkeypatch)
    button(at, RETRY).click().run()
    assert [e.value for e in at.exception] == []
    assert PREPARING in page_texts(at)
    assert session_of(at).learner.quiz_job_id == JOB_ID
    assert api.open_attempt is None
    assert len(api.post_keys) == 1
    for _ in range(4):  # cada ejecución sondea el trabajo una vez
        if api.open_attempt is not None:
            break
        at.switch_page(FINAL).run()
    _on_e8_question_one(at)
    first, second = api.post_keys
    # La API repite la respuesta de una clave ya usada (el 202): el segundo POST lleva otra.
    assert first != second
    assert api.result_calls.count(NEW_ATTEMPT) == 0


def test_the_same_key_replays_the_202_so_the_app_asks_with_a_new_one_b048() -> None:
    """La API guarda la respuesta por clave: repetir el POST con la misma devolvería el 202."""
    api = FinalApi(needs_generation=True)
    with respx.mock:
        api.mount()
        client = httpx.Client(base_url=API)
        url = f"/api/v1/me/enrollments/{ENROLLMENT_ID}/final-attempts"
        first = client.post(url, headers={"Idempotency-Key": "k"})
        api.generated = True
        replay = client.post(url, headers={"Idempotency-Key": "k"})
        fresh = client.post(url, headers={"Idempotency-Key": "k2"})
    assert (first.status_code, replay.status_code, fresh.status_code) == (202, 202, 201)


@respx.mock
def test_retry_with_202_and_a_failed_job_offers_to_retry_b048(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FinalApi(needs_generation=True)
    api.mount()
    respx.get(f"{API}/api/v1/jobs/{JOB_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "job_id": JOB_ID,
                "job_type": "items.generate_final_bank",
                "status": "failed",
                "progress_label": "Error",
                "ingested": False,
                "next_action": None,
                "error": {"code": "AI_FAILED", "message": "x"},
            },
        )
    )
    at = _app(monkeypatch)
    button(at, RETRY).click().run()
    at.switch_page(FINAL).run()
    assert [e.value for e in at.exception] == []
    assert any("No pudimos preparar las preguntas nuevas" in e.value for e in at.error)
    button(at, "Reintentar").click().run()
    assert len(api.post_keys) == 2
    assert api.post_keys[0] != api.post_keys[1]
