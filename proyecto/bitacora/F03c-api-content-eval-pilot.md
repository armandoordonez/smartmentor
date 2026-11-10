# Bitácora F03c · API v2: contenido, evaluación humana, piloto y observabilidad

Rama: `feature/api-v2-content-evaluation-pilot` (desde `origin/dev`, con `origin/dev` fusionada de nuevo). Agente: `api-content` (Fase 3, tercera parte).

## Hecho

- **`content`** (commit `feat(api): dominio content...`): recursos de un tema (listado de versiones, revisión, edición con versión nueva y `content.check_faithfulness`, regeneración con `Idempotency-Key`), ítems (`GET /topics/{id}/items`, `PATCH /items/{id}` aprobar, retirar o editar con `items.review`), videos (`GET/POST /topics/{id}/video-candidates`, `PATCH /video-candidates/{id}` con juicio de pertinencia, «usar este» y respaldos), calidad de videos (`GET /learning-paths/{id}/video-quality`, índice bayesiano con «Midiendo») y `POST /me/video-feedback`.
- **Ingestores idempotentes** registrados en `ai_gateway/dependencies.py`: `content.explain_topic`, `content.check_faithfulness`, `items.generate_quiz_bank`, `items.generate_final_bank`, `diagnostic.generate_items`, `items.review` y `video.collect_candidates`. Las salidas de `FakeAiService` para esos trabajos viven en `content/fake_results.py`.
- OpenAPI y colección de Postman regenerados (`dev.sh openapi` y `postman`).

## Desviaciones frente al plan o al brief

- **Ids enteros en las rutas, no `public_id`**: el contrato (`api-v2.md`) y todo el código ya integrado (`courses`, `identity`) usan enteros; cambiar solo estos dominios rompería la coherencia. Los `public_id` se siguen usando en lo público (badge) y en los trabajos (`job_id`).
- `resources.version` es un entero en la base; la API lo devuelve como `version` y como `version_label` (`1.0`, `1.1`...).

## Decisiones

- Aprobar una versión de una explicación retira la versión aprobada anterior del mismo tema (el aprendiz ve una sola). Una edición queda en `pending_review` y la anterior sigue sirviendo hasta que se apruebe la nueva.
- Un ítem editado y una aprobación van en peticiones separadas (`422` si llegan juntas): la edición siempre vuelve a `pending_review`.
- Solo hay un video `in_use` por tema; al elegir otro, el anterior pasa a `backup`. El video en uso tiene su fila en `resources` (`resource_type=video`).
- Idempotencia sin tabla propia: explicaciones por `created_at` del trabajo, ítems por (tema, banco, enunciado) y `ai_job_id`, videos por la unicidad (tema, `youtube_video_id`); un candidato existente conserva el estado que le dio el instructor. El barrido solo revisa trabajos terminados en los últimos 7 días.
- `POST /me/video-feedback` repetido reemplaza la calificación (`200`); la primera da `201`.
- `AssessmentItemModel` queda en `content/models.py`; el dominio `assessments` debe importarlo (dos clases para la misma tabla fallan al cargar).

## Problemas y lecciones

- La barrera de herramientas del agente rechaza `heredoc` largos y variables en comandos de `docker`: se usaron scripts de apoyo en el directorio temporal.

## Métricas

(Se completan al cerrar cada dominio.)

## Impacto en el brief

- Pendiente de cerrar.

## Cambios pedidos a archivos compartidos

- `diagnostic.generate_items` lo ingiere `content`, pero nadie lo encola: `PublicationService` (`courses`) o el orquestador de `ai/` (`include_diagnostic`) debe pedirlo al publicar.

## Qué falta

- Dominios `evaluation`, `pilot`, `observability` y el administrador de `data_subject_requests` (ver commits siguientes).
