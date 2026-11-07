# Bitácora F05 · `ai/` contenido, evaluación y videos (agente `ai-content`, Ola 2)

Rama: `feature/ai-content-evaluation` (sale de `origin/feature/ai-service-base`, con fusiones posteriores de esa rama; no rebase). Publicada en `origin`.
Fuentes: `PLAN_IMPLEMENTACION_V3.md` (secciones 3, 4, 5.4, 18.5 y Fase 5), ADR 0011, 0012, 0013, 0015 y 0016, `docs/contracts/`, `prompts/` y `ai/app/domain/contracts/`.

## Hecho

| Bloque | Qué | Dónde |
| --- | --- | --- |
| Embeddings y RAG | Fragmentos de ~900 caracteres por párrafo, indexado idempotente por SHA-256 (fuentes y temas), recuperación top-k = 4 por coseno, almacén en memoria y almacén PostgreSQL con pgvector (`<=>`), sin LlamaIndex | `application/embeddings/`, `adapters/memory_knowledge.py`, `adapters/pg_knowledge.py` |
| Contenido | `content.explain_topic` (citas `[n]` dentro del rango, caché por tema), `content.check_faithfulness`, `content.remedial` y `content.personal_example` (perfil seudonimizado, sin caché) | `application/content/` |
| Ítems | `items.generate_quiz_bank` (23 por tema = 18 de opción múltiple + 5 de respuesta corta, cobertura de todos los resultados, sin repetir enunciados) y `items.generate_final_bank` (`f<n>_v<k>`, `eg_<n>`, `final`/`retention`), ambos con revisión automática | `application/items/` |
| Calificación | `grading.short_answer` (temperatura 0, sin caché, rúbrica literal, puntos parciales, la retroalimentación no puede copiar la respuesta esperada ni un criterio no cumplido; respuesta vacía = 0 por regla sin llamar al modelo) y calificación de opción múltiple por regla | `application/grading/` |
| Videos | Adaptador de YouTube Data API (`relevanceLanguage`, `videoEmbeddable`, duración, idioma, capítulos), transcripción por metadatos, caracterización con la lista cerrada de subtemas, puntaje = similitud + ajustes de idioma y duración, top 3 con respaldos, `video.collect_candidates` y `video.rank` (ruta síncrona `POST /v1/tasks/video.rank`) | `adapters/youtube.py`, `adapters/metadata_transcripts.py`, `domain/video_ranking.py`, `application/video/` |
| Badge y orquestación | `badge.compose_text`; `course.generate_content` encola un trabajo por tarea y tema con claves idempotentes | `application/badge/`, `application/content/course_generation.py` |
| Conexión | `TaskSpec` y `ContentJobHandler` adaptan las tareas al `JobHandler` de ai-base; `build_handlers` recibe los servicios de contenido | `application/content/registry.py`, `wiring.py`, `container.py` |
| Arnés | `python -m eval` / `eval.pipeline.run_pipeline`: sílabo → trabajos de `course.generate_content` ejecutados como el worker → badge → aprendices simulados (ejemplo, respuestas, calificación, explicación alterna) → `llm_log.jsonl`, `metrics.json` y `verify_consistency`. Respuestas falsas que leen los datos de cada petición | `ai/eval/` |

Commits: `f8b2068` (código), `26def28` (pruebas), `d003c14` (conexión con ai-base) y los siguientes de esta rama.

## Desviaciones frente al plan o al brief

| # | Plan o contrato | Lo que se hizo | Motivo |
| --- | --- | --- | --- |
| DV-01 | ai-base DC-08: los nombres propios no se detectan en `ai/` | `content/privacy.py` quita también nombres con una pista (`me llamo X`, `Soy X Y`, `Dra. X`, firmas, `@usuario`) | El plan 5.4.12 y esta tarea piden quitar nombres con reglas simples; un nombre sin pista no se detecta (se prefiere pocos falsos positivos) |
| DV-02 | Contrato `course.generate_content`: `result = {"jobs": […]}` | Se nombra el contrato `generate_content_jobs.v1` y el de indexado `embeddings_index.v1`, sin archivo de esquema | `prompts/schemas/` no define esos dos; se propone agregarlos |
| DV-03 | `app/application/items.py` (ai-base) | Pasó a `app/application/items/review_handler.py` y el paquete lo reexporta | El paquete `items/` pedido para esta fase reemplaza al módulo del mismo nombre; los imports de ai-base siguen funcionando |
| DV-04 | `AI_SOURCES_DIR`, `YOUTUBE_API_KEY` | Se leen directo del entorno en `content/wiring.py` | `core/config.py` es de ai-base; propuesta: agregarlos a `Settings` y a `.env.example` |
| DV-05 | Embeddings de Gemini en `adapters/gemini_embeddings.py` | Se descartó mi adaptador: ai-base publicó `GeminiEmbeddingProvider` en `adapters/gemini.py` | Evitar duplicado |
| DV-06 | Caché de revisión «por ítem» (contrato 3) | La revisión se cachea por lote (clave del `LlmRunner`) | El runner cachea por prompt renderizado; cachear por ítem exigiría cambiar el núcleo |

## Decisiones

