# Bitácora F04 · `ai/` base, syllabus y diagnóstico (agente `ai-base`, Ola 1)

Rama: `feature/ai-service-base` (sale de `origin/dev`). Publicada en `origin` al cerrar cada bloque.
Fuentes: `PLAN_IMPLEMENTACION_V3.md` (5.4 completa, 16.2, 18.5 y Fase 4 de la sección 7), ADR 0008, 0009, 0010, 0011, 0012, 0014 y 0019, `docs/contracts/ai-service-v1.md`, `docs/contracts/error-codes.md`, `prompts/` y `ai/app/domain/contracts/`.

## Hecho

| Bloque | Qué | Commit |
| --- | --- | --- |
| 1 | Esqueleto para `ai-content`: `app/ports/` (los 9 puertos del plan más `CatalogReader`), `app/core/` (configuración con `pydantic-settings` sin modelos por defecto, logs JSON con `request_id` y `job_id`, errores RFC 9457, JWT de servicio por JWKS con audiencia `smartmentor-ai`, motor de base), adaptadores falsos y en memoria (`fake_llm.py`, `fake_embedding.py`, `memory.py`), `prompt_files.py` con verificación de hashes, `application/llm_runner.py` (validación, reintentos, caché, presupuesto y registro), `application/pricing.py`, `adapters/budget.py`, `config/prices.yaml` sin precios, `domain/leveling.py`, `domain/sequencing.py`, `domain/pseudonymize.py`. `pyproject.toml` hereda `../ruff.toml` | ver `git log` |

## Desviaciones frente al plan o al brief

| # | Plan o contrato | Lo que se hizo | Motivo |
| --- | --- | --- | --- |
| DV-01 | 5.4.6: `generate_structured(prompt, schema, model, temperature)` | `generate_structured(LlmRequest)`; `LlmRequest` lleva `prompt_id`, versión, `system`, `user`, esquema, modelo y temperatura | El falso necesita saber qué prompt responde (varios comparten esquema) y el registro necesita el id; es el mismo contenido agrupado |
| DV-02 | 5.4.1: puertos listados | Se agrega `CatalogReader` (lectura de `courses`, `topics`, `learning_outcomes`, `syllabus_documents`) | Los trabajos reciben ids (`syllabus_document_id`, `course_id`, `topic_ids`) y deben leer el texto y los temas (ADR 0009, lectura permitida) |
| DV-03 | Plan 5.4.1: `adapters/pricing` implícito | `PriceTable` vive en `app/application/pricing.py` | La aplicación no importa adaptadores; leer un YAML de configuración no justifica un puerto |

## Decisiones

| # | Decisión | Opciones | Motivo |
| --- | --- | --- | --- |
| DC-01 | Sin modelos ni proveedores por defecto: el servicio arranca, `/health` responde, `/ready` falla con `missing` y el *worker* se niega a correr | Fallar al importar la configuración | Así `/ready` puede explicar qué falta (ADR 0011, plan 16.2) |
| DC-02 | Con proveedor real (`gemini`, `anthropic`) los cuatro topes `AI_*_BUDGET_USD` son obligatorios para `/ready`; con `fake` un tope vacío no limita | Topes por defecto en código | `.env.example` dice «vacío = el servicio no arranca con LLM real»; no se inventan montos |
| DC-03 | Con `AI_LLM_PROVIDER=fake` un modelo sin precio cuesta 0 y no bloquea `/ready` | Exigir precio siempre | La CI y el compose de desarrollo corren con el falso sin que el dueño llene precios ficticios |
| DC-04 | `json_valid` = la salida pasó el esquema; las validaciones de código fallidas quedan con `status=invalid_output` y `json_valid=true` | Marcar `json_valid=false` también en ese caso | Distingue «JSON inválido» (métrica L-07) de «JSON válido que no cumple las reglas» |
| DC-05 | Reintentos en dos niveles: el *runner* reintenta errores transitorios del proveedor (2) y salidas inválidas (2, con los problemas en el prompt); el *worker* reencola solo códigos transitorios (`LLM_PROVIDER_*`, `INTERNAL_ERROR`, `VIDEO_SEARCH_UNAVAILABLE`) hasta `AI_JOB_MAX_ATTEMPTS` usando `locked_until` como «no antes de» | Reencolar también `INVALID_OUTPUT` | `INVALID_OUTPUT` ya gastó sus reintentos; queda reintentable solo a pedido (`/retry`) |
| DC-06 | La caché guarda la salida `…LLM` validada; un acierto deja una fila en `llm_call_logs` con `from_cache=true` y costo 0 | No registrar aciertos | AD2 puede medir la tasa de acierto |
| DC-07 | El presupuesto se calcula sumando `llm_call_logs.cost_usd` (día y mes según `APP_TIMEZONE`; curso e inscripción por las `refs` del trabajo) y se revisa antes de cada intento | Contadores aparte | Una sola fuente de verdad; con el volumen del piloto la suma es barata |
| DC-08 | `pseudonymize()` quita correos, enlaces y números largos; los nombres propios no se detectan en `ai/` | Heurística de mayúsculas | Demasiados falsos positivos en español; la API nunca envía el nombre (DEF-05) |
| DC-09 | Secuenciación: `blocked` si algún prerrequisito incluido no está completado (un omitido cuenta como completado); si no, `pending` (puede haber varios `pending`) | Solo el primero `pending` y el resto `blocked` | Es la regla literal del contrato 4.2 y deja el primero disponible en `pending` |
| DC-10 | Nivel: un tema sin ítems tiene `test_score=null` y su peso se redistribuye; si no queda ninguna señal con peso, cuenta la prueba sola con 0 | Error | El contrato prohíbe dar peso a una señal ausente y exige pesos que sumen 1 |

## Problemas y lecciones

- El sandbox del agente rechaza comandos con variables en la ruta de `docker`: se usa un guion en el *scratchpad* con la ruta escrita.
- Un directorio de caché de uv creado por otro proceso como `root` impidió usar `/tmp/uv-cache-ai-base`; se usa `/tmp/uv-cache-ai-base2`.

## Métricas

| Momento | Ruff | mypy | pytest |
| --- | --- | --- | --- |
| Bloque 1 | sin errores | sin errores (58 archivos) | 218 pasan (197 previas + 21 nuevas) en 1,8 s |

## Impacto en el brief

(Se completa al cerrar.)

## Cambios pedidos a archivos compartidos

(Se completa al cerrar.)
