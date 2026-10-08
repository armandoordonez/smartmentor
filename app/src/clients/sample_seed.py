"""Datos de ejemplo del prototipo de la Fase 0.

Reproducen la historia del diseño de Figma: Laura Martínez cursa «Fundamentos de Machine
Learning», la profesora Elena Ramírez es dueña de los cursos y un admin gestiona usuarios. Solo el
curso de ML tiene contenido completo (explicaciones, quizzes y evaluación final); los otros cursos
tienen temas y diagnóstico, como pasaría antes de que la capa de IA genere su contenido.

`build_seed()` devuelve un almacén nuevo cada vez: cada sesión de la interfaz trabaja sobre su
propia copia, así que lo que hace un usuario no afecta a otro.
"""

from dataclasses import dataclass, field
from datetime import date

from clients.models import (
    BloomLevel,
    CourseStatus,
    EmbeddingStatus,
    EnrollmentStatus,
    EvaluationMetric,
    LlmCall,
    LlmLog,
    PathSettings,
    QuestionKind,
    ReviewStatus,
    Role,
    StepStatus,
    User,
)


@dataclass
class SeedQuestion:
    id: int
    topic_id: int
    bloom_level: BloomLevel
    prompt: str
    options: tuple[str, ...]
    correct: int
    kind: QuestionKind = "multiple_choice"
    status: ReviewStatus = "approved"


@dataclass
class SeedTopic:
    id: int
    course_id: int
    order: int
    title: str
    bloom_level: BloomLevel
    estimated_minutes: int
    prerequisite_ids: tuple[int, ...] = ()
    embedding_status: EmbeddingStatus = "indexed"
    explanation: str | None = None
    explanation_version: str | None = None
    video_title: str | None = None
    video_minutes: int | None = None
    video_relevance: float | None = None


@dataclass
class SeedCourse:
    id: int
    owner_user_id: int
    title: str
    status: CourseStatus
    short_title: str
    level: str
    highlight: str | None = None
    syllabus_file: str | None = None
    syllabus_pages: int | None = None
    settings: PathSettings = field(
        default_factory=lambda: PathSettings(
            topic_threshold=0.7, final_threshold=0.8, max_attempts=3, skip_threshold=0.8
        )
    )


@dataclass
class SeedEnrollment:
    id: int
    user_id: int
    course_id: int
    status: EnrollmentStatus
    group: str
    enrolled_on: date
    profile_description: str | None = None
    personal_objective: str | None = None
    levels: dict[int, float] | None = None
    proposed_objective: str | None = None


@dataclass
class SeedStep:
    enrollment_id: int
    topic_id: int
    order: int
    status: StepStatus
    attempts_used: int = 0
    last_score: float | None = None
    diagnostic_score: float | None = None


@dataclass
class SeedAttempt:
    enrollment_id: int
    topic_id: int | None
    """None en la evaluación final."""
    attempt_number: int
    score: float
    passed: bool
    taken_on: date
    topic_scores: dict[int, float] = field(default_factory=dict)


@dataclass
class SeedBadge:
    enrollment_id: int
    issued_on: date
    final_score: float


@dataclass
class SeedResource:
    id: int
    topic_id: int
    label: str
    sources: str
    faithfulness: float | None
    status: ReviewStatus


@dataclass
class SampleStore:
    users: dict[int, User]
    courses: dict[int, SeedCourse]
    topics: dict[int, SeedTopic]
    diagnostic_questions: list[SeedQuestion]
    quiz_questions: list[SeedQuestion]
    final_questions: list[SeedQuestion]
    resources: list[SeedResource]
    enrollments: dict[int, SeedEnrollment]
    steps: list[SeedStep]
    attempts: list[SeedAttempt]
    badges: list[SeedBadge]
    llm_log: LlmLog
    metrics: list[EvaluationMetric]
    next_id: int = 1000

    def new_id(self) -> int:
        self.next_id += 1
        return self.next_id


DEMO_USER_BY_ROLE: dict[Role, int] = {"student": 1, "teacher": 2, "admin": 3}
"""Usuario con el que se entra en cada rol desde el selector (no hay login en el prototipo)."""


