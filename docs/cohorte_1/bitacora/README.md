# Bitácoras por fase · cohorte 1

Estas bitácoras son el **registro que dejó cada agente de desarrollo al terminar su parte** del [plan de implementación v3](../../../PLAN_IMPLEMENTACION_V3.md). Cada archivo cuenta, para una rama de trabajo: qué se hizo, qué se desvió del plan y por qué, cómo se validó (pruebas y resultados reales) y qué quedó pendiente. Son la evidencia detallada de cómo se construyó el producto, fase por fase.

**Para qué sirven:**

- Reconstruir por qué algo quedó como quedó: cada desvío del plan está anotado con su motivo.
- Dar trazabilidad a las decisiones de arquitectura, de base de datos, de API, de IA, de interfaz y de infraestructura.
- Servir de insumo al [brief de la cohorte 1](../../../proyecto/cohorte_1/brief.md), a los [anexos técnicos](../anexos/) y a la [trazabilidad](../trazabilidad/TRAZABILIDAD.md).

**Cómo leerlas:**

- Son **históricas**: se escribieron en su momento (2026-11-07 en adelante) y su contenido no se reescribe. Solo se actualizaron las rutas de los documentos que cambiaron de sitio al cerrar la cohorte (por ejemplo, `PENDIENTES.md` es hoy [`TRAZABILIDAD.md`](../trazabilidad/TRAZABILIDAD.md)).
- Las fases siguen el plan v3 y se ejecutaron en «olas» de agentes en paralelo, cada uno en su rama. El orden del plan fue: fase 0 (decisiones), 1 (diseño y contratos), 2 (base de datos), 3 (API), 4 y 5 (servicio de IA) y 7 (interfaz) en paralelo, 6 (integración de punta a punta), 8 (Keycloak, infraestructura y CI) y 9 (evaluación).
- **No hay bitácora de la fase 6 ni de las fases 10 y 11.** La evidencia de la integración de punta a punta con el LLM real (2026-11-12) está en la [hoja de ruta](../trazabilidad/HOJA_DE_RUTA.md#evidencia-de-f6-2026-11-12), y el cierre en el [brief de la cohorte](../../../proyecto/cohorte_1/brief.md) y la [trazabilidad](../trazabilidad/TRAZABILIDAD.md).

## Índice

### Fase 0 · Estándares e integración

| Bitácora | Contexto |
| --- | --- |
| [F00-repo-standards](F00-repo-standards.md) | Base de calidad común del repositorio: CI mínima, Ruff común, pre-commit, plantilla de pull request, Dependabot y guía de contribución. Rama `feature/repo-standards` |
| [F00-integracion-ola0](F00-integracion-ola0.md) | Integración de la «ola 0»: se unieron las cuatro ramas de diseño, ADR y prompts en una sola, sin conflictos, y se agregó el tablero de avance |

### Fase 1 · Diseño, decisiones y contratos

| Bitácora | Contexto |
| --- | --- |
| [F01-adrs](F01-adrs.md) | Agente `adrs`: los ADR de la arquitectura v3 (fecha 2026-11-07). Rama `feature/adr-architecture-v3` |
| [F01-contracts-prompts](F01-contracts-prompts.md) | Agente `contracts`: contratos de la API y de la IA, esquemas JSON y los prompts versionados, a partir de la prueba «Mago de Oz» |
| [F01-design-use-cases](F01-design-use-cases.md) | Agente `design-docs`: casos de uso (CU-01 a CU-35), estados y flujos del prototipo v3 |

### Fase 2 · Base de datos

| Bitácora | Contexto |
| --- | --- |
| [F02-database](F02-database.md) | Agente `database`: el rebase del esquema a `v2.0.0` con Liquibase, auditoría, roles de base y datos semilla. Ver el [anexo B](../anexos/B-modelo-de-datos.md) |

### Fase 3 · API

| Bitácora | Contexto |
| --- | --- |
| [F03a-api-identity-courses](F03a-api-identity-courses.md) | API v2, parte 1: identidad, cursos e integración con el servicio de IA |
| [F03b-api-paths-assessments](F03b-api-paths-assessments.md) | API v2, parte 2: rutas, evaluaciones y las rutas del aprendiz |
| [F03c-api-content-eval-pilot](F03c-api-content-eval-pilot.md) | API v2, parte 3: contenido, evaluación humana, piloto y observabilidad |

### Fases 4 y 5 · Servicio de IA

| Bitácora | Contexto |
| --- | --- |
| [F04-ai-base](F04-ai-base.md) | Agente `ai-base`: base del servicio `ai/`, estructuración del syllabus y diagnóstico |
| [F05-ai-content](F05-ai-content.md) | Agente `ai-content`: contenido con RAG, bancos de ítems, evaluación y recomendación de videos. Ver el [anexo C](../anexos/C-agentes-prompts-y-modelos.md) |

### Fase 7 · Interfaz

| Bitácora | Contexto |
| --- | --- |
| [F07a-app-core](F07a-app-core.md) | Interfaz v3, parte 1: la base (estilos y tokens, núcleo de sesión y navegación, clientes de la API, componentes y las primeras páginas) |
| [F07b-app-learner](F07b-app-learner.md) | Interfaz v3, parte 2: las páginas del aprendiz |
| [F07c-app-staff](F07c-app-staff.md) | Interfaz v3, parte 3: las páginas del instructor y del administrador |

### Fases 8 y 9 · Infraestructura y evaluación

| Bitácora | Contexto |
| --- | --- |
| [F08-infra](F08-infra.md) | Agente `infra`: realm de Keycloak v3 con sus scripts, Docker Compose con perfiles, scripts de secretos y coherencia del `.env`, y la integración continua. Ver el [anexo A](../anexos/A-arquitectura-y-despliegue.md) |
| [F09-eval-tools](F09-eval-tools.md) | Agente `eval-tools`: funciones de métricas, cuaderno reproducible, documentación de métricas y estructura del conjunto de oro. No incluye el piloto ni la usabilidad |

## Relacionado

- [Trazabilidad](../trazabilidad/TRAZABILIDAD.md): lo realizado, lo abierto y lo migrado a la siguiente fase.
- [Hoja de ruta](../trazabilidad/HOJA_DE_RUTA.md) y [bugs](../trazabilidad/BUGS.md): el día a día de la cohorte con fecha y hora.
- [Registro de decisiones](../decisiones.md) y [ADR](../../adr/README.md).
