# Hoja de ruta

Lo que falta para llegar al hito del brief (el flujo corre de punta a punta con el LLM real) y al piloto. Arranca del estado de `dev` en `d8de841` (2026-11-12). Estados e IDs en el [README](README.md#estados). Las fases F0–F11 son las del [plan v3](../../PLAN_IMPLEMENTACION_V3.md#7-plan-fase-a-fase).

**Última actualización:** 2026-11-12 15:31

## Dónde estamos (2026-11-12)

| Capa | Estado |
| --- | --- |
| Base de datos v2.0.0, API v2, Keycloak v3 y CI | ✔ En `dev` |
| Servicio `ai/` (syllabus, diagnóstico, contenido, RAG, calificación, videos) | ✔ En `dev`, con pruebas simuladas. Con Gemini real solo se probó la extracción del syllabus (F6 en curso) |
| Interfaz: las 96 pantallas de Figma tienen su página en Streamlit | ✔ En `dev` |
| Interfaz que lee la **API real** | ◐ Solo Mis cursos, Rutas y avance, Revisión de contenido, Videos y Calificación (PR 3). Las demás solo funcionan con datos de ejemplo |
| Revisión visual en un navegador | ☐ Nunca se hizo |

## Estado por fase (F0 a F11)

**Fase actual: F6 (integración de punta a punta, el hito del brief), en paralelo con lo que le queda a F7 (la interfaz con la API real).** Revisado el 2026-11-12 14:59.

Fuentes: el [tablero del plan](../../PLAN_IMPLEMENTACION_V3.md#21-tablero-de-avance-del-plan) (actualizado el 2026-11-07 y el 2026-11-10), cuyos commits de evidencia se comprobaron con `git merge-base --is-ancestor` y **todos están en `dev`**; los PR 1 a 5; y este seguimiento. «Sin verificar» quiere decir que no se ejecutó ni se encontró una evidencia escrita.

| Fase | Qué es | Estado | Evidencia | Lo que falta | Tareas |
| --- | --- | --- | --- | --- | --- |
| F0 | Decisiones, línea base en `dev` y alcance congelado | ✔ Lo técnico · aprobación sin verificar | `eb84c97` (línea base), `726fc16` (estándares y CI mínima) | Aprobación del plan por el director (pide la salida verificable de F0; no hay registro). Prueba de usabilidad de la Fase 0 del brief | — |
| F1 | Diseño y contratos | ✔ Lo técnico · aprobación sin verificar | `e709dd4` (casos de uso), `3e23ac3` (ADR 0007 a 0021), `f81d49d` (contratos y prompts), `37f44e8` (v3 como única fuente) | Aprobación del director en `design/01-flujo-y-casos-de-uso/README.md`. Revisar los ADR 0014, 0018, 0019 y 0020, que siguen propuestos | — |
| F2 | Base de datos `v2.0.0` | ✔ En `dev` | `995dbd9`: 51 changesets, 39 tablas y rollback | — | — |
| F3 | API v2 sin IA | ✔ En `dev` · se amplía | `995dbd9` y siguientes; 641 pruebas (tablero) y 651 (PR 3) | Cambios aditivos de T-012 a T-015 (subidos en `feature/seguimiento-trazabilidad`, sin PR; CI en verde: API 660, app 621, ai 463) | T-012 a T-015 |
| F4 | `ai/` base: trabajos, syllabus y diagnóstico | ✔ En `dev` | `9000895`; syllabus real → Gemini → temas verificado el 2026-11-10 (tablero) | — | — |
| F5 | `ai/`: contenido, evaluación y videos | ✔ En `dev` · falta el LLM real | `9000895`: 400 pruebas con simulaciones | Corrida con el LLM real (la frenó el tope de gasto: HTTP 429) | T-030, T-032 |
| F6 | Integración de punta a punta (**hito**) | ◐ **En curso** | Syllabus real a temas (2026-11-10). PR 3 y PR 4 (bloqueo API ↔ `ai/`) | Llevar a `dev` el arreglo del PR 4 ([B-001](BUGS.md)). Subir el tope de gasto. Syllabus real. Corrida de punta a punta con costo y latencia | T-002, T-030, T-031, T-032 |
| F7 | Interfaz v3 | ◐ **En curso** | Las 96 pantallas tienen página en `dev`; 577 pruebas de la UI (PR 3) | Que todas las pantallas lean la API real (PR 5 en borrador; T-011, T-015f, T-016, T-017). Estados que Figma no dibuja (T-020 a T-023). **Comparación visual con Figma, nunca hecha** (T-034) | T-010 a T-024, T-033, T-034 |
| F8 | Keycloak, infraestructura y CI | ✔ En `dev` · salida sin verificar | `995dbd9`: realm v3, compose y `.github/workflows/ci.yml` | `docker compose up` en un PC limpio en menos de 10 minutos (sin verificar). Contraseña SMTP de Keycloak (P-19). Endurecimiento antes de datos reales | T-050 |
| F9 | Evaluación y piloto | ◐ Herramientas hechas · faltan personas | `97ffd44`: métricas y notebook. AD3 ya muestra el catálogo de métricas (T-015c, subido sin PR) | Anotación de expertos, calificación humana, usabilidad (SUS) y piloto con personas reales. Textos legales | T-040 a T-043 |
| F10 | Revisión final, despliegue y brief v2 | ☐ Pendiente | — | Todo; empieza después de F9. Incluye poner al día el checklist y el HANDOFF ([B-002](BUGS.md)) | T-003, T-051 |
| F11 | Cierre y traspaso | ☐ Pendiente | — | Etiqueta `v1.0-cohorte1`, release y traspaso | T-052 |

Resumen: **hechas 6** (F0 a F5 en lo técnico; F0 y F1 esperan la aprobación del director y F5 la corrida con el LLM real), **en curso 3** (F6, F7 y F9) y **pendientes 2** (F10 y F11). Casi todo lo que bloquea F6 lo tiene que resolver el dueño: el tope de gasto de Gemini y el syllabus real.

## Etapa 0 · Trazabilidad y puesta al día

| ID | Tarea | Fase | Depende de | Estado | Inicio | Fin | Rama / PR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-001 | Crear la carpeta de seguimiento (esta hoja, bitácora, bugs, Figma, subidas y mejoras) | — | — | ⬆ Subido (sin PR) | 2026-11-12 13:57 | 2026-11-12 14:00 | `feature/seguimiento-trazabilidad` · `ee2ee75` |
| T-002 | Llevar a `dev` el arreglo del bloqueo API ↔ `ai/` ([B-001](BUGS.md)) | F6 | — | ⬆ Subido (sin PR), CI en verde | 2026-11-12 14:01 | 2026-11-12 14:01 | `feature/seguimiento-trazabilidad` · `4ea823f` (también en `fix/bloqueo-trabajos-ia-a-dev` · `0699da7`, sin subir) |
| T-003 | Poner al día `proyecto/checklist.md`, `HANDOFF.md`, `app/README.md` y `CHANGELOG.md` ([B-002](BUGS.md)) | F10 | T-002 | ☐ | | | |

## Etapa 1 · Conectar con la API real las pantallas que faltan

Se sigue el patrón del PR 3: cambios **aditivos** en la API, un adaptador por pantalla en `app/src/clients/` y muestras validadas contra `docs/contracts/openapi-api.json`.

| ID | Tarea | Pantallas de Figma | Depende de | Estado | Inicio | Fin | Rama / PR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-010 | Flujo del aprendiz: revisar y terminar el PR 5 (catálogo, perfil, quiz y ruta) y sacarlo de borrador | E1–E7c, E15 | T-002 | ◐ PR 5 en borrador | 2026-11-11 | | `fix/flujo-aprendiz` · PR 5 |
| T-011 | Resto del aprendiz con la API real: diagnóstico, final, badge, progreso, logros, encuesta y retención | E3–E4b, E8–E14, U1a–U1d | T-010 | ☐ | | | |
| T-012 | Detalle del aprendiz e intentos extra | D4, D4b, D4c | — | ⬆ Subido (sin PR), CI en verde | 2026-11-12 14:0x (aprox.) | 2026-11-12 14:11 | `feature/seguimiento-trazabilidad` · `d47df63` |
| T-013 | Cola de anotación de preguntas | D5b | — | ⬆ Subido (sin PR), CI en verde | 2026-11-12 14:13 | 2026-11-12 14:16 | `feature/seguimiento-trazabilidad` · `d47df63` |
| T-014 | Calidad de los videos según los aprendices | D5f | F-012 | ⬆ Subido (sin PR), CI en verde | 2026-11-12 14:17 | 2026-11-12 14:22 | `feature/seguimiento-trazabilidad` · `d47df63` |
| T-015 | Pantallas del administrador (dividida en T-015a a T-015f) | AD1–AD5, C4 | — | ◐ | 2026-11-12 14:22 | | |
| T-015a | Usuarios y roles: roles desde `/roles` y `/user-roles`, activos e inactivos, alta y activación con las rutas reales ([B-003 a B-005](BUGS.md)) | AD1 | — | ⬆ Subido (sin PR), CI en verde | 2026-11-12 14:22 | 2026-11-12 14:27 | `feature/seguimiento-trazabilidad` · `d47df63` |
| T-015b | Log del LLM y resumen: tokens, campos vacíos, latencias y nombre de la tarea | AD2 | — | ⬆ Subido (sin PR), CI en verde | 2026-11-12 14:22 | 2026-11-12 14:27 | `feature/seguimiento-trazabilidad` · `d47df63` |
| T-015c | Métricas globales: catálogo de 29 métricas con meta y estado calculados en la API (decisión del dueño) | AD3 | — | ⬆ Subido (sin PR), CI en verde | 2026-11-12 14:51 | 2026-11-12 14:56 | `feature/seguimiento-trazabilidad` · `d47df63` |
| T-015d | Piloto y vista previa de la ruta fija: el piloto se busca con `GET /pilots` ([B-006](BUGS.md)), y se agregan la ruta, los consentimientos, los temas con ítems y la vista previa con nombres | AD4, AD4b | — | ⬆ Subido (sin PR), CI en verde | 2026-11-12 14:28 | 2026-11-12 14:33 | `feature/seguimiento-trazabilidad` · `d47df63` |
| T-015e | Cursos, rutas e inscripciones: nombre del aprendiz y consentimiento al piloto en la API; dueño del curso desde `owner_user_id` | AD5 | — | ⬆ Subido (sin PR), CI en verde | 2026-11-12 14:38 | 2026-11-12 14:42 | `feature/seguimiento-trazabilidad` · `d47df63` |
| T-015f | Catálogo de prompts: revisar si lee la API o `prompts/catalog.yaml` | C4 | — | ☐ | | | |
| T-016 | Vista previa de la ruta fija | AD4b, E5b | T-015 | ◐ AD4b hecho en T-015d; falta revisar E5b (vista del aprendiz) | 2026-11-12 14:28 | | |
| T-017 | Revisar si las demás pantallas del instructor ya leen la API real: nuevo curso, syllabus, grafo y panel de ruta | D1b–D2d, D3b | — | ☐ | | | |

## Etapa 2 · Estados que Figma no dibuja

Antes de codificarlos se le avisa al dueño (ver [FIGMA.md](FIGMA.md)).

| ID | Tarea | Hueco | Estado |
| --- | --- | --- | --- |
| T-020 | Error de un trabajo de IA en las pantallas de carga | F-001 | ☐ Revisar lo que ya hace el código y aprobarlo |
| T-021 | Catálogo vacío | F-002 | ☐ ⛔ Falta el diseño o la aprobación |
| T-022 | Instructor sin cursos | F-003 | ☐ ⛔ Falta el diseño o la aprobación |
| T-023 | Menú de perfil con cambio de rol | F-004 | ☐ ⛔ Falta el diseño o la aprobación |
| T-024 | Corregir en la app las contradicciones de datos de ejemplo que se hayan copiado de Figma | F-006, F-008, F-010 | ☐ |

## Etapa 3 · De punta a punta con el LLM real (F6, hito del brief)

| ID | Tarea | Depende de | Estado |
| --- | --- | --- | --- |
| T-030 | Subir el tope de gasto de Google AI Studio (hoy responde 429) | Dueño | ⛔ Dueño |
| T-031 | Conseguir el syllabus real del curso (Carlos Villada) | Dueño | ⛔ Dueño |
| T-032 | Corrida completa: syllabus → temas → contenido → diagnóstico → ruta → quiz → final → badge, con costo y latencia anotados | T-002, T-010, T-011, T-030, T-031 | ☐ |
| T-033 | Verificar en el navegador que la nota del LLM aparece después de guardar (cambio 6 del PR 3) | Autorización para levantar la app | ⛔ No autorizado aún |
| T-034 | Revisión visual de todas las pantallas frente a Figma ([M-005](MEJORAS.md)) | Autorización para levantar la app | ⛔ No autorizado aún |

## Etapa 4 · Evaluación y piloto (F9)

| ID | Tarea | Depende de | Estado |
| --- | --- | --- | --- |
| T-040 | Textos legales del consentimiento (A3, A3b, A3c) revisados por jurídica | P-09, F-007 | ⛔ Dueño |
| T-041 | Anotación de expertos y calificación humana con personas reales | T-013, T-032 | ☐ |
| T-042 | Prueba de usabilidad (SUS) | T-034 | ☐ |
| T-043 | Piloto con 15 a 30 aprendices: dónde se despliega y quién lo opera (DEF-16) | T-032, T-040 | ⛔ Dueño |

## Etapa 5 · Cierre (F10 y F11)

| ID | Tarea | Estado |
| --- | --- | --- |
| T-050 | Endurecimiento antes de datos reales: rotar los secretos del historial, quitar `smartmentor-dev-tools`, Keycloak con HTTPS | ☐ |
| T-051 | Brief v2 a partir de las bitácoras | ☐ |
| T-052 | Etiqueta `v1.0-cohorte1` y release | ☐ |

## Pendientes que solo puede resolver el dueño

Están en la [sección 21 del plan](../../PLAN_IMPLEMENTACION_V3.md#21-tablero-de-avance-del-plan). Los que hoy bloquean esta hoja son T-030, T-031, T-040, T-043 y la autorización para levantar la app y correr las pruebas.