def _users() -> dict[int, User]:
    users = [
        User(
            id=1,
            full_name="Laura Martínez",
            email="laura.martinez@universidad.edu.co",
            roles=("student",),
        ),
        User(
            id=2,
            full_name="Elena Ramírez",
            email="elena.ramirez@universidad.edu.co",
            roles=("teacher",),
        ),
        User(id=3, full_name="Admin MSc", email="admin@universidad.edu.co", roles=("admin",)),
        User(
            id=4,
            full_name="Andrés Gómez",
            email="andres.gomez@universidad.edu.co",
            roles=("student",),
        ),
        User(
            id=5,
            full_name="Camila Rojas",
            email="camila.rojas@universidad.edu.co",
            roles=("student",),
        ),
        User(
            id=6,
            full_name="Julián Pérez",
            email="julian.perez@universidad.edu.co",
            roles=("student",),
            active=False,
        ),
        User(
            id=7,
            full_name="Ricardo Díaz",
            email="ricardo.diaz@universidad.edu.co",
            roles=("teacher",),
        ),
    ]
    return {user.id: user for user in users}


def _courses() -> dict[int, SeedCourse]:
    courses = [
        SeedCourse(
            id=1,
            owner_user_id=2,
            title="Fundamentos de Machine Learning",
            status="published",
            short_title="Fundamentos de ML",
            level="Intermedio",
            highlight="Recomendada para ti",
            syllabus_file="syllabus_ML_2026-2.pdf",
            syllabus_pages=12,
        ),
        SeedCourse(
            id=2,
            owner_user_id=2,
            title="Estadística para ciencia de datos",
            status="published",
            short_title="Estadística",
            level="Básico",
            highlight="Nueva",
            syllabus_file="syllabus_estadistica_2026-2.pdf",
            syllabus_pages=9,
        ),
        SeedCourse(
            id=3,
            owner_user_id=2,
            title="Python para análisis de datos",
            status="published",
            short_title="Python",
            level="Básico",
            highlight="Popular",
            syllabus_file="syllabus_python_2026-2.pdf",
            syllabus_pages=8,
        ),
        SeedCourse(
            id=4,
            owner_user_id=2,
            title="Series de tiempo",
            status="in_review",
            short_title="Series de tiempo",
            level="Intermedio",
            syllabus_file="syllabus_series_2026-2.pdf",
            syllabus_pages=10,
        ),
        SeedCourse(
            id=5,
            owner_user_id=7,
            title="Visualización de datos",
            status="draft",
            short_title="Visualización",
            level="Básico",
        ),
    ]
    return {course.id: course for course in courses}


