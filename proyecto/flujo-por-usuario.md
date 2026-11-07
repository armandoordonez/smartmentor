# Flujo del prototipo por tipo de usuario

Cada paso indica dónde se aplica el aporte de ciencia de datos del proyecto (ver [brief.md](brief.md)):

- 🔵 **P1 · Modelo de diagnóstico:** estimar el nivel del estudiante por tema.
- 🟠 **P2 · Motor de ruta:** seleccionar y secuenciar recursos según la brecha detectada.
- 🟢 **P3 · Evaluación de la calidad de la IA:** medir rigurosamente lo que genera la IA.

La columna **Objetivo** indica el objetivo específico del brief (OE1 a OE5, ver el cruce al final). **OE3\*** marca los pasos de secuenciación de la ruta, que ningún objetivo nombra hoy. Los pasos sin marca son infraestructura o interfaz y no forman parte del aporte.

## Estudiante

| # | Paso | Objetivo | Aporte |
| --- | --- | --- | --- |
| 1 | **Login:** entra con su cuenta de estudiante. |  | |
| 2 | **Catálogo de rutas:** ve las rutas disponibles y se inscribe en una. |  | |
| 3 | **Perfil:** escribe en texto libre su experiencia, formación e intereses. | OE2 | 🔵 P1: el texto se convierte en embeddings y da una señal previa de conocimiento por tema. |
| 4 | **Diagnóstico:** responde una prueba generada desde el syllabus (2 a 3 preguntas por tema). | OE2 · OE5 | 🔵 P1: generación de preguntas por nivel de Bloom. 🟢 P3: calidad de las preguntas (% válidas, κ de Cohen, discriminación). |
| 5 | **Resultado:** ve su nivel por tema. | OE2 | 🔵 P1: porcentaje de aciertos ponderado por dificultad, combinado con la señal del perfil. |
| 6 | **Objetivo:** recibe el de la ruta o una propuesta de la IA, y lo confirma o lo ajusta. | OE3 | 🟠 P2: la propuesta parte de la brecha detectada. |
| 7 | **Vista de ruta:** ve su ruta personalizada, con los temas dominados (≥ 80 %) omitidos y los prerrequisitos débiles incluidos. | OE3* | 🟠 P2: recorrido del DAG en orden topológico. Se mide el tiempo ahorrado frente a una ruta fija. |
| 8 | **Tema:** lee el texto con fuentes citadas y ve un video. | OE4 · OE5 | 🟠 P2: selección de recursos para la brecha. 🟢 P3: fidelidad del RAG (RAGAS) y Precision@3 / nDCG@3 de los videos. |
| 9 | **Quiz del tema:** responde opción múltiple y respuesta corta con calificación automática. | OE4 · OE5 | 🟢 P3: calidad de las preguntas y acuerdo LLM vs. humano en respuestas cortas (QWK). |
| 10 | **Resultado del quiz:** con ≥ 70 % aprueba. Con menos recibe una explicación alterna y reintenta con preguntas nuevas (máximo 3 intentos). | OE5 | 🔵 P1: se valida el diagnóstico con el AUC al predecir la aprobación en el primer intento. 🟠 P2: el refuerzo se adapta al error. |
| 11 | **Siguiente tema:** repite los pasos 8 a 10 hasta completar la ruta. | OE5 | 🟠 P2: avance registrado por paso de ruta. |
| 12 | **Evaluación final:** presenta una prueba de toda la ruta. | OE4 · OE5 | 🟢 P3: ganancia de aprendizaje (Hake) entre el diagnóstico y esta prueba, con ítems equivalentes. |
| 13 | **Resultado final:** con ≥ 80 % pasa al badge. Con menos recibe un repaso dirigido a los temas débiles. | OE3* | 🟠 P2: el repaso se dirige a los temas débiles. |
| 14 | **Badge:** recibe y descarga su badge (imagen + JSON Open Badges). |  | |

## Docente

| # | Paso | Objetivo | Aporte |
| --- | --- | --- | --- |
| 1 | **Login:** entra con su cuenta de docente. |  | |
| 2 | **Crear curso:** registra un curso nuevo. |  | |
| 3 | **Cargar syllabus:** sube un PDF o texto. |  | |
| 4 | **Revisar temas:** corrige los temas, prerrequisitos y resultados de aprendizaje que extrajo el LLM. | OE1 | 🟢 P3: precisión, recall y F1 de lo extraído, comparado con la anotación del docente. |
| 5 | **Aprobar:** aprueba el grafo de temas. | OE1 | 🟠 P2: este DAG es la entrada del motor de ruta. 🔵 P1: define los temas que se diagnostican. |
| 6 | **Configurar ruta:** define el objetivo por defecto y los umbrales (70 %, 80 %, 3 intentos). | OE3 | 🟠 P2: parámetros del motor. |
| 7 | **Curar recursos:** corrige el contenido generado o agrega videos de respaldo. | OE4 | 🟢 P3: revisión de expertos sobre la muestra de contenido. |
| 8 | **Dashboard:** ve el avance por tema y el historial de intentos de cada estudiante. | OE5 | 🔵🟠 Fuente de datos para medir el diagnóstico y la ruta (dominio por tema, intentos por tema, abandono). |

