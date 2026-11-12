# Hoja de ruta

Lo que falta para llegar al hito del brief (el flujo corre de punta a punta con el LLM real) y al piloto. Arranca del estado de `dev` en `d8de841` (2026-11-12). Estados e IDs en el [README](README.md#estados). Las fases F0–F11 son las del [plan v3](../../PLAN_IMPLEMENTACION_V3.md#7-plan-fase-a-fase).

**Última actualización:** 2026-11-12 14:05

## Dónde estamos (2026-11-12)

| Capa | Estado |
| --- | --- |
| Base de datos v2.0.0, API v2, Keycloak v3 y CI | ✔ En `dev` |
| Servicio `ai/` (syllabus, diagnóstico, contenido, RAG, calificación, videos) | ✔ En `dev`, con pruebas simuladas. Con Gemini real solo se probó la extracción del syllabus (F6 en curso) |
| Interfaz: las 96 pantallas de Figma tienen su página en Streamlit | ✔ En `dev` |
| Interfaz que lee la **API real** | ◐ Solo Mis cursos, Rutas y avance, Revisión de contenido, Videos y Calificación (PR 3). Las demás solo funcionan con datos de ejemplo |
| Revisión visual en un navegador | ☐ Nunca se hizo |

## Etapa 0 · Trazabilidad y puesta al día

| ID | Tarea | Fase | Depende de | Estado | Inicio | Fin | Rama / PR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-001 | Crear la carpeta de seguimiento (esta hoja, bitácora, bugs, Figma, subidas y mejoras) | — | — | ⏳ | 2026-11-12 13:57 | 2026-11-12 14:05 | `feature/seguimiento-trazabilidad` |
| T-002 | Llevar a `dev` el arreglo del bloqueo API ↔ `ai/` ([B-001](BUGS.md)) | F6 | — | ☐ | | | |
| T-003 | Poner al día `proyecto/checklist.md`, `HANDOFF.md`, `app/README.md` y `CHANGELOG.md` ([B-002](BUGS.md)) | F10 | T-002 | ☐ | | | |

## Etapa 1 · Conectar con la API real las pantallas que faltan

Se sigue el patrón del PR 3: cambios **aditivos** en la API, un adaptador por pantalla en `app/src/clients/` y muestras validadas contra `docs/contracts/openapi-api.json`.

| ID | Tarea | Pantallas de Figma | Depende de | Estado | Inicio | Fin | Rama / PR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-010 | Flujo del aprendiz: revisar y terminar el PR 5 (catálogo, perfil, quiz y ruta) y sacarlo de borrador | E1–E7c, E15 | T-002 | ◐ PR 5 en borrador | 2026-11-11 | | `fix/flujo-aprendiz` · PR 5 |
| T-011 | Resto del aprendiz con la API real: diagnóstico, final, badge, progreso, logros, encuesta y retención | E3–E4b, E8–E14, U1a–U1d | T-010 | ☐ | | | |
| T-012 | Detalle del aprendiz e intentos extra | D4, D4b, D4c | — | ☐ | | | |
| T-013 | Cola de anotación de preguntas | D5b | — | ☐ | | | |
| T-014 | Calidad de los videos según los aprendices | D5f | — | ☐ | | | |
| T-015 | Pantallas del administrador | AD1, AD2, AD3, AD4, AD5, C4 | — | ☐ | | | |
| T-016 | Vista previa de la ruta fija | AD4b, E5b | T-015 | ☐ | | | |
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