def _topics() -> dict[int, SeedTopic]:
    topics = [
        # Fundamentos de Machine Learning
        SeedTopic(
            id=11,
            course_id=1,
            order=1,
            title="Introducción y tipos de aprendizaje",
            bloom_level="understand",
            estimated_minutes=80,
            explanation=(
                "El aprendizaje automático construye modelos que aprenden patrones a partir de "
                "datos. En el aprendizaje supervisado cada ejemplo trae la respuesta esperada "
                "(la etiqueta); en el no supervisado el modelo busca estructura sin etiquetas, y "
                "en el aprendizaje por refuerzo un agente aprende con recompensas. [1]"
            ),
            explanation_version="v1.1",
            video_title="Tipos de aprendizaje automático",
            video_minutes=9,
            video_relevance=0.91,
        ),
        SeedTopic(
            id=12,
            course_id=1,
            order=2,
            title="Regresión lineal",
            bloom_level="apply",
            estimated_minutes=60,
            prerequisite_ids=(11,),
            explanation=(
                "La regresión lineal modela una variable continua como una combinación lineal de "
                "las variables de entrada. Los coeficientes se estiman minimizando la suma de los "
                "errores al cuadrado, y el R² indica qué parte de la variabilidad explica el "
                "modelo. Compararlo en entrenamiento y en prueba revela el sobreajuste. [1][3]"
            ),
            explanation_version="v1.2",
            video_title="Regresión lineal paso a paso",
            video_minutes=12,
            video_relevance=0.89,
        ),
        SeedTopic(
            id=13,
            course_id=1,
            order=3,
            title="Regresión logística",
            bloom_level="apply",
            estimated_minutes=50,
            prerequisite_ids=(12,),
            explanation=(
                "La regresión logística estima la probabilidad de que una observación pertenezca "
                "a una clase. Aplica la función sigmoide a la combinación lineal de las variables "
                "y, con un umbral de 0,5, convierte la probabilidad en una clase. [1][2]"
            ),
            explanation_version="v1.3",
            video_title="Regresión logística",
            video_minutes=11,
            video_relevance=0.94,
        ),
        SeedTopic(
            id=14,
            course_id=1,
            order=4,
            title="Árboles de decisión",
            bloom_level="apply",
            estimated_minutes=45,
            prerequisite_ids=(11,),
            explanation=(
                "Un árbol de decisión divide los datos con preguntas sobre las variables hasta "
                "llegar a grupos homogéneos. Cada división se elige porque reduce la impureza "
                "(Gini o entropía). Son fáciles de interpretar, pero un árbol muy profundo "
                "sobreajusta; podarlo o combinar muchos árboles (bosque aleatorio) lo evita. [2]"
            ),
            explanation_version="v1.0",
            video_title="Árboles de decisión",
            video_minutes=10,
            video_relevance=0.88,
        ),
        SeedTopic(
            id=15,
            course_id=1,
            order=5,
            title="Evaluación de modelos",
            bloom_level="analyze",
            estimated_minutes=50,
            prerequisite_ids=(12, 13, 14),
            explanation=(
                "Un modelo se evalúa con datos que no vio al entrenar. La matriz de confusión "
                "cuenta aciertos y errores por clase; de ella salen la precisión, la sensibilidad "
                "y el F1. Con clases desbalanceadas la exactitud engaña: conviene mirar la "
                "sensibilidad o el AUC-ROC, que resume el desempeño en todos los umbrales. [2][3]"
            ),
            explanation_version="v1.0",
            video_title="Métricas de evaluación de clasificación",
            video_minutes=13,
            video_relevance=0.90,
        ),
        # Estadística para ciencia de datos
        SeedTopic(
            id=21,
            course_id=2,
            order=1,
            title="Estadística descriptiva",
            bloom_level="understand",
            estimated_minutes=60,
        ),
        SeedTopic(
            id=22,
            course_id=2,
            order=2,
            title="Probabilidad",
            bloom_level="apply",
            estimated_minutes=70,
            prerequisite_ids=(21,),
        ),
        SeedTopic(
            id=23,
            course_id=2,
            order=3,
            title="Distribuciones",
            bloom_level="understand",
            estimated_minutes=70,
            prerequisite_ids=(22,),
        ),
        SeedTopic(
            id=24,
            course_id=2,
            order=4,
            title="Inferencia e intervalos de confianza",
            bloom_level="apply",
            estimated_minutes=80,
            prerequisite_ids=(23,),
        ),
        SeedTopic(
            id=25,
            course_id=2,
            order=5,
            title="Pruebas de hipótesis",
            bloom_level="analyze",
            estimated_minutes=80,
            prerequisite_ids=(24,),
        ),
        # Python para análisis de datos
        SeedTopic(
            id=31,
            course_id=3,
            order=1,
            title="Sintaxis y estructuras de datos",
            bloom_level="remember",
            estimated_minutes=60,
        ),
        SeedTopic(
            id=32,
            course_id=3,
            order=2,
            title="NumPy",
            bloom_level="apply",
            estimated_minutes=75,
            prerequisite_ids=(31,),
        ),
        SeedTopic(
            id=33,
            course_id=3,
            order=3,
            title="pandas",
            bloom_level="apply",
            estimated_minutes=90,
            prerequisite_ids=(32,),
        ),
        SeedTopic(
            id=34,
            course_id=3,
            order=4,
            title="Visualización con matplotlib",
            bloom_level="apply",
            estimated_minutes=75,
            prerequisite_ids=(33,),
        ),
        # Series de tiempo (syllabus extraído, en revisión)
        SeedTopic(
            id=41,
            course_id=4,
            order=1,
            title="Componentes de una serie de tiempo",
            bloom_level="understand",
            estimated_minutes=60,
        ),
        SeedTopic(
            id=42,
            course_id=4,
            order=2,
            title="Suavizamiento exponencial",
            bloom_level="apply",
            estimated_minutes=70,
            prerequisite_ids=(41,),
        ),
        SeedTopic(
            id=43,
            course_id=4,
            order=3,
            title="Modelos ARIMA",
            bloom_level="apply",
            estimated_minutes=90,
            prerequisite_ids=(41, 42),
            embedding_status="pending",
        ),
        SeedTopic(
            id=44,
            course_id=4,
            order=4,
            title="Validación temporal",
            bloom_level="evaluate",
            estimated_minutes=60,
            prerequisite_ids=(43,),
            embedding_status="pending",
        ),
    ]
    return {topic.id: topic for topic in topics}