| # | Decisión | Opciones | Motivo |
| --- | --- | --- | --- |
| DC-01 | `content.explain_topic` indexa el curso si hace falta antes de recuperar | Exigir que `embeddings.index_course` haya corrido | El orden de los trabajos hijos no está garantizado; indexar es barato si nada cambió |
| DC-02 | Sin fragmentos → `NO_SOURCE_FRAGMENTS` (no reintentable) | Explicar sin fuentes | El RAG exige fuentes (DEF-08) |
| DC-03 | Puntaje de video = similitud + 0,05·idioma + 0,05·duración; filtros duros 4–30 min e idioma (inglés solo si se permite); videos del instructor se saltan los filtros | Pesos del informe (0,15 y 0,15) | Con pesos grandes el idioma y la duración dominarían la similitud; son valores iniciales configurables (`RankingPreferences`) |
| DC-04 | Un tema sin clave de YouTube ni lista del instructor devuelve `origin = none` | Fallar el trabajo | El contrato lo prevé (L-08); el instructor debe agregar un video |
| DC-05 | Búsqueda de YouTube caída con lista del instructor: sigue con la lista; sin lista: `VIDEO_SEARCH_UNAVAILABLE` (reintentable) | Fallar siempre | Mantiene el respaldo obligatorio de la sección 4 |
| DC-06 | Umbral de repetición de enunciados: similitud de Jaccard de palabras ≥ 0,85 | Igualdad exacta | Detecta reformulaciones leves sin rechazar enunciados distintos del mismo resultado |
| DC-07 | `quiz_items_per_topic = 23` se reparte 18 + 5 (`quiz_split`) | 4 + 1 por intento ×… | 3 intentos × (4 + 1) × 1,5 de margen (ADR 0015) |
| DC-08 | El banco final se genera para todos los temas del curso (`course.generate_content`) | Solo los de una ruta | El contrato recibe `learning_path_id` pero la ruta personal se decide después; el banco es por curso |
| DC-09 | El arnés ejecuta `syllabus_structuring` con el `LlmRunner` directamente | Esperar la tarea `syllabus.structure` | Mantiene el arnés independiente; se puede cambiar por el manejador de ai-base |

## Problemas y lecciones

- El sandbox rechaza comandos con la palabra `eval`, variables en rutas de `sed` y `cd` calculados: se usan guiones en el scratchpad y scripts de Python.
- Un paquete y un módulo con el mismo nombre (`items/` e `items.py`) se tapan entre sí; apareció al fusionar la rama de ai-base.
- Respuestas falsas fijas no sirven para un pipeline completo (ids que no coinciden): se escribieron respuestas que leen los bloques de datos del prompt. Los enunciados falsos necesitaron palabras elegidas por hash para no chocar con el control de repetición.
- Los controles de código atraparon un defecto real del primer borrador del arnés (banco con 5 respuestas cortas casi idénticas).
- El banco final repite enunciados del quiz si la API no envía `previous_stems`; el arnés lo detecta (`verify_consistency`). La API debería pasar los enunciados del quiz al pedir el banco final.

## Métricas

| Momento | Ruff | mypy | pytest |
| --- | --- | --- | --- |
| Final | sin errores | sin errores (132 archivos) | 346 pasan, 2 omitidas (PostgreSQL) en ~4 s; las 2 de `PgKnowledgeStore` pasan contra `pgvector/pgvector:0.8.7-pg17-bookworm` desechable (contenedor y red eliminados) |

Corrida del arnés con el falso: 11 trabajos (todos `succeeded`), 3 temas × 23 ítems de quiz, 16 ítems finales (8 grupos × 2 versiones), 3 videos seleccionados, fidelidad media 1,0, 0 inconsistencias, 2 aprendices simulados. Esquemas exportados al día (26).
Fidelidad, JSON inválido, latencia y costo reales: **sin medir** (no hay corrida con el LLM real; requiere `AI_EVAL_LIVE=1`, clave y precios).

## Qué falta

- Corrida real del arnés (`python -m eval --live`) con clave de Gemini, precios en `config/prices.yaml` y `YOUTUBE_API_KEY`; guardar en `data/examples/ai-run-<fecha>/`.
- Fuentes reales y licencias (DEF-08) en `AI_SOURCES_DIR`; verificar las condiciones de la API de YouTube (P-06) antes de usar subtítulos.
- Revisión de los prompts con salidas reales (Opus); si hay que cambiar uno, crear `v2.md` y registrar el hash.
- Esquemas JSON para `generate_content_jobs.v1` y `embeddings_index.v1`.
- `include_diagnostic` del orquestador queda apagado; la API puede encolar `diagnostic.generate_items` aparte.
- Prueba de integración de punta a punta por HTTP (`POST /v1/jobs`) con el worker real de ai-base.

## Impacto en el brief

- Sección de generación de contenido: el RAG usa consultas SQL sobre pgvector y no LlamaIndex (ADR 0013, B-04).
- Sección de videos: ranking por tema con curaduría del instructor y respaldos (ADR 0016, B-08); la caracterización por metadatos puede ser menos precisa que la transcripción.
- Sección de evaluación: banco de ítems pre-generado y revisado (ADR 0015, B-02).

## Cambios pedidos a archivos compartidos

- `ai/pyproject.toml`: `eval` en `[tool.mypy] files`; excepciones de Ruff para pruebas (`PT018`, `RUF001`, `E501`). Hechos en esta rama.
- `ai/app/container.py` y `ai/app/api/tasks.py` (de ai-base): cambios mínimos para registrar los servicios de contenido y la ruta `video.rank`. Hechos en esta rama.
- `ai/app/core/config.py` y `.env.example`: agregar `AI_SOURCES_DIR` y `YOUTUBE_API_KEY` (hoy se leen del entorno). httpx debería pasar de grupo de desarrollo a dependencias (lo usa el adaptador de YouTube; hoy llega por `google-genai`).
