"""Cliente con datos de ejemplo (`APP_DATA_SOURCE=sample`).

Hace de API falsa para el prototipo de la Fase 0, la prueba de usabilidad y las pruebas: responde
con los mismos modelos y aplica, de forma simplificada, las reglas que en producción aplica la API
(roles, pertenencia, umbrales, intentos y omisión de temas dominados). Por eso las reglas viven
aquí y no en `services/`: cuando se use la API real, este archivo deja de usarse y nada más cambia.
"""

from datetime import date
from statistics import mean

from clients.base import Answers, ApiError
from clients.models import (
    AnswerReview,
    AttemptRecord,
    Badge,
    BankQuestion,
    ContentResource,
    Course,
    Diagnostic,
    Enrollment,
    EvaluationMetric,
    FinalAssessment,
    FinalResult,
    LearningPath,
    LlmLog,
    PathDashboard,
    PathProgress,
    PathSettings,
    PathStep,
    Question,
    Quiz,
    QuizResult,
    ReviewStatus,
    Role,
    StepStatus,
    StudentDetail,
    StudentProgressRow,
    Topic,
    TopicContent,
    TopicLevel,
    TopicLevelStatus,
    TopicScore,
    User,
    VideoResource,
)
from clients.sample_seed import (
    SampleStore,
    SeedAttempt,
    SeedBadge,
    SeedCourse,
    SeedEnrollment,
    SeedQuestion,
    SeedStep,
    SeedTopic,
)

_PROFILE_SIGNAL = 0.5
"""Señal del perfil por tema. En el piloto la calcula la IA a partir de la descripción."""

_ACTIVE_STATUSES = ("onboarding", "in_progress")