def _diagnostic_questions() -> list[SeedQuestion]:
    q = SeedQuestion
    return [
        q(
            101,
            11,
            "understand",
            "¿Qué tipo de aprendizaje usa datos con la respuesta esperada (etiqueta)?",
            ("Supervisado", "No supervisado", "Por refuerzo", "Ninguno"),
            0,
        ),
        q(
            102,
            11,
            "understand",
            "Agrupar clientes por su comportamiento de compra, sin etiquetas, es un problema de:",
            ("Clasificación", "Regresión", "Agrupamiento", "Refuerzo"),
            2,
        ),
        q(
            103,
            12,
            "apply",
            "Un modelo de regresión lineal obtiene R² = 0,92 en entrenamiento y "
            "0,41 en prueba. ¿Qué es lo más probable?",
            (
                "El modelo está sobreajustado a los datos de entrenamiento",
                "El modelo está subajustado y necesita más variables",
                "Es normal que el R² de prueba sea menor; no hay problema",
                "Los datos de prueba tienen errores de digitación",
            ),
            0,
        ),
        q(
            104,
            12,
            "apply",
            "En el modelo y = 3 + 2x, ¿cuánto cambia y si x aumenta en 1?",
            ("Aumenta 3", "Aumenta 2", "Aumenta 5", "No cambia"),
            1,
        ),
        q(
            105,
            13,
            "understand",
            "¿Para qué tipo de problema se usa la regresión logística?",
            (
                "Predecir un valor continuo",
                "Clasificar en categorías",
                "Agrupar datos sin etiquetas",
                "Reducir el número de variables",
            ),
            1,
        ),
        q(
            106,
            13,
            "understand",
            "La salida de la función sigmoide se interpreta como…",
            ("Una probabilidad", "Una distancia", "Un error", "Una categoría"),
            0,
        ),
        q(
            107,
            14,
            "understand",
            "¿Qué hace un árbol de decisión en cada nodo?",
            (
                "Divide los datos según una condición sobre una variable",
                "Promedia todas las variables",
                "Elimina los datos atípicos",
                "Normaliza los datos",
            ),
            0,
        ),
        q(
            108,
            14,
            "analyze",
            "Un árbol de decisión muy profundo tiende a…",
            ("Subajustar", "Sobreajustar", "No aprender nada", "Entrenar más rápido"),
            1,
        ),
        q(
            109,
            15,
            "understand",
            "¿Para qué sirve la validación cruzada?",
            (
                "Estimar el desempeño con datos no vistos",
                "Entrenar más rápido",
                "Eliminar variables",
                "Aumentar el R²",
            ),
            0,
        ),
        q(
            110,
            15,
            "analyze",
            "Si el 99 % de los datos es de una sola clase, una exactitud de 99 %…",
            (
                "Garantiza un buen modelo",
                "Puede ser engañosa",
                "Es imposible",
                "Indica sobreajuste",
            ),
            1,
        ),
        q(
            121,
            21,
            "understand",
            "¿Qué medida de tendencia central es más robusta a los valores atípicos?",
            ("La media", "La mediana", "La varianza", "El rango"),
            1,
        ),
        q(
            122,
            22,
            "apply",
            "Si lanzas dos veces una moneda justa, ¿cuál es la probabilidad de obtener dos caras?",
            ("1/2", "1/4", "1/3", "3/4"),
            1,
        ),
        q(
            123,
            23,
            "understand",
            "En una distribución normal, ¿qué parte de los datos queda a "
            "±1 desviación estándar de la media?",
            ("Cerca del 68 %", "El 50 %", "El 95 %", "El 99,7 %"),
            0,
        ),
        q(
            124,
            24,
            "apply",
            "Al aumentar el tamaño de la muestra, el intervalo de confianza…",
            ("Se hace más ancho", "Se hace más angosto", "No cambia", "Desaparece"),
            1,
        ),
        q(
            125,
            25,
            "analyze",
            "Con α = 0,05, un valor p de 0,03 indica que…",
            (
                "Se rechaza la hipótesis nula",
                "Se acepta la hipótesis nula",
                "El estudio falló",
                "α está mal elegido",
            ),
            0,
        ),
        q(
            131,
            31,
            "remember",
            "¿Qué estructura de Python no admite claves repetidas?",
            ("Lista", "Tupla", "Diccionario", "Cadena"),
            2,
        ),
        q(
            132,
            32,
            "apply",
            "¿Qué devuelve np.arange(3)?",
            ("[1, 2, 3]", "[0, 1, 2]", "[0, 1, 2, 3]", "3"),
            1,
        ),
        q(
            133,
            33,
            "apply",
            "¿Qué método de pandas agrupa filas para calcular resúmenes?",
            ("groupby", "merge", "pivot", "apply"),
            0,
        ),
        q(
            134,
            34,
            "apply",
            "¿Qué función de matplotlib dibuja un diagrama de dispersión?",
            ("plt.plot", "plt.bar", "plt.scatter", "plt.hist"),
            2,
        ),
    ]


