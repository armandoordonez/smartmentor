# ADR 0018: Protección de datos personales: consentimiento, supresión y auditoría (Ley 1581)

* **Estado:** Propuesto. Lo cierra DEF-05 (director, responsable de evaluación y jurídica de la organización responsable) con la revisión de P-09; bloquea la supresión en la Fase 3 y el envío al LLM en la Fase 4
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 0 (riesgo 4), 2.3, 2.4 (C-13), 5.2.1, 5.3.2, 5.3.4, 5.4.12, 10 (R-04, R-05), 18.2 y DEF-05
* **Relacionados:** [ADR 0002](0002-liquibase-schema-versioning.md), [ADR 0007](0007-schema-rebase-v2.md), [ADR 0011](0011-llm-provider.md), [ADR 0019](0019-least-privilege-db-users.md)

---

## 1. Contexto

Figma v3 agrega consentimiento informado y derechos del titular (A3, A3b, A3c, E11, E11b): una autorización obligatoria para el tratamiento de datos, otra opcional para el piloto, revocación y «borrar mis datos». La Ley 1581 de Colombia exige poder suprimir los datos personales. Tres hechos lo complican:

- **Auditoría completa:** cada tabla de negocio tiene su `<tabla>_audit` con la fila entera en `jsonb` (ADR 0002). Borrar la fila deja los datos en la auditoría (C-13, R-05).
- **Borrado lógico:** la convención es `active = false`, sin `DELETE` desde la API.
- **Un tercero procesa texto:** la descripción libre y la hoja de vida del aprendiz alimentan prompts del LLM externo ([ADR 0011](0011-llm-provider.md)), y no hay base legal escrita para enviarlas (R-04).

Además, no existe un inventario de campos personales con su finalidad y retención (plan 18.2), y los textos de A3, A3b y A3c citan fechas vencidas y a la universidad (P-09).

## 2. Decisión

### 2.1 Consentimiento

1. **Tabla `consents`** (`user_id`, `consent_type` en `data_processing` o `pilot_research`, `document_version`, `granted_at`, `revoked_at`).
2. **`data_processing` es obligatoria para inscribirse:** sin ella, 403 `CONSENT_REQUIRED`. Se pide en el primer ingreso. `pilot_research` es opcional; solo quien la otorga entra al sorteo del piloto.
3. **Endpoints:** `GET` y `POST /me/consents`, `PATCH /me/consents/{type}/revoke`; `GET /me` devuelve `consent_status`.

### 2.2 Supresión frente a `_audit`

4. **Tabla `data_subject_requests`** (`request_type` en `deletion`, `access` o `rectification`; `status`; `resolved_at`). El aprendiz la crea con `POST /me/data-subject-requests` y el administrador la ejecuta.
5. **Supresión = seudonimizar y purgar:** las filas del titular se seudonimizan (se reemplazan nombre, correo, descripción y hoja de vida) y **se purgan sus filas de `_audit`**. Las filas de negocio que sostienen métricas agregadas se conservan sin datos que identifiquen a la persona.
6. **El procedimiento es una función de la base ejecutada por un usuario con permiso explícito** sobre las tablas `_audit` (que la API no tiene en uso normal, [ADR 0019](0019-least-privilege-db-users.md)) y se prueba con un caso de integración que verifica que no queda el correo ni el nombre en ninguna tabla.
7. **La supresión también se aplica en Keycloak** (usuario deshabilitado o eliminado).

### 2.3 Envío seudonimizado al LLM

8. **Nunca se envía al LLM** nombre, correo ni identificadores.
9. **La descripción libre se seudonimiza** antes de enviarla (se quitan correos, teléfonos y nombres propios con reglas simples) y **la hoja de vida va en categorías** (nivel, rango de experiencia, herramientas), no en texto libre.
10. **La explicación principal de un tema no lleva datos del aprendiz** (L-01); la personalización va en el ejemplo y en la explicación alterna, con el perfil seudonimizado.
11. **Proveedor con plan de pago o con exclusión de entrenamiento**, y retención según sus términos, que se documentan en DEF-05.
12. **Los registros (`llm_call_logs` y logs JSON) guardan el `input_sha256`**, no el texto enviado, y nunca datos personales ni claves.

### 2.4 Inventario y acceso

13. **Inventario de campos personales** (finalidad, retención, quién accede) aprobado por jurídica. El instructor ve un perfil reducido (A3c: herramientas e idiomas, no la hoja de vida completa).
14. **Recursos públicos sin ids secuenciales:** la verificación del badge usa `public_id uuid` y el receptor con hash y sal (Open Badges).

## 3. Alternativas descartadas

- **Borrado físico de las filas y de su auditoría:** rompe las métricas del piloto y la integridad referencial.
- **Solo borrado lógico (`active = false`):** no cumple la supresión; los datos siguen en la fila y en `_audit`.
- **Quitar la auditoría de las tablas con datos personales:** pierde la trazabilidad que exige el ADR 0002.
- **Enviar el perfil completo al LLM:** mejor personalización, pero entrega datos personales a un tercero sin base legal.

## 4. Consecuencias

- **Positivas:** la supresión es posible y verificable; el tercero no recibe identificadores; el consentimiento queda versionado por documento.
- **Negativas y pendientes:**
  - Purgar `_audit` es la única excepción a «la auditoría no se toca» y debe quedar registrada en el propio procedimiento.
  - La seudonimización con reglas simples no detecta todos los nombres propios; el riesgo residual se documenta en DEF-05.
  - Los textos legales de A3, A3b y A3c se reescriben con jurídica y con `ORGANIZATION_NAME` (no «la universidad»).
  - Sin DEF-05 cerrada no hay piloto con datos reales.
