# HANDOFF

El seguimiento de las tareas, con responsables y porcentaje de avance, está en [`proyecto/checklist.md`](proyecto/checklist.md). Este documento recoge el estado técnico, la deuda y los próximos pasos.

Estado del proyecto, deuda técnica y próximos pasos para la siguiente cohorte. Última actualización: 2026-10-07 (cohorte 1).

## Qué funciona

- **Entorno:** `docker compose up -d --build` levanta PostgreSQL 17 + pgvector, aplica el esquema con Liquibase y arranca la API y Keycloak. Ver [`README.md`](README.md).
- **Base de datos:** esquema `v1.0.1` con 14 tablas de negocio, cada una con su `_audit` y trigger, secuencias propias, borrado lógico (`active`) y fechas `timestamptz` en `America/Bogota`. Rollback probado. Respaldos con `database/scripts/backup.sh`. Ver [`database/README.md`](database/README.md).
- **API:** 6 dominios y 14 recursos con crear, consultar, listar, actualizar, activar e inactivar (sin `DELETE`). Reglas de negocio del brief: umbrales y máximo de intentos de la ruta, aprobación automática, prerrequisitos sin ciclos, badge solo con la final aprobada. Errores RFC 9457, logs JSON con `request_id`. 148 pruebas, Ruff y mypy estricto en verde (`api/scripts/dev.sh all`). Ver [`api/README.md`](api/README.md).
- **Endpoints del estudiante** (`/api/v1/me/enrollments...`): inscribirse, ver y actualizar su inscripción, abandonarla, ver su ruta, entregar el diagnóstico y los intentos y ver su badge. Verifican la pertenencia (404 si el dato es de otro) y el estudiante nunca fija puntajes. Ver [`api/README.md`](api/README.md#endpoints-del-estudiante).
- **Autenticación (D-03, [ADR 0004](docs/adr/0004-authentication-keycloak-bearer.md)):** la API valida bearer tokens de Keycloak (RS256 por JWKS, `iss`, `aud`, `exp`), enlaza al usuario por `sub` o por correo verificado, crea como `student` a quien no existe, y autoriza con los roles de `user_roles` (matriz en `api/app/auth/policies.py`). Probado de punta a punta con tokens reales de este Keycloak.
- **Keycloak ([ADR 0005](docs/adr/0005-keycloak-postgres-realm-versioned.md)):** guarda sus datos en la base `keycloak` del PostgreSQL del proyecto, con su propio rol. El realm `smartmentor` (roles, clientes y usuarios de prueba) está versionado en `keycloak/realm/smartmentor-realm.json` y se importa solo en un PC nuevo. Respaldo y restauración de ambas bases con `database/scripts/backup.sh` y `restore.sh`; el realm se actualiza con `keycloak/scripts/export-realm.sh`.
- **Usuario inicial:** `Administrador` (`admin.smartmentor@yopmail.com`, rol `admin`) sembrado por Liquibase; se enlaza con Keycloak en su primer acceso si el correo está verificado.

## Qué no funciona o no existe todavía

| Pendiente | Detalle |
| --- | --- |
| Configuración de Keycloak | Al migrar, el realm tenía: el usuario administrador **sin contraseña**, el cliente `smartmentor-frontend` sin el mapper de audiencia y una URI de redirección mal escrita (`http:localhost:8081`, aún sin borrar). El mapper de audiencia, la URI de retorno de Postman y el cliente `smartmentor-dev-tools` ya se agregaron y se probó el inicio de sesión completo; falta **definir la contraseña** del usuario administrador en la consola y ejecutar `keycloak/scripts/export-realm.sh` (ver `keycloak/README.md`). |
| Endpoints de estudiante que dependen de la IA | Pedir el siguiente quiz o el recurso de un tema requiere la capa de IA. Lo base (inscribirse, ver y entregar) ya existe. |
| Endurecimiento | Limitación de peticiones, CORS restringido al frontend, HTTPS en Keycloak, vida corta de los tokens y decidir si el registro es abierto (hoy cualquiera con correo verificado se vuelve estudiante). |
| Capa de IA | `ai/`: generación, RAG, motor de ruta y calificador. La API ya tiene dónde guardar sus resultados (`topics`, `resources`, `diagnostics`, `assessment_attempts`, `llm_call_logs`). |
| Interfaz | Decidida: **Streamlit** ([ADR 0006](docs/adr/0006-frontend-streamlit.md)). Arquitectura y plan en [`app/README.md`](app/README.md); falta la prueba técnica del login y el código. |
| Embeddings | La dimensión `vector(1024)` y los índices HNSW son provisionales (D-01). |
| Syllabus y RAG | Extracción del syllabus, fragmentos RAG (D-04) y videos. |
| CI | No hay GitHub Actions todavía (Ruff, mypy, pytest y validación de changelogs). |

Las decisiones abiertas están en [`proyecto/decisiones-pendientes.md`](proyecto/decisiones-pendientes.md) (D-01 a D-06).

## Deuda técnica

- **Secretos en git:** `keycloak/realm/smartmentor-realm.json` incluye client secrets, llaves privadas de firma y hashes de contraseñas (decisión aceptada para datos de prueba, ADR 0005). **Antes de datos reales o de hacer público el repositorio:** regenerar llaves y secretos, dejar de versionar usuarios y secretos del realm y limpiar el historial de git. El client secret de `smartmentor-api` además se compartió en una conversación: regenerarlo.

- **Cliente `smartmentor-dev-tools` (flujo password):** existe para que Swagger, `api/scripts/token.sh` y Postman pidan un token sin navegador. **Solo desarrollo:** eliminarlo de Keycloak y dejar `OIDC_DOCS_CLIENT_ID` vacío antes de producción.
- Usuario único de base de datos para Liquibase y la API (D-05): separar uno con permisos mínimos para la API.
- La validación de tokens usa `PyJWKClient` (síncrono) en un hilo aparte; si el volumen crece, conviene un cliente JWKS asíncrono.
- Keycloak en modo `start-dev` (HTTP): para producción, `start` con HTTPS, nombre de host fijo y un rol de base de datos con mínimos privilegios.
- `topics.embedding` y `enrollments.profile_embedding` se cargan completos en cada consulta aunque la API no los devuelve; convendría diferir su carga.
- `changed_at` de la auditoría usa `now()`: los cambios de una misma transacción comparten hora. El orden real lo da `audit_id`.
- La detección de ciclos en prerrequisitos carga el grafo por consultas sucesivas; si los cursos crecen, conviene una consulta recursiva.
- Las pruebas no miden cobertura todavía.

## Próximos pasos sugeridos

1. Terminar la configuración de Keycloak (mapper de audiencia, URIs, correo verificado) y probar el inicio de sesión desde el frontend.
2. Decidir el modelo de embeddings con el procedimiento de D-01 y el proveedor de LLM (D-02).
3. Construir `ai/` empezando por la estructuración del syllabus (módulo 2 del brief).
4. Elegir y construir la interfaz.
5. Configurar CI.

## Traspaso entre cohortes

Checklist del brief:

- [ ] Versión etiquetada en Git y aplicación desplegada funcionando.
- [x] Este `HANDOFF.md` actualizado.
- [ ] Notebook de métricas reproducible.
- [ ] Datos anonimizados y anotaciones en `data/`.
- [ ] Accesos transferidos (GitHub, despliegue, claves de API, Figma, Keycloak).
- [ ] Brief actualizado con métricas y lecciones aprendidas.

Para trasladar datos entre PC: `database/scripts/backup.sh` en el origen, copiar los `.dump` y `restore.sh` en el destino (aplicación y Keycloak). `.env` no viaja con git y contiene credenciales: cópialo por un canal seguro o regenéralo.