def _quiz_questions() -> list[SeedQuestion]:
    q = SeedQuestion
    return [
        q(
            201,
            11,
            "understand",
            "¿Cuál es un ejemplo de aprendizaje supervisado?",
            (
                "Agrupar noticias por tema sin etiquetas",
                "Predecir el precio de una casa con ventas pasadas",
                "Un robot que aprende a caminar con recompensas",
            ),
            1,
        ),
        q(
            202,
            11,
            "remember",
            "En el aprendizaje no supervisado, los datos…",
            ("No tienen etiqueta", "Siempre tienen etiqueta", "Vienen de un simulador"),
            0,
        ),
        q(
            203,
            11,
            "understand",
            "¿Para qué se separan los datos de entrenamiento y de prueba?",
            (
                "Para entrenar más rápido",
                "Para no tener que limpiar los datos",
                "Para estimar cómo funciona el modelo con datos nuevos",
            ),
            2,
        ),
        q(
            211,
            12,
            "remember",
            "¿Qué minimiza el método de mínimos cuadrados?",
            ("La suma de los errores al cuadrado", "El número de variables", "El R²"),
            0,
        ),
        q(
            212,
            12,
            "understand",
            "Un R² de 0,85 significa que…",
            (
                "El 85 % de las predicciones son exactas",
                "El modelo explica el 85 % de la variabilidad de y",
                "El error promedio es 0,85",
            ),
            1,
        ),
        q(
            213,
            12,
            "apply",
            "¿Qué indica un coeficiente negativo en una regresión lineal?",
            (
                "Que la variable no importa",
                "Que el modelo está mal",
                "Que y disminuye cuando la variable aumenta",
            ),
            2,
        ),
        q(
            221,
            13,
            "remember",
            "¿Qué valores devuelve la función sigmoide?",
            ("Valores entre 0 y 1", "Valores entre −1 y 1", "Cualquier número real"),
            0,
        ),
        q(
            222,
            13,
            "apply",
            "Con un umbral de 0,5, una probabilidad de 0,7 se clasifica como…",
            ("Clase negativa", "Clase positiva", "Indeterminada"),
            1,
            status="pending",
        ),
        q(
            223,
            13,
            "apply",
            "¿Qué métrica conviene si los falsos negativos son costosos?",
            ("Exactitud", "Precisión", "Sensibilidad (recall)"),
            2,
            status="pending",
        ),
        q(
            224,
            13,
            "understand",
            "¿Cómo se interpreta un coeficiente positivo?",
            ("Aumenta la probabilidad de la clase positiva", "La disminuye", "No la afecta"),
            0,
        ),
        q(
            225,
            13,
            "analyze",
            "Explica por qué no usarías regresión lineal para clasificar.",
            (
                "Porque sus predicciones no quedan entre 0 y 1",
                "Porque es más lenta",
                "Porque necesita más datos",
            ),
            0,
            kind="short_answer",
            status="pending",
        ),
        q(
            231,
            14,
            "understand",
            "¿Qué mide el índice de Gini en un nodo?",
            ("La impureza de las clases", "La profundidad del árbol", "El número de variables"),
            0,
        ),
        q(
            232,
            14,
            "apply",
            "¿Qué técnica reduce el sobreajuste de un árbol?",
            (
                "Aumentar la profundidad",
                "Podar el árbol o limitar su profundidad",
                "Usar más variables",
            ),
            1,
        ),
        q(
            233,
            14,
            "understand",
            "Un bosque aleatorio combina…",
            (
                "Muchos árboles entrenados con muestras distintas",
                "Un árbol y una regresión",
                "Varias capas de neuronas",
            ),
            0,
        ),
        q(
            241,
            15,
            "understand",
            "¿Qué muestra una matriz de confusión?",
            (
                "La correlación entre variables",
                "Aciertos y errores por clase",
                "La curva de aprendizaje",
            ),
            1,
        ),
        q(
            242,
            15,
            "analyze",
            "Un AUC de 0,5 indica…",
            (
                "Un modelo perfecto",
                "Un modelo sobreajustado",
                "Un modelo que no es mejor que el azar",
            ),
            2,
        ),
        q(
            243,
            15,
            "remember",
            "¿Qué combina la métrica F1?",
            ("Precisión y sensibilidad", "Exactitud y error", "Sesgo y varianza"),
            0,
        ),
    ]