class SampleDataClient:
    def __init__(self, store: SampleStore, user_id: int) -> None:
        self._store = store
        self._user_id = user_id

    # --- utilidades ----------------------------------------------------------------------------
    @property
    def _user(self) -> User:
        return self._store.users[self._user_id]

    def _require_role(self, *roles: Role) -> None:
        if not set(roles) & set(self._user.roles):
            raise ApiError(403, "INSUFFICIENT_ROLE", "El rol no permite esta operación")

    def _is_admin(self) -> bool:
        return "admin" in self._user.roles

    def _own_enrollment(self, enrollment_id: int) -> SeedEnrollment:
        enrollment = self._store.enrollments.get(enrollment_id)
        if enrollment is None or enrollment.user_id != self._user_id:
            raise ApiError(404, "NOT_FOUND", "Inscripción no encontrada")
        return enrollment

    def _own_course(self, course_id: int) -> SeedCourse:
        self._require_role("teacher", "admin")
        course = self._store.courses.get(course_id)
        if course is None or (course.owner_user_id != self._user_id and not self._is_admin()):
            raise ApiError(404, "NOT_FOUND", "Curso no encontrado")
        return course

    def _course_topics(self, course_id: int) -> list[SeedTopic]:
        topics = [t for t in self._store.topics.values() if t.course_id == course_id]
        return sorted(topics, key=lambda t: t.order)

    def _steps(self, enrollment_id: int) -> list[SeedStep]:
        steps = [s for s in self._store.steps if s.enrollment_id == enrollment_id]
        return sorted(steps, key=lambda s: s.order)

    def _step(self, enrollment_id: int, topic_id: int) -> SeedStep:
        for step in self._steps(enrollment_id):
            if step.topic_id == topic_id:
                return step
        raise ApiError(404, "NOT_FOUND", "El tema no es parte de tu ruta")

    def _final_attempts(self, enrollment_id: int) -> list[SeedAttempt]:
        return [
            a
            for a in self._store.attempts
            if a.enrollment_id == enrollment_id and a.topic_id is None
        ]

    def _has_badge(self, enrollment_id: int) -> bool:
        return any(b.enrollment_id == enrollment_id for b in self._store.badges)

    def _final_available(self, enrollment: SeedEnrollment) -> bool:
        steps = self._steps(enrollment.id)
        settings = self._store.courses[enrollment.course_id].settings
        return (
            enrollment.status == "in_progress"
            and bool(steps)
            and all(s.status in ("skipped", "approved") for s in steps)
            and len(self._final_attempts(enrollment.id)) < settings.max_attempts
            and not self._has_badge(enrollment.id)
            and any(q.topic_id in {s.topic_id for s in steps} for q in self._store.final_questions)
        )

    @staticmethod
    def _question(seed: SeedQuestion) -> Question:
        return Question(
            id=seed.id,
            topic_id=seed.topic_id,
            bloom_level=seed.bloom_level,
            prompt=seed.prompt,
            options=seed.options,
            kind=seed.kind,
        )

    @staticmethod
    def _grade(questions: list[SeedQuestion], answers: Answers) -> list[bool]:
        return [answers.get(q.id) == q.correct for q in questions]

    @staticmethod
    def _level_status(score: float, skip_threshold: float) -> TopicLevelStatus:
        if score >= skip_threshold:
            return "mastered"
        return "reinforce" if score >= 0.5 else "learn"

    def _topic(self, topic: SeedTopic) -> Topic:
        return Topic(
            id=topic.id,
            course_id=topic.course_id,
            order=topic.order,
            title=topic.title,
            bloom_level=topic.bloom_level,
            prerequisite_ids=topic.prerequisite_ids,
            estimated_minutes=topic.estimated_minutes,
            embedding_status=topic.embedding_status,
        )

    def _enrollment(self, enrollment: SeedEnrollment) -> Enrollment:
        return Enrollment(
            id=enrollment.id,
            user_id=enrollment.user_id,
            learning_path_id=enrollment.course_id,
            status=enrollment.status,
            group=enrollment.group,
            enrolled_on=enrollment.enrolled_on,
            profile_description=enrollment.profile_description,
            personal_objective=enrollment.personal_objective,
        )

    def _levels(self, enrollment: SeedEnrollment) -> tuple[TopicLevel, ...]:
        if enrollment.levels is None:
            return ()
        skip = self._store.courses[enrollment.course_id].settings.skip_threshold
        return tuple(
            TopicLevel(
                topic_id=topic.id,
                topic_title=topic.title,
                score=enrollment.levels[topic.id],
                status=self._level_status(enrollment.levels[topic.id], skip),
            )
            for topic in self._course_topics(enrollment.course_id)
            if topic.id in enrollment.levels
        )

    def _saved_minutes(self, enrollment_id: int) -> int:
        return sum(
            self._store.topics[s.topic_id].estimated_minutes
            for s in self._steps(enrollment_id)
            if s.status == "skipped"
        )

    # --- identidad -----------------------------------------------------------------------------
    def me(self) -> User:
        return self._user

    # --- catálogo ------------------------------------------------------------------------------
    def _learning_path(self, course: SeedCourse) -> LearningPath:
        topics = self._course_topics(course.id)
        return LearningPath(
            id=course.id,
            course_id=course.id,
            title=course.title,
            short_title=course.short_title,
            level=course.level,
            estimated_hours=round(sum(t.estimated_minutes for t in topics) / 60),
            highlight=course.highlight,
            topic_count=len(topics),
        )

    def list_learning_paths(self) -> list[LearningPath]:
        return [
            self._learning_path(course)
            for course in self._store.courses.values()
            if course.status == "published"
        ]

    def get_learning_path(self, learning_path_id: int) -> LearningPath:
        course = self._store.courses.get(learning_path_id)
        if course is None or course.status != "published":
            raise ApiError(404, "NOT_FOUND", "Ruta no encontrada")
        return self._learning_path(course)

    def list_topics(self, course_id: int) -> list[Topic]:
        return [self._topic(t) for t in self._course_topics(course_id)]

    # --- estudiante: inscripción y diagnóstico ---------------------------------------------------
    def list_my_enrollments(self) -> list[Enrollment]:
        return [
            self._enrollment(e)
            for e in self._store.enrollments.values()
            if e.user_id == self._user_id
        ]

    def enroll(self, learning_path_id: int, profile_description: str) -> Enrollment:
        self.get_learning_path(learning_path_id)
        for enrollment in self._store.enrollments.values():
            if (
                enrollment.user_id == self._user_id
                and enrollment.course_id == learning_path_id
                and enrollment.status in _ACTIVE_STATUSES
            ):
                raise ApiError(409, "ALREADY_ENROLLED", "Ya estás inscrito en esta ruta")
        enrollment = SeedEnrollment(
            id=self._store.new_id(),
            user_id=self._user_id,
            course_id=learning_path_id,
            status="onboarding",
            group="2026-2",
            enrolled_on=date.today(),
            profile_description=profile_description.strip() or None,
        )
        self._store.enrollments[enrollment.id] = enrollment
        return self._enrollment(enrollment)

    def _diagnostic_questions(self, course_id: int) -> list[SeedQuestion]:
        topic_ids = {t.id for t in self._course_topics(course_id)}
        return [q for q in self._store.diagnostic_questions if q.topic_id in topic_ids]

    def get_diagnostic(self, enrollment_id: int) -> Diagnostic:
        enrollment = self._own_enrollment(enrollment_id)
        return Diagnostic(
            enrollment_id=enrollment.id,
            questions=tuple(
                self._question(q) for q in self._diagnostic_questions(enrollment.course_id)
            ),
            submitted=enrollment.levels is not None,
            levels=self._levels(enrollment),
            proposed_objective=enrollment.proposed_objective,
        )

    def submit_diagnostic(self, enrollment_id: int, answers: Answers) -> Diagnostic:
        enrollment = self._own_enrollment(enrollment_id)
        if enrollment.levels is not None:
            raise ApiError(409, "ALREADY_SUBMITTED", "Ya entregaste el diagnóstico")
        questions = self._diagnostic_questions(enrollment.course_id)
        weight = 0.7
        levels: dict[int, float] = {}
        for topic in self._course_topics(enrollment.course_id):
            topic_questions = [q for q in questions if q.topic_id == topic.id]
            if not topic_questions:
                continue
            diagnostic_score = mean(self._grade(topic_questions, answers))
            levels[topic.id] = round(weight * diagnostic_score + (1 - weight) * _PROFILE_SIGNAL, 2)
        enrollment.levels = levels
        skip = self._store.courses[enrollment.course_id].settings.skip_threshold
        to_learn = [
            self._store.topics[topic_id].title.lower()
            for topic_id, score in levels.items()
            if score < skip
        ]
        target = (
            ", ".join(to_learn[:-1]) + f" y {to_learn[-1]}"
            if len(to_learn) > 1
            else (to_learn[0] if to_learn else "todos los temas")
        )
        enrollment.proposed_objective = (
            f"Dominar {target} y aplicarlos en un caso real, logrando al menos 80 % en la "
            "evaluación final."
        )
        return self.get_diagnostic(enrollment_id)

    def confirm_objective(self, enrollment_id: int, personal_objective: str) -> Enrollment:
        enrollment = self._own_enrollment(enrollment_id)
        if enrollment.levels is None:
            raise ApiError(409, "DIAGNOSTIC_REQUIRED", "Primero completa el diagnóstico")
        enrollment.personal_objective = personal_objective.strip() or enrollment.proposed_objective
        if enrollment.status == "onboarding":
            enrollment.status = "in_progress"
            skip = self._store.courses[enrollment.course_id].settings.skip_threshold
            current_assigned = False
            for topic in self._course_topics(enrollment.course_id):
                score = enrollment.levels.get(topic.id, 0.0)
                status: StepStatus
                if score >= skip:
                    status = "skipped"
                elif not current_assigned:
                    status, current_assigned = "in_progress", True
                else:
                    status = "pending"
                self._store.steps.append(
                    SeedStep(enrollment.id, topic.id, topic.order, status, diagnostic_score=score)
                )
        return self._enrollment(enrollment)

    # --- estudiante: ruta, temas y evaluaciones --------------------------------------------------
    def get_path_progress(self, enrollment_id: int) -> PathProgress:
        enrollment = self._own_enrollment(enrollment_id)
        return PathProgress(
            enrollment_id=enrollment.id,
            learning_path_id=enrollment.course_id,
            steps=tuple(
                PathStep(
                    topic_id=s.topic_id,
                    order=s.order,
                    status=s.status,
                    attempts_used=s.attempts_used,
                    last_score=s.last_score,
                    diagnostic_score=s.diagnostic_score,
                )
                for s in self._steps(enrollment.id)
            ),
            final_available=self._final_available(enrollment),
            final_passed=self._has_badge(enrollment.id),
            saved_minutes=self._saved_minutes(enrollment.id),
            settings=self._store.courses[enrollment.course_id].settings,
        )

    def get_topic_content(self, topic_id: int) -> TopicContent:
        topic = self._store.topics.get(topic_id)
        if topic is None:
            raise ApiError(404, "NOT_FOUND", "Tema no encontrado")
        video = None
        if topic.video_title and topic.video_minutes and topic.video_relevance:
            video = VideoResource(
                title=topic.video_title,
                duration_minutes=topic.video_minutes,
                relevance=topic.video_relevance,
            )
        provenance = None
        if topic.explanation_version:
            provenance = (
                "Texto generado con IA a partir de fuentes verificadas y revisado por tu docente"
                f" · prompt explicacion_tema {topic.explanation_version}"
            )
        return TopicContent(
            topic_id=topic.id, explanation=topic.explanation, provenance=provenance, video=video
        )

    def _quiz_questions(self, topic_id: int) -> list[SeedQuestion]:
        return [
            q
            for q in self._store.quiz_questions
            if q.topic_id == topic_id and q.status != "retired" and q.kind == "multiple_choice"
        ]

    def get_topic_quiz(self, enrollment_id: int, topic_id: int) -> Quiz:
        enrollment = self._own_enrollment(enrollment_id)
        step = self._step(enrollment.id, topic_id)
        settings = self._store.courses[enrollment.course_id].settings
        return Quiz(
            topic_id=topic_id,
            questions=tuple(self._question(q) for q in self._quiz_questions(topic_id)),
            attempt_number=min(step.attempts_used + 1, settings.max_attempts),
            max_attempts=settings.max_attempts,
            threshold=settings.topic_threshold,
        )

    def submit_topic_quiz(self, enrollment_id: int, topic_id: int, answers: Answers) -> QuizResult:
        enrollment = self._own_enrollment(enrollment_id)
        step = self._step(enrollment.id, topic_id)
        settings = self._store.courses[enrollment.course_id].settings
        if step.status != "approved" and step.attempts_used >= settings.max_attempts:
            raise ApiError(409, "NO_ATTEMPTS_LEFT", "Ya usaste todos los intentos de este tema")
        questions = self._quiz_questions(topic_id)
        if not questions:
            raise ApiError(409, "QUIZ_NOT_READY", "Este tema todavía no tiene quiz")
        results = self._grade(questions, answers)
        score = round(sum(results) / len(results), 2)
        passed = score >= settings.topic_threshold
        step.attempts_used += 1
        step.last_score = score
        self._store.attempts.append(
            SeedAttempt(enrollment.id, topic_id, step.attempts_used, score, passed, date.today())
        )
        if passed and step.status != "approved":
            step.status = "approved"
            steps = self._steps(enrollment.id)
            if not any(s.status == "in_progress" for s in steps):
                for next_step in steps:
                    if next_step.status == "pending":
                        next_step.status = "in_progress"
                        break
        elif step.status == "pending":
            step.status = "in_progress"
        return QuizResult(
            topic_id=topic_id,
            score=score,
            correct_count=sum(results),
            total=len(results),
            threshold=settings.topic_threshold,
            passed=passed,
            attempt_number=step.attempts_used,
            max_attempts=settings.max_attempts,
            reviews=tuple(
                AnswerReview(number=i, prompt=q.prompt, correct=ok)
                for i, (q, ok) in enumerate(zip(questions, results, strict=True), start=1)
            ),
        )

    def _final_questions(self, course_id: int) -> list[SeedQuestion]:
        topic_ids = {t.id for t in self._course_topics(course_id)}
        return [q for q in self._store.final_questions if q.topic_id in topic_ids]

    def get_final_assessment(self, enrollment_id: int) -> FinalAssessment:
        enrollment = self._own_enrollment(enrollment_id)
        if not self._final_available(enrollment):
            raise ApiError(409, "FINAL_LOCKED", "La evaluación final todavía no está habilitada")
        settings = self._store.courses[enrollment.course_id].settings
        return FinalAssessment(
            learning_path_id=enrollment.course_id,
            questions=tuple(self._question(q) for q in self._final_questions(enrollment.course_id)),
            attempt_number=len(self._final_attempts(enrollment.id)) + 1,
            max_attempts=settings.max_attempts,
            threshold=settings.final_threshold,
        )

    def _final_result(self, enrollment: SeedEnrollment, attempt: SeedAttempt) -> FinalResult:
        settings = self._store.courses[enrollment.course_id].settings
        topic_scores = tuple(
            TopicScore(
                topic_id=topic_id, topic_title=self._store.topics[topic_id].title, score=score
            )
            for topic_id, score in attempt.topic_scores.items()
        )
        return FinalResult(
            enrollment_id=enrollment.id,
            score=attempt.score,
            passed=attempt.passed,
            threshold=settings.final_threshold,
            attempt_number=attempt.attempt_number,
            max_attempts=settings.max_attempts,
            topic_scores=topic_scores,
            weak_topics=tuple(t for t in topic_scores if t.score < settings.final_threshold),
        )

    def submit_final_assessment(self, enrollment_id: int, answers: Answers) -> FinalResult:
        enrollment = self._own_enrollment(enrollment_id)
        assessment = self.get_final_assessment(enrollment_id)
        questions = self._final_questions(enrollment.course_id)
        results = self._grade(questions, answers)
        score = round(sum(results) / len(results), 2)
        passed = score >= assessment.threshold
        topic_scores: dict[int, float] = {}
        for topic in self._course_topics(enrollment.course_id):
            topic_results = [
                ok for q, ok in zip(questions, results, strict=True) if q.topic_id == topic.id
            ]
            if topic_results:
                topic_scores[topic.id] = round(mean(topic_results), 2)
        attempt = SeedAttempt(
            enrollment.id,
            None,
            assessment.attempt_number,
            score,
            passed,
            date.today(),
            topic_scores=topic_scores,
        )
        self._store.attempts.append(attempt)
        if passed:
            enrollment.status = "completed"
            self._store.badges.append(SeedBadge(enrollment.id, date.today(), score))
        return self._final_result(enrollment, attempt)

    def list_final_results(self, enrollment_id: int) -> list[FinalResult]:
        enrollment = self._own_enrollment(enrollment_id)
        return [self._final_result(enrollment, a) for a in self._final_attempts(enrollment.id)]

    def list_my_badges(self) -> list[Badge]:
        badges = []
        for badge in self._store.badges:
            enrollment = self._store.enrollments[badge.enrollment_id]
            if enrollment.user_id != self._user_id:
                continue
            course = self._store.courses[enrollment.course_id]
            steps = self._steps(enrollment.id)
            badges.append(
                Badge(
                    enrollment_id=enrollment.id,
                    learning_path_id=course.id,
                    path_title=course.title,
                    issued_on=badge.issued_on,
                    final_score=badge.final_score,
                    mastered_topics=sum(s.status in ("skipped", "approved") for s in steps),
                    total_topics=len(steps),
                    saved_minutes=self._saved_minutes(enrollment.id),
                    verification_url=f"https://smartmentor.example/badges/{enrollment.id}",
                )
            )
        return badges

    # --- docente -------------------------------------------------------------------------------
    def _course(self, course: SeedCourse) -> Course:
        return Course(
            id=course.id,
            owner_user_id=course.owner_user_id,
            title=course.title,
            status=course.status,
            syllabus_file=course.syllabus_file,
            syllabus_pages=course.syllabus_pages,
            topic_count=len(self._course_topics(course.id)),
            enrolled_count=sum(
                1 for e in self._store.enrollments.values() if e.course_id == course.id
            ),
        )

    def list_my_courses(self) -> list[Course]:
        self._require_role("teacher", "admin")
        return [
            self._course(c)
            for c in self._store.courses.values()
            if c.owner_user_id == self._user_id or self._is_admin()
        ]

    def create_course(self, title: str) -> Course:
        self._require_role("teacher", "admin")
        if not title.strip():
            raise ApiError(422, "VALIDATION_ERROR", "El nombre del curso es obligatorio")
        course = SeedCourse(
            id=self._store.new_id(),
            owner_user_id=self._user_id,
            title=title.strip(),
            status="draft",
            short_title=title.strip(),
            level="Básico",
        )
        self._store.courses[course.id] = course
        return self._course(course)

    def get_course(self, course_id: int) -> Course:
        return self._course(self._own_course(course_id))

    def publish_course(self, course_id: int) -> Course:
        course = self._own_course(course_id)
        if course.status != "in_review" or not self._course_topics(course_id):
            raise ApiError(409, "SYLLABUS_REQUIRED", "Solo se publica un syllabus en revisión")
        course.status = "published"
        course.highlight = "Nueva"
        for topic in self._course_topics(course_id):
            topic.embedding_status = "indexed"
        return self._course(course)

    def get_path_dashboard(self, course_id: int) -> PathDashboard:
        course = self._own_course(course_id)
        enrollments = [e for e in self._store.enrollments.values() if e.course_id == course_id]
        rows = []
        for enrollment in enrollments:
            steps = self._steps(enrollment.id)
            current = next((s for s in steps if s.status == "in_progress"), None)
            last_final = self._final_attempts(enrollment.id)
            last_score = (
                last_final[-1].score if last_final else current.last_score if current else None
            )
            rows.append(
                StudentProgressRow(
                    user_id=enrollment.user_id,
                    full_name=self._store.users[enrollment.user_id].full_name,
                    enrollment_status=enrollment.status,
                    completed_topics=sum(s.status in ("skipped", "approved") for s in steps),
                    total_topics=len(steps),
                    current_topic=self._store.topics[current.topic_id].title if current else None,
                    last_score=last_score,
                    has_badge=self._has_badge(enrollment.id),
                )
            )
        approved = [s for e in enrollments for s in self._steps(e.id) if s.status == "approved"]
        return PathDashboard(
            course_id=course.id,
            learning_path_id=course.id,
            path_title=course.title,
            group="2026-2",
            settings=course.settings,
            enrolled=len(enrollments),
            completion_rate=(
                sum(e.status == "completed" for e in enrollments) / len(enrollments)
                if enrollments
                else 0.0
            ),
            badges_issued=sum(self._has_badge(e.id) for e in enrollments),
            attempts_per_topic=(
                round(mean(s.attempts_used for s in approved), 1) if approved else 0.0
            ),
            students=tuple(rows),
        )

    def update_path_settings(self, course_id: int, settings: PathSettings) -> PathSettings:
        course = self._own_course(course_id)
        course.settings = settings
        return settings

    def get_student_detail(self, course_id: int, user_id: int) -> StudentDetail:
        course = self._own_course(course_id)
        enrollment = next(
            (
                e
                for e in self._store.enrollments.values()
                if e.course_id == course_id and e.user_id == user_id
            ),
            None,
        )
        if enrollment is None:
            raise ApiError(404, "NOT_FOUND", "El estudiante no está inscrito en esta ruta")
        attempts = tuple(
            AttemptRecord(
                topic_title=(
                    self._store.topics[a.topic_id].title if a.topic_id else "Evaluación final"
                ),
                attempt_number=a.attempt_number,
                score=a.score,
                passed=a.passed,
                taken_on=a.taken_on,
            )
            for a in self._store.attempts
            if a.enrollment_id == enrollment.id
        )
        return StudentDetail(
            user=self._store.users[user_id],
            course_id=course.id,
            path_title=course.title,
            group=enrollment.group,
            enrollment_status=enrollment.status,
            profile_description=enrollment.profile_description,
            personal_objective=enrollment.personal_objective,
            levels=self._levels(enrollment),
            attempts=attempts,
        )

    def _owned_topic(self, topic_id: int) -> SeedTopic:
        topic = self._store.topics.get(topic_id)
        if topic is None:
            raise ApiError(404, "NOT_FOUND", "Tema no encontrado")
        self._own_course(topic.course_id)
        return topic

    def list_topic_resources(self, topic_id: int) -> list[ContentResource]:
        self._owned_topic(topic_id)
        return [
            ContentResource(
                id=r.id,
                topic_id=r.topic_id,
                label=r.label,
                sources=r.sources,
                faithfulness=r.faithfulness,
                status=r.status,
            )
            for r in self._store.resources
            if r.topic_id == topic_id
        ]

    def list_topic_questions(self, topic_id: int) -> list[BankQuestion]:
        self._owned_topic(topic_id)
        return [
            BankQuestion(
                id=q.id,
                topic_id=q.topic_id,
                prompt=q.prompt,
                bloom_level=q.bloom_level,
                kind=q.kind,
                status=q.status,
            )
            for q in self._store.quiz_questions
            if q.topic_id == topic_id
        ]

    def set_resource_status(self, resource_id: int, status: ReviewStatus) -> ContentResource:
        resource = next((r for r in self._store.resources if r.id == resource_id), None)
        if resource is None:
            raise ApiError(404, "NOT_FOUND", "Recurso no encontrado")
        self._owned_topic(resource.topic_id)
        resource.status = status
        return next(r for r in self.list_topic_resources(resource.topic_id) if r.id == resource_id)

    def set_question_status(self, question_id: int, status: ReviewStatus) -> BankQuestion:
        question = next((q for q in self._store.quiz_questions if q.id == question_id), None)
        if question is None:
            raise ApiError(404, "NOT_FOUND", "Pregunta no encontrada")
        self._owned_topic(question.topic_id)
        question.status = status
        return next(q for q in self.list_topic_questions(question.topic_id) if q.id == question_id)

    # --- administración ------------------------------------------------------------------------
    def list_users(self) -> list[User]:
        self._require_role("admin")
        return list(self._store.users.values())

    def create_user(self, full_name: str, email: str, role: Role) -> User:
        self._require_role("admin")
        email = email.strip().lower()
        if not full_name.strip() or "@" not in email:
            raise ApiError(422, "VALIDATION_ERROR", "Nombre y correo válidos son obligatorios")
        if any(u.email == email for u in self._store.users.values()):
            raise ApiError(409, "EMAIL_TAKEN", "Ya existe un usuario con ese correo")
        user = User(
            id=self._store.new_id(), full_name=full_name.strip(), email=email, roles=(role,)
        )
        self._store.users[user.id] = user
        return user

    def _editable_user(self, user_id: int) -> User:
        self._require_role("admin")
        user = self._store.users.get(user_id)
        if user is None:
            raise ApiError(404, "NOT_FOUND", "Usuario no encontrado")
        if user_id == self._user_id:
            raise ApiError(403, "SELF_EDIT_FORBIDDEN", "Solo otro admin puede editar tu cuenta")
        return user

    def set_user_role(self, user_id: int, role: Role) -> User:
        user = self._editable_user(user_id).model_copy(update={"roles": (role,)})
        self._store.users[user_id] = user
        return user

    def set_user_active(self, user_id: int, active: bool) -> User:
        user = self._editable_user(user_id).model_copy(update={"active": active})
        self._store.users[user_id] = user
        return user

    def get_llm_log(self) -> LlmLog:
        self._require_role("admin")
        return self._store.llm_log

    def list_evaluation_metrics(self) -> list[EvaluationMetric]:
        self._require_role("admin")
        return list(self._store.metrics)