## Admin

| # | Paso | Objetivo | Aporte |
| --- | --- | --- | --- |
| 1 | **Login:** entra con su cuenta de admin. |  | |
| 2 | **Usuarios:** crea, edita y elimina usuarios y asigna roles. |  | |
| 3 | **Cursos y rutas:** gestiona cursos, rutas e inscripciones (CRUD). |  | |
| 4 | **Supervisión:** consulta el estado general del sistema y el log de llamadas al LLM. | OE5 | 🟢 P3: latencia, tasa de JSON inválido y costo por estudiante-ruta. |

El brief no detalla las pantallas del admin. Los pasos 3 y 4 son una inferencia a partir del Módulo 1.

## Resumen: dónde vive cada pieza

| Pieza | Pasos donde se aplica |
| --- | --- |
| 🔵 P1 · Diagnóstico | Estudiante 3, 4, 5, 10 · Docente 5, 8 |
| 🟠 P2 · Motor de ruta | Estudiante 6, 7, 8, 10, 11, 13 · Docente 5, 6, 8 |
| 🟢 P3 · Calidad de la IA | Estudiante 4, 8, 9, 12 · Docente 4, 7 · Admin 4 |

## Cruce con los objetivos específicos

OE1 a OE5 son los objetivos específicos del [brief](brief.md#objetivos).

| Objetivo específico | Pasos del flujo | Pieza | Medición |
| --- | --- | --- | --- |
| **OE1.** Modelar el syllabus como grafo de temas con prerrequisitos y resultados medibles | Docente 3, 4, 5 | 🟢 P3 (base de 🟠 P2) | F1 ≥ 0,85 de temas y prerrequisitos |
| **OE2.** Generar el diagnóstico y estimar el nivel por tema | Estudiante 3, 4, 5 | 🔵 P1 (con 🟢 P3 en la calidad de las preguntas) | % de preguntas válidas, κ, discriminación, AUC ≥ 0,7 |
| **OE3.** Definir el objetivo de aprendizaje de cada estudiante | Estudiante 6 · Docente 6 | 🟠 P2 | El estudiante confirma o ajusta; el objetivo se redacta como resultado medible |
| **OE4.** Generar y curar recursos y evaluaciones por tema y final, alineados con Bloom | Estudiante 8, 9, 12 · Docente 7 | 🟠 P2 y 🟢 P3 | Fidelidad ≥ 0,8, P@3 ≥ 0,7, QWK ≥ 0,6, preguntas válidas ≥ 80 % |
| **OE5.** Evaluar la calidad del contenido y la efectividad de la ruta | Estudiante 10, 12 · Docente 8 · Admin 4 | 🔵 P1, 🟠 P2 y 🟢 P3 (transversal) | Ganancia de Hake ≥ 0,3, d de Cohen, SUS ≥ 68, costo y latencia |

### Hallazgos del cruce

1. **La secuenciación de P2 no tiene objetivo específico propio.** El paso 7 del estudiante (omitir temas dominados, ordenar el DAG e incluir prerrequisitos débiles) es parte del aporte, pero ningún OE lo nombra. OE3 cubre el objetivo y OE4 cubre la generación de recursos. Propuesta: ampliar OE3 a "definir el objetivo y secuenciar la ruta de cada estudiante".
2. **OE1 no es una de las tres piezas.** Es la entrada de las tres y se mide con F1, que entra en 🟢 P3. Si falla, el error se propaga a todo lo demás.
3. **OE5 va más allá de P3.** P3 habla de la calidad de lo que genera la IA. OE5 añade la efectividad en los estudiantes (Hake, d de Cohen, finalización, abandono), que usa datos de P1 y P2.
4. **P1 se concentra en OE2, pero se valida en OE5.** El AUC solo se puede calcular con datos del piloto (estudiante 10), no al construir el diagnóstico.
5. **Pasos sin objetivo asociado:** login, catálogo, inscripción, badge y CRUD del admin. Son infraestructura del MVP y no se miden como aporte.
6. **El dashboard del docente respalda a OE5.** Sin los datos de dominio, intentos y abandono por tema no se pueden calcular las métricas de los estudiantes.