def _final_questions() -> list[SeedQuestion]:
    q = SeedQuestion
    # Dos preguntas por tema. La demo del prototipo («Ver resultado menor a 80 %») responde
    # siempre la primera opción: acierta 7 de 10 (70 %) y deja débiles los temas 3 y 5.
    return [
        q(
            301,
            11,
            "understand",
            "¿Qué distingue al aprendizaje supervisado?",
            (
                "Usa ejemplos con la respuesta esperada",
                "No necesita datos",
                "Solo sirve para imágenes",
                "Aprende solo con recompensas",
            ),
            0,
        ),
        q(
            302,
            11,
            "remember",
            "¿Qué conjunto de datos se usa para estimar el desempeño final?",
            ("El de prueba", "El de entrenamiento", "Ninguno", "Todos los datos juntos"),
            0,
        ),
        q(
            303,
            12,
            "understand",
            "¿Qué supone la regresión lineal sobre la relación entre x e y?",
            (
                "Que es aproximadamente lineal",
                "Que es exponencial",
                "Que no existe",
                "Que es categórica",
            ),
            0,
        ),
        q(
            304,
            12,
            "analyze",
            "Si el R² es alto en entrenamiento y bajo en prueba, el modelo…",
            ("Está sobreajustado", "Está subajustado", "Es perfecto", "Necesita más épocas"),
            0,
        ),
        q(
            305,
            13,
            "understand",
            "¿Qué rango de valores produce la regresión logística antes de aplicar el umbral?",
            ("Cualquier número real", "Entre 0 y 1", "Entre −1 y 1", "Solo 0 o 1"),
            1,
        ),
        q(
            306,
            13,
            "apply",
            "Si el umbral de clasificación baja de 0,5 a 0,3…",
            (
                "Bajan los positivos predichos",
                "Suben los positivos predichos",
                "No cambia nada",
                "El modelo se vuelve a entrenar",
            ),
            1,
        ),
        q(
            307,
            14,
            "understand",
            "¿Qué criterio usa un árbol para elegir una división?",
            (
                "La que más reduce la impureza",
                "La variable con más valores",
                "La primera variable del conjunto",
                "Una al azar",
            ),
            0,
        ),
        q(
            308,
            14,
            "remember",
            "¿Qué ventaja tienen los árboles de decisión?",
            (
                "Son fáciles de interpretar",
                "Nunca sobreajustan",
                "No necesitan datos",
                "Siempre son lineales",
            ),
            0,
        ),
        q(
            309,
            15,
            "analyze",
            "Un modelo de clasificación detecta fraude con 99 % de exactitud, "
            "pero casi nunca encuentra los fraudes. ¿Qué explica esto?",
            (
                "Las clases están muy desbalanceadas",
                "El modelo está subajustado",
                "La exactitud siempre es la mejor métrica",
                "El umbral debe ser 1,0",
            ),
            0,
        ),
        q(
            310,
            15,
            "understand",
            "¿Qué métrica resume el desempeño en todos los umbrales?",
            ("La exactitud", "El AUC-ROC", "El R²", "El error cuadrático medio"),
            1,
        ),
    ]


def _resources() -> list[SeedResource]:
    r = SeedResource
    return [
        r(501, 11, "Texto: explicación v1.1", "Apuntes unidad 1 · ISLR cap. 2", 0.88, "approved"),
        r(
            502,
            11,
            "Video: Tipos de aprendizaje automático (9 min)",
            "YouTube · relevancia 91 %",
            None,
            "approved",
        ),
        r(511, 12, "Texto: explicación v1.2", "Apuntes unidad 2 · ISLR cap. 3", 0.84, "approved"),
        r(
            512,
            12,
            "Video: Regresión lineal paso a paso (12 min)",
            "YouTube · relevancia 89 %",
            None,
            "approved",
        ),
        r(521, 13, "Texto: explicación v1.3", "Apuntes unidad 3 · ISLR cap. 4", 0.86, "approved"),
        r(522, 13, "Texto: explicación alterna", "Apuntes unidad 3", 0.81, "pending"),
        r(
            523,
            13,
            "Video: Regresión logística (11 min)",
            "YouTube · relevancia 94 %",
            None,
            "pending",
        ),
        r(531, 14, "Texto: explicación v1.0", "Apuntes unidad 4 · ISLR cap. 8", 0.83, "approved"),
        r(
            532,
            14,
            "Video: Árboles de decisión (10 min)",
            "YouTube · relevancia 88 %",
            None,
            "pending",
        ),
        r(541, 15, "Texto: explicación v1.0", "Apuntes unidad 5 · ISLR cap. 5", 0.79, "pending"),
        r(
            542,
            15,
            "Video: Métricas de evaluación de clasificación (13 min)",
            "YouTube · relevancia 90 %",
            None,
            "pending",
        ),
    ]


