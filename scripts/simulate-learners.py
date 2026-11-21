#!/usr/bin/env python3
"""Simula aprendices que recorren cada curso publicado de punta a punta. SOLO DESARROLLO.

Crea (si no existen) 4 aprendices en Keycloak y, con la API real, cada uno:
autorizaciones → perfil → inscripción en cada ruta publicada → diagnóstico → objetivo →
estudio y quiz de cada paso (con reintentos) → evaluación final → encuesta. Si un paso agota
los intentos, el administrador habilita uno más, como haría el instructor (D4b).

Las respuestas correctas se leen con la cuenta del administrador (`GET /topics/{id}/items`):
cada aprendiz acierta con su propia probabilidad y mejora en cada reintento, así que los
resultados son distintos y repetibles (semilla fija). Las respuestas cortas las califica la IA.

Uso (desde la raíz, con el stack levantado y el .env real):
    python3 scripts/simulate-learners.py                 # los 4 aprendices en todas las rutas
    python3 scripts/simulate-learners.py --only 1 --path 5

Lee del .env: SEED_USERS_PASSWORD (contraseña de los aprendices y de SEED_ADMIN_EMAIL),
KEYCLOAK_ADMIN y KEYCLOAK_ADMIN_PASSWORD, KEYCLOAK_PORT y API_PORT. No imprime contraseñas.
**Cuidado:** escribe en la base que use el .env y gasta la cuota de la IA real.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REALM = "smartmentor"
JOB_TIMEOUT_S = 900
MAX_LOOPS = 250

PERSONAS: list[dict[str, Any]] = [
    {
        "email": "aprendiz1.smartmentor@yopmail.com",
        "first": "Valentina",
        "last": "Rojas",
        "skill": 0.92,
        "pilot": True,
        "profile": {
            "description": "Ingeniera de sistemas con cinco años como desarrolladora backend. "
            "Trabajo a diario con Python, SQL y pipelines de datos en la nube.",
            "education_level": "postgraduate",
            "qualification_title": "Especialización en ingeniería de software",
            "job_title": "Desarrolladora backend",
            "experience_band": "3_5_years",
            "tools": ["Python", "SQL", "Docker", "Git", "AWS"],
            "languages": [{"code": "es", "cefr_level": "C2"}, {"code": "en", "cefr_level": "B2"}],
        },
    },
    {
        "email": "aprendiz2.smartmentor@yopmail.com",
        "first": "Andrés",
        "last": "Gómez",
        "skill": 0.78,
        "pilot": True,
        "profile": {
            "description": "Analista de datos en una empresa de logística. Uso Excel y Power BI "
            "y estoy aprendiendo Python para automatizar reportes.",
            "education_level": "undergraduate",
            "qualification_title": "Ingeniería industrial",
            "job_title": "Analista de datos",
            "experience_band": "1_3_years",
            "tools": ["Excel", "Power BI", "SQL"],
            "languages": [{"code": "es", "cefr_level": "C2"}, {"code": "en", "cefr_level": "B1"}],
        },
    },
    {
        "email": "aprendiz3.smartmentor@yopmail.com",
        "first": "Camila",
        "last": "Torres",
        "skill": 0.62,
        "pilot": False,
        "profile": {
            "description": "Tecnóloga en gestión administrativa. Quiero pasarme al área de "
            "tecnología y apenas empiezo con programación.",
            "education_level": "technical",
            "qualification_title": "Tecnología en gestión administrativa",
            "job_title": "Asistente administrativa",
            "experience_band": "less_than_1_year",
            "tools": ["Excel"],
            "languages": [{"code": "es", "cefr_level": "C2"}],
        },
    },
    {
        "email": "aprendiz4.smartmentor@yopmail.com",
        "first": "Julián",
        "last": "Mejía",
        "skill": 0.45,
        "pilot": False,
        "profile": {
            "description": "Estudiante de último semestre de bachillerato técnico. No tengo "
            "experiencia laboral pero me interesa la inteligencia artificial.",
            "education_level": "secondary",
            "qualification_title": None,
            "job_title": None,
            "experience_band": "none",
            "tools": [],
            "languages": [{"code": "es", "cefr_level": "C2"}],
        },
    },
]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text("utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"')
    return env


class ApiError(Exception):
    def __init__(self, status: int, body: Any) -> None:
        self.status, self.body = status, body
        code = body.get("code") if isinstance(body, dict) else None
        self.code = code or ""
        super().__init__(f"HTTP {status} {code or ''} {str(body)[:300]}")


def http(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: Any = None,
    form: dict[str, str] | None = None,
    idempotent: bool = False,
) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idempotent:
        headers["Idempotency-Key"] = str(uuid.uuid4())
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (solo localhost)
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw.decode(errors="replace")
        raise ApiError(exc.code, parsed) from None


class Keycloak:
    def __init__(self, env: dict[str, str]) -> None:
        self.base = f"http://localhost:{env.get('KEYCLOAK_PORT', '8180')}"
        self.env = env

    def token(self, username: str, password: str) -> str:
        _, data = http(
            "POST",
            f"{self.base}/realms/{REALM}/protocol/openid-connect/token",
            form={
                "grant_type": "password",
                "client_id": "smartmentor-dev-tools",
                "username": username,
                "password": password,
                "scope": "openid profile email",
            },
        )
        return str(data["access_token"])

    def ensure_learner(self, persona: dict[str, Any], password: str) -> str:
        _, data = http(
            "POST",
            f"{self.base}/realms/master/protocol/openid-connect/token",
            form={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self.env.get("KEYCLOAK_ADMIN", "admin"),
                "password": self.env["KEYCLOAK_ADMIN_PASSWORD"],
            },
        )
        admin = data["access_token"]
        users = f"{self.base}/admin/realms/{REALM}/users"
        email = persona["email"]
        try:
            http(
                "POST",
                users,
                token=admin,
                body={
                    "username": email,
                    "email": email,
                    "emailVerified": True,
                    "enabled": True,
                    "firstName": persona["first"],
                    "lastName": persona["last"],
                    "credentials": [{"type": "password", "value": password, "temporary": False}],
                },
            )
            state = "creado"
        except ApiError as exc:
            if exc.status != 409:
                raise
            state = "ya existía"
        query = urllib.parse.urlencode({"email": email, "exact": "true"})
        _, found = http("GET", f"{users}?{query}", token=admin)
        user_id = found[0]["id"]
        _, role = http("GET", f"{self.base}/admin/realms/{REALM}/roles/learner", token=admin)
        http("POST", f"{users}/{user_id}/role-mappings/realm", token=admin, body=[role])
        return state


class AnswerKey:
    """Ítems con su respuesta, leídos como administrador. Se recarga si aparece uno nuevo."""

    def __init__(self, api: str, token: Any) -> None:
        self.api, self.token = api, token  # función que devuelve un token vigente
        self.items: dict[int, dict[str, Any]] = {}
        self.loaded_topics: set[int] = set()

    def load_topic(self, topic_id: int) -> None:
        offset = 0
        while True:
            _, page = http(
                "GET",
                f"{self.api}/topics/{topic_id}/items?limit=100&offset={offset}",
                token=self.token(),
            )
            for item in page["items"]:
                self.items[int(item["id"])] = item
            offset += len(page["items"])
            if not page["items"] or offset >= page["total"]:
                break
        self.loaded_topics.add(topic_id)

    def get(self, item_id: int, topic_id: int | None) -> dict[str, Any] | None:
        if item_id not in self.items and topic_id is not None:
            self.load_topic(topic_id)
        return self.items.get(item_id)


class Learner:
    def __init__(
        self, persona: dict[str, Any], kc: Keycloak, password: str, api: str, key: AnswerKey,
        admin: Any,
    ) -> None:
        self.p, self.kc, self.password, self.api, self.key = persona, kc, password, api, key
        self.admin = admin  # función que devuelve un token vigente del administrador
        self.token = kc.token(persona["email"], password)
        self.rng = random.Random(persona["email"])  # noqa: S311 (simulación, no criptografía)
        self.log_lines: list[str] = []

    def call(self, method: str, path: str, **kw: Any) -> tuple[int, Any]:
        """Llama a la API; renueva el token si venció (dura 5 min) y reintenta cortes de la IA."""
        for attempt in range(4):
            try:
                return http(method, f"{self.api}{path}", token=self.token, **kw)
            except ApiError as exc:
                if exc.status == 401 and attempt == 0:
                    self.token = self.kc.token(self.p["email"], self.password)
                elif exc.status == 503 and exc.code == "AI_SERVICE_UNAVAILABLE" and attempt < 3:
                    self.log(f"la IA no respondió ({method} {path}); reintento en 15 s")
                    time.sleep(15)
                else:
                    raise
        raise RuntimeError("inalcanzable")

    def log(self, text: str) -> None:
        line = f"  [{self.p['first']}] {text}"
        print(line, flush=True)
        self.log_lines.append(line)

    # --- Preparación -------------------------------------------------------------------------
    def setup(self) -> None:
        self.call("GET", "/me")
        self.call("POST", "/me/consents", body={"consent_type": "data_processing",
                                                 "document_version": "1.0"})
        if self.p["pilot"]:
            self.call("POST", "/me/consents", body={"consent_type": "pilot_research",
                                                     "document_version": "1.0"})
        self.call("PUT", "/me/profile", body=self.p["profile"])

    def enroll(self, path_id: int) -> int:
        try:
            _, enrollment = self.call("POST", "/me/enrollments",
                                      body={"learning_path_id": path_id})
            return int(enrollment["id"])
        except ApiError as exc:
            if exc.status != 409:
                raise
        _, page = self.call("GET", "/me/enrollments?limit=100")
        for enrollment in page["items"]:
            if enrollment["learning_path"]["id"] == path_id:
                return int(enrollment["id"])
        raise RuntimeError(f"No se encontró la inscripción en la ruta {path_id}")

    # --- Respuestas --------------------------------------------------------------------------
    def answer(self, item: dict[str, Any], skill: float, allow_dont_know: bool) -> dict[str, Any]:
        item_id = int(item["item_id"] if "item_id" in item else item["id"])
        known = self.key.get(item_id, item.get("topic_id"))
        right = self.rng.random() < skill
        if item.get("item_type") == "short_answer":
            text = (known or {}).get("model_answer") if right else None
            return {"item_id": item_id, "selected_option": None, "dont_know": False,
                    "text_answer": text or "No estoy seguro; creo que depende del contexto."}
        if allow_dont_know and not right and self.rng.random() < 0.4:
            return {"item_id": item_id, "selected_option": None, "dont_know": True,
                    "text_answer": None}
        options = len(item.get("options") or []) or 4
        correct = (known or {}).get("correct_option")
        if correct is None:
            choice = self.rng.randrange(options)
        elif right:
            choice = int(correct)
        else:
            choice = self.rng.choice([i for i in range(options) if i != correct] or [0])
        return {"item_id": item_id, "selected_option": choice, "dont_know": False,
                "text_answer": None}

    def wait_job(self, job_id: str, label: str) -> dict[str, Any]:
        start = time.monotonic()
        while time.monotonic() - start < JOB_TIMEOUT_S:
            _, job = self.call("GET", f"/jobs/{job_id}")
            if job["status"] == "succeeded" and job.get("ingested", True):
                return job
            if job["status"] in ("failed", "cancelled"):
                raise RuntimeError(f"El trabajo {label} falló: {job.get('error')}")
            time.sleep(4)
        raise TimeoutError(f"El trabajo {label} tardó más de {JOB_TIMEOUT_S} s")

    # --- Recorrido ---------------------------------------------------------------------------
    def run_enrollment(self, enrollment_id: int, name: str) -> dict[str, Any]:
        tries: dict[int | None, int] = {}  # intentos por paso (None = final)
        seen_results: set[int] = set()
        base = f"/me/enrollments/{enrollment_id}"
        for _ in range(MAX_LOOPS):
            _, enrollment = self.call("GET", base)
            action = enrollment["next_action"]
            kind = action["type"]
            if kind in ("view_badge", "none"):
                self.log(f"{name}: terminó ({enrollment['status']}, {kind})")
                return {"course": name, "status": enrollment["status"], "tries": tries}
            if kind == "complete_profile":
                self.call("PUT", "/me/profile", body=self.p["profile"])
            elif kind in ("start_diagnostic", "continue_diagnostic"):
                self.diagnostic(base, name)
            elif kind == "wait_job":
                self.wait_job(action["job_id"], "en curso")
            elif kind == "confirm_objective":
                _, result = self.call("GET", f"{base}/diagnostic/result")
                obj = result["proposed_objective"] or {}
                self.call("PUT", f"{base}/objective", body={
                    "bloom_verb": obj.get("bloom_verb"), "content": obj.get("content"),
                    "criterion": obj.get("criterion")})
                levels = ", ".join(f"{t['name'][:25]} {t['level']:.0f}"
                                   for t in result["level_by_topic"])
                self.log(f"{name}: diagnóstico {result['overall_score']:.0f} % · {levels}")
            elif kind == "study_topic":
                self.study(base, int(action["step_id"]), enrollment_id)
            elif kind == "continue_attempt":
                step = action.get("step_id")
                tries[step] = tries.get(step, 0) + 1
                self.take_attempt(int(action["attempt_id"]), tries[step], step is None, name)
            elif kind == "view_attempt_result":
                attempt_id = int(action["attempt_id"])
                if attempt_id in seen_results:
                    raise RuntimeError(f"next_action repite view_attempt_result {attempt_id}")
                seen_results.add(attempt_id)
                self.call("GET", f"/me/attempts/{attempt_id}/result")
            elif kind == "wait_instructor":
                step_id = int(action["step_id"])
                http("POST", f"{self.api}/path-steps/{step_id}/attempt-grants", token=self.admin(),
                     body={"attempts": 1, "note": "Simulación: intento extra"})
                self.log(f"{name}: paso {step_id} agotado; el administrador habilita 1 intento")
            elif kind in ("take_final", "review_final"):
                if kind == "review_final":
                    self.call("GET", f"{base}/review-plan")
                status, data = self.call("POST", f"{base}/final-attempts", idempotent=True)
                if status == 202:  # sin preguntas no vistas: se generan más (B-011)
                    self.log(f"{name}: generando preguntas nuevas para la final")
                    self.wait_job(data["job_id"], "items.generate_final_bank")
            elif kind == "answer_survey":
                self.survey(base)
                self.log(f"{name}: encuesta final enviada")
            else:
                raise RuntimeError(f"next_action desconocido: {action}")
        raise RuntimeError(f"{name}: se superó el máximo de {MAX_LOOPS} pasos")

    def diagnostic(self, base: str, name: str) -> None:
        for wait in range(30):
            try:
                _, diag = self.call("POST", f"{base}/diagnostic")
                break
            except ApiError as exc:
                if exc.code == "DIAGNOSTIC_ALREADY_EXISTS":
                    _, diag = self.call("GET", f"{base}/diagnostic")
                    break
                if exc.code == "DIAGNOSTIC_BANK_EMPTY":
                    if wait == 0:
                        self.log(f"{name}: el banco del diagnóstico aún se genera; espero")
                    time.sleep(20)
                    continue
                raise
        else:
            raise TimeoutError("El banco del diagnóstico no estuvo listo en 10 minutos")
        skill = self.p["skill"]
        answers = [self.answer(i, skill, i.get("allows_dont_know", False)) for i in diag["items"]]
        self.call("PUT", f"{base}/diagnostic/answers", body={"answers": answers})
        _, job = self.call("POST", f"{base}/diagnostic/submit", idempotent=True)
        self.wait_job(job["job_id"], "diagnostic.finalize")

    def study(self, base: str, step_id: int, enrollment_id: int) -> None:
        _, content = self.call("GET", f"{base}/steps/{step_id}/content")
        video = content.get("video")
        if video and self.rng.random() < 0.8:
            rating = self.rng.choice(["useful", "useful", "useful", "too_long", "outdated"])
            try:
                self.call("POST", "/me/video-feedback", body={
                    "video_candidate_id": video["video_candidate_id"],
                    "enrollment_id": enrollment_id, "rating": rating, "comment": None,
                    "watched_fully": self.rng.random() < 0.7})
            except ApiError as exc:
                if exc.status != 409:
                    raise
        status, data = self.call("POST", f"{base}/steps/{step_id}/attempts",
                                 body={"assessment_type": "topic"}, idempotent=True)
        if status == 202:
            self.wait_job(data["job_id"], "items.generate_quiz_bank")

    def take_attempt(self, attempt_id: int, number: int, final: bool, name: str) -> None:
        _, attempt = self.call("GET", f"/me/attempts/{attempt_id}")
        # Cada reintento sube la probabilidad de acertar: el aprendiz estudió el repaso.
        skill = min(0.98, self.p["skill"] + 0.18 * (number - 1) + (0.08 if final else 0))
        answers = [self.answer(i, skill, False) for i in attempt["items"]]
        self.call("PUT", f"/me/attempts/{attempt_id}/answers", body={"answers": answers})
        status, data = self.call("POST", f"/me/attempts/{attempt_id}/submit", idempotent=True)
        if status == 202:
            self.wait_job(data["job_id"], "grading.short_answer")
            _, data = self.call("GET", f"/me/attempts/{attempt_id}/result")
        label = "final" if final else f"paso {attempt.get('step_id')}"
        verdict = "aprobado" if data["passed"] else "no aprobado"
        self.log(f"{name}: {label}, intento {number}: {data['score']:.0f} % ({verdict})")

    def survey(self, base: str) -> None:
        high = self.p["skill"] >= 0.6
        likert = {q: self.rng.choice([4, 5] if high else [3, 4]) for q in ("q1", "q2", "q3")}
        sus = [self.rng.choice([4, 5]) if i % 2 == 0 else self.rng.choice([1, 2])
               for i in range(10)]
        self.call("POST", f"{base}/surveys/final", body={
            "likert": likert, "sus_items": sus,
            "comment": "Simulación: la ruta me pareció clara." if high else None})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", type=int, action="append", help="aprendiz 1 a 4 (repetible)")
    parser.add_argument("--path", type=int, action="append", help="id de ruta (repetible)")
    args = parser.parse_args()

    env = load_env()
    password = env["SEED_USERS_PASSWORD"]
    api = f"http://localhost:{env.get('API_PORT', '8020')}/api/v1"
    kc = Keycloak(env)
    admin_cache: dict[str, Any] = {}

    def admin() -> str:
        """Token del administrador, renovado cada 4 min (el realm lo emite por 5)."""
        if time.monotonic() - admin_cache.get("at", -1e9) > 240:
            admin_cache.update(token=kc.token(env["SEED_ADMIN_EMAIL"], password),
                               at=time.monotonic())
        return str(admin_cache["token"])

    key = AnswerKey(api, admin)

    _, courses = http("GET", f"{api}/courses?status=published&limit=100", token=admin())
    paths: list[tuple[int, int, str]] = []
    for course in courses["items"]:
        lp = course.get("learning_path") or {}
        if course["status"] == "published" and lp.get("id"):
            if not args.path or lp["id"] in args.path:
                paths.append((int(course["id"]), int(lp["id"]), course["name"]))
    print("Rutas: " + "; ".join(f"{n} (ruta {p})" for _, p, n in paths), flush=True)

    summary: list[str] = []
    loaded_courses: set[int] = set()
    for index, persona in enumerate(PERSONAS, start=1):
        if args.only and index not in args.only:
            continue
        print(f"\n== Aprendiz {index}: {persona['first']} {persona['last']} "
              f"({persona['email']}, acierta {persona['skill']:.0%}) ==", flush=True)
        print(f"  Keycloak: {kc.ensure_learner(persona, password)}", flush=True)
        learner = Learner(persona, kc, password, api, key, admin)
        learner.setup()
        for course_id, path_id, name in paths:
            if course_id not in loaded_courses:
                _, topics = http("GET", f"{api}/courses/{course_id}/topics", token=admin())
                for topic in topics["topics"]:
                    key.load_topic(int(topic["id"]))
                loaded_courses.add(course_id)
            try:
                result = learner.run_enrollment(learner.enroll(path_id), name)
                summary.append(f"{persona['first']} · {name}: {result['status']}")
            except (ApiError, RuntimeError, TimeoutError) as exc:
                learner.log(f"{name}: ERROR {exc}")
                summary.append(f"{persona['first']} · {name}: ERROR {str(exc)[:150]}")
    print("\n== Resumen ==\n" + "\n".join(summary), flush=True)
    return 0 if not any("ERROR" in line for line in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
