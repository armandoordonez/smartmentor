# Definition of Done y revisión de pull requests

Una página para decidir si algo está «hecho». El detalle técnico está en [`api/microservice-development-standard.md`](../../api/microservice-development-standard.md) y [`PLAN_IMPLEMENTACION_V3.md`](../../PLAN_IMPLEMENTACION_V3.md) (sección 14.2); el flujo, en [`CONTRIBUTING.md`](../../CONTRIBUTING.md).

## 1. Una tarea está hecha cuando

**Código**
- [ ] Hace lo que pide el caso de uso o la decisión de la fase, sin reglas de negocio fuera de su capa.
- [ ] `ruff check` y `ruff format --check` sin avisos; mypy estricto sin errores; sin `Any` implícito.
- [ ] Sin `print`, sin `except` vacío, sin fechas sin zona horaria (`timestamptz` en UTC; se muestra en Bogotá).
- [ ] Errores en `application/problem+json` (RFC 9457) y registros JSON con `request_id`, sin datos personales ni claves.

**Pruebas**
- [ ] pytest en verde; hay pruebas para el comportamiento nuevo y para sus casos de error.
- [ ] Cobertura mínima del 80 % en `domain/` y `application/` donde exista.
- [ ] Todo acceso a un objeto verifica que pertenezca al usuario (404 si no).

**Base de datos**
- [ ] Cambios solo mediante changesets nuevos; ninguno aplicado se modifica; `liquibase validate` en verde.
- [ ] Comentarios de tablas y columnas en español; nombres en inglés.

**Configuración y seguridad**
- [ ] Sin secretos ni valores reales en archivos versionados; variables nuevas en `.env.example` y leídas con `pydantic-settings`.
- [ ] Imágenes con etiqueta exacta, usuario no root y `HEALTHCHECK`.

**Documentación y proceso**
- [ ] Documentos, comentarios y commits en español; identificadores en inglés; roles `learner`, `instructor`, `admin`.
- [ ] Decisión de arquitectura nueva registrada como ADR; contratos o catálogos afectados actualizados.
- [ ] Commits Conventional Commits con el pie de coautoría; bitácora o checklist actualizados cuando corresponda.
- [ ] La CI está en verde sobre el commit exacto que se integra.

## 2. Lista de revisión de un pull request

1. **Alcance:** un solo tema, tamaño razonable, apunta a `dev` desde una rama `feature/*`; nada hacia `stage` ni `main`.
2. **CI:** `api`, `app` y `liquibase` en verde; el autor indica qué probó y con qué resultado.
3. **Corrección:** la lógica cumple el caso de uso; los casos límite y de error están probados.
4. **Diseño:** respeta las capas; sin dependencias nuevas sin justificación; sin duplicar lo que ya existe.
5. **Seguridad:** autorización en cada ruta, sin ids ajenos accesibles, sin secretos, entradas validadas, sin datos personales en registros.
6. **Datos:** migraciones reversibles o seguras, sin modificar changesets aplicados, índices y restricciones razonables.
7. **Excepciones de lint:** cada `noqa` o `per-file-ignores` nuevo tiene su motivo escrito.
8. **Documentación:** idioma correcto, enlaces válidos, ADR si hubo decisión, `.env.example` al día.
9. **Cambios en el flujo del usuario:** coherentes con el brief (`proyecto/brief.md`, que no se edita).