_LAURA_PROFILE = (
    "Soy ingeniera industrial y trabajo hace dos años como analista de datos. Uso Excel y SQL a "
    "diario y sé algo de Python (pandas). Nunca he entrenado un modelo de machine learning y "
    "quiero aprender a predecir la demanda de mi empresa."
)
_LAURA_OBJECTIVE = (
    "Aplicar regresión logística y árboles de decisión para predecir la demanda en un caso de tu "
    "empresa, logrando al menos 80 % en la evaluación final."
)


def _enrollments() -> dict[int, SeedEnrollment]:
    enrollments = [
        SeedEnrollment(
            id=1,
            user_id=1,
            course_id=1,
            status="in_progress",
            group="2026-2",
            enrolled_on=date(2026, 9, 28),
            profile_description=_LAURA_PROFILE,
            personal_objective=_LAURA_OBJECTIVE,
            levels={11: 0.92, 12: 0.64, 13: 0.38, 14: 0.25, 15: 0.45},
            proposed_objective=_LAURA_OBJECTIVE,
        ),
        SeedEnrollment(
            id=2,
            user_id=4,
            course_id=1,
            status="completed",
            group="2026-2",
            enrolled_on=date(2026, 9, 21),
            profile_description="Economista. Programa en R y quiere pasar a Python y ML.",
            personal_objective="Construir un modelo de riesgo de crédito y aprobar la final.",
            levels={11: 0.85, 12: 0.85, 13: 0.5, 14: 0.5, 15: 0.15},
        ),
        SeedEnrollment(
            id=3,
            user_id=5,
            course_id=1,
            status="in_progress",
            group="2026-2",
            enrolled_on=date(2026, 9, 30),
            profile_description="Diseñadora de producto que empieza en analítica.",
            personal_objective="Entender los modelos básicos para trabajar con el equipo de datos.",
            levels={11: 0.5, 12: 0.15, 13: 0.15, 14: 0.15, 15: 0.15},
        ),
        SeedEnrollment(
            id=4,
            user_id=6,
            course_id=1,
            status="abandoned",
            group="2026-2",
            enrolled_on=date(2026, 9, 22),
            profile_description="Ingeniero de sistemas.",
            personal_objective="Aprender regresión para un proyecto personal.",
            levels={11: 0.5, 12: 0.15, 13: 0.15, 14: 0.15, 15: 0.15},
        ),
    ]
    return {enrollment.id: enrollment for enrollment in enrollments}


def _steps() -> list[SeedStep]:
    s = SeedStep
    return [
        # Laura: el estado de la pantalla E5 de Figma.
        s(1, 11, 1, "skipped", diagnostic_score=0.92),
        s(1, 12, 2, "approved", attempts_used=1, last_score=0.85, diagnostic_score=0.64),
        s(1, 13, 3, "in_progress", attempts_used=1, last_score=0.6, diagnostic_score=0.38),
        s(1, 14, 4, "pending", diagnostic_score=0.25),
        s(1, 15, 5, "pending", diagnostic_score=0.45),
        # Andrés: ruta completa con badge.
        s(2, 11, 1, "skipped", diagnostic_score=0.85),
        s(2, 12, 2, "skipped", diagnostic_score=0.85),
        s(2, 13, 3, "approved", attempts_used=2, last_score=0.8, diagnostic_score=0.5),
        s(2, 14, 4, "approved", attempts_used=1, last_score=1.0, diagnostic_score=0.5),
        s(2, 15, 5, "approved", attempts_used=2, last_score=0.8, diagnostic_score=0.15),
        # Camila: en el segundo tema.
        s(3, 11, 1, "approved", attempts_used=1, last_score=1.0, diagnostic_score=0.5),
        s(3, 12, 2, "in_progress", attempts_used=1, last_score=0.55, diagnostic_score=0.15),
        s(3, 13, 3, "pending", diagnostic_score=0.15),
        s(3, 14, 4, "pending", diagnostic_score=0.15),
        s(3, 15, 5, "pending", diagnostic_score=0.15),
        # Julián: abandonó en el segundo tema.
        s(4, 11, 1, "approved", attempts_used=1, last_score=0.67, diagnostic_score=0.5),
        s(4, 12, 2, "in_progress", attempts_used=1, last_score=0.4, diagnostic_score=0.15),
        s(4, 13, 3, "pending", diagnostic_score=0.15),
        s(4, 14, 4, "pending", diagnostic_score=0.15),
        s(4, 15, 5, "pending", diagnostic_score=0.15),
    ]


def _attempts() -> list[SeedAttempt]:
    a = SeedAttempt
    return [
        a(1, 12, 1, 0.85, True, date(2026, 10, 3)),
        a(1, 13, 1, 0.6, False, date(2026, 10, 3)),
        a(2, 13, 1, 0.6, False, date(2026, 9, 25)),
        a(2, 13, 2, 0.8, True, date(2026, 9, 26)),
        a(2, 14, 1, 1.0, True, date(2026, 9, 29)),
        a(2, 15, 1, 0.67, False, date(2026, 10, 1)),
        a(2, 15, 2, 0.8, True, date(2026, 10, 2)),
        a(
            2,
            None,
            1,
            0.88,
            True,
            date(2026, 10, 5),
            topic_scores={11: 1.0, 12: 1.0, 13: 0.5, 14: 1.0, 15: 1.0},
        ),
        a(3, 11, 1, 1.0, True, date(2026, 10, 2)),
        a(3, 12, 1, 0.55, False, date(2026, 10, 4)),
        a(4, 11, 1, 0.67, False, date(2026, 9, 24)),
        a(4, 12, 1, 0.4, False, date(2026, 9, 26)),
    ]


def _llm_log() -> LlmLog:
    return LlmLog(
        period_days=7,
        calls=1284,
        total_cost_usd=4.12,
        p95_latency_seconds=11.8,
        invalid_json_rate=0.009,
        recent=(
            LlmCall(
                task="Quiz del tema",
                model="claude-sonnet",
                prompt_version="quiz_tema v1.2",
                tokens=2140,
                cost_usd=0.011,
                latency_seconds=8.2,
            ),
            LlmCall(
                task="Explicación (RAG)",
                model="claude-sonnet",
                prompt_version="explicacion_tema v1.3",
                tokens=3960,
                cost_usd=0.021,
                latency_seconds=12.4,
            ),
            LlmCall(
                task="Califica respuesta corta",
                model="claude-haiku",
                prompt_version="rubrica_corta v1.0",
                tokens=610,
                cost_usd=0.001,
                latency_seconds=2.1,
            ),
            LlmCall(
                task="Diagnóstico inicial",
                model="claude-sonnet",
                prompt_version="diagnostico v1.1",
                tokens=2870,
                cost_usd=0.015,
                latency_seconds=9.6,
            ),
            LlmCall(
                task="Estructura del syllabus",
                model="claude-sonnet",
                prompt_version="syllabus v2.0",
                tokens=8420,
                cost_usd=0.044,
                latency_seconds=18.3,
            ),
        ),
    )


def _metrics() -> list[EvaluationMetric]:
    # Metas del brief (proyecto/brief.md, sección de evaluación).
    m = EvaluationMetric
    return [
        m(
            key="syllabus_f1",
            label="F1 syllabus",
            value=0.87,
            target=0.85,
            comparison="gte",
            unit="ratio",
        ),
        m(
            key="cohen_kappa",
            label="Kappa de Cohen",
            value=0.64,
            target=0.6,
            comparison="gte",
            unit="ratio",
        ),
        m(
            key="rag_faithfulness",
            label="Fidelidad RAG",
            value=0.82,
            target=0.8,
            comparison="gte",
            unit="ratio",
        ),
        m(
            key="grading_qwk",
            label="QWK calificación",
            value=0.63,
            target=0.6,
            comparison="gte",
            unit="ratio",
        ),
        m(
            key="diagnostic_auc",
            label="AUC diagnóstico",
            value=0.66,
            target=0.7,
            comparison="gte",
            unit="ratio",
        ),
        m(key="sus", label="Usabilidad SUS", value=72, target=68, comparison="gte", unit="score"),
        m(
            key="hake_gain",
            label="Ganancia de Hake (g)",
            value=0.34,
            target=0.3,
            comparison="gte",
            unit="ratio",
        ),
        m(
            key="attempts_per_topic",
            label="Intentos por tema",
            value=1.6,
            target=1.8,
            comparison="lte",
            unit="count",
        ),
        m(
            key="cost_per_student_path",
            label="Costo por estudiante-ruta",
            value=0.23,
            target=None,
            comparison="report",
            unit="usd",
        ),
    ]


def build_seed() -> SampleStore:
    return SampleStore(
        users=_users(),
        courses=_courses(),
        topics=_topics(),
        diagnostic_questions=_diagnostic_questions(),
        quiz_questions=_quiz_questions(),
        final_questions=_final_questions(),
        resources=_resources(),
        enrollments=_enrollments(),
        steps=_steps(),
        attempts=_attempts(),
        badges=[SeedBadge(enrollment_id=2, issued_on=date(2026, 10, 5), final_score=0.88)],
        llm_log=_llm_log(),
        metrics=_metrics(),
    )
