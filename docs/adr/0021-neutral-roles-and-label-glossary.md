# ADR 0021: Roles neutros (`learner`, `instructor`, `admin`) y glosario de etiquetas

* **Estado:** Aceptado (R-5 y DEF-23, decididos por el dueño el 2026-11-07; DEF-24 y DEF-26 con su valor por defecto)
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 0.1 (R-5), 13, 15.1 (B-01), DEF-23, DEF-24 y DEF-26
* **Relacionados:** [ADR 0003](0003-api-domain-first-layout.md), [ADR 0004](0004-authentication-keycloak-bearer.md), [ADR 0007](0007-schema-rebase-v2.md), [ADR 0014](0014-service-to-service-auth-client-credentials.md), [ADR 0017](0017-frontend-rebuilt-from-figma-v3.md)

---

## 1. Contexto

El dueño pidió que SmartMentor no quede atado al mundo académico universitario: el mismo producto debe servir para formación universitaria, empresarial y de otros contextos. Figma v3 ya muestra **Aprendiz**, **Instructor** y **Administrador**. Pero los códigos vigentes en la base, la API, el realm y las pruebas son los heredados del prototipo (`student` y `teacher`, ADR 0004), y el brief usa el vocabulario académico en todo su texto.

Además, una propuesta anterior (DEF-15) agregaba un cuarto rol `evaluator` para los expertos que anotan ítems y califican a mano, lo que contradice la decisión de tres roles.

## 2. Decisión

1. **Códigos técnicos neutros, en inglés:** `learner` (Aprendiz), `instructor` (Instructor) y `admin` (Administrador; «Admin» en el menú). Reemplazan a los códigos heredados en todas las capas.
2. **Sin cuarto rol:** los expertos externos entran como `instructor` y se **asignan** como evaluadores de un curso en la tabla `course_evaluators` (`course_id`, `user_id`, `assigned_by_user_id`), sin ser dueños de él (DEF-24).
3. **Las etiquetas visibles salen de un glosario, no de la base:** `app/src/core/labels.py` con un diccionario por perfil de contexto, y `config/labels.yaml` si la API necesita compartirlo (`role_labels` en `GET /me`). No hay tabla de traducciones.
4. **Perfiles de contexto** elegidos con `APP_CONTEXT_PROFILE`: `generic` (P0, por defecto), `academic` y `corporate` (P2). Solo cambian el texto visible; códigos, tablas, rutas e identificadores no cambian.
5. **`syllabus` se conserva en el código** (lo usan el brief, el notebook y los prompts); su etiqueta visible es configurable (DEF-26).
6. **Campos neutros del perfil:** `education_level` con valores `secondary`, `technical`, `undergraduate`, `postgraduate`, `other` y `none`; `qualification_title`; «grupo» (`group_label`) en lugar de «cohorte» en el producto.
7. **Emisor del badge y textos legales:** `BADGE_ISSUER_NAME` y `ORGANIZATION_NAME` en `.env`.
8. **Sin multi-organización:** una instalación es un contexto. Servir a varias organizaciones a la vez es otra decisión, para una cohorte posterior.
9. **Cambios por capa:**

   | Capa | Cambio |
   | --- | --- |
   | Base | Semilla de `roles` con `learner`, `instructor`, `admin` en el re-base ([ADR 0007](0007-schema-rebase-v2.md)), sin datos que migrar |
   | Keycloak | Roles del realm renombrados; la política de OTP pasa a `instructor` y `admin` (Fase 8, [ADR 0014](0014-service-to-service-auth-client-credentials.md)) |
   | API | `Role.LEARNER`, `Role.INSTRUCTOR`, `Role.ADMIN`; el dominio de casos de uso bajo `/me` se llama `learner` (ADR 0003); mensajes de error neutros |
   | `ai/` y prompts | Textos de los prompts con «instructor» y «aprendiz»; campos `learner_*` en los esquemas (por ejemplo `simulated_learner`). El notebook del Mago de Oz no se edita |
   | App | Carpetas `pages/learner`, `pages/instructor`, `pages/admin`; etiquetas desde el glosario ([ADR 0017](0017-frontend-rebuilt-from-figma-v3.md)) |
   | Documentos | Casos de uso, flujos y README (Fase 1); brief v2 (Fase 10) |

## 3. Alternativas descartadas

- **Conservar los códigos académicos y cambiar solo las etiquetas:** deja el sesgo en el modelo, que es justo lo que el dueño pidió evitar.
- **Etiquetas en una tabla de la base:** agrega una tabla y una pantalla de administración para un texto que cambia una vez por instalación.
- **Rol `evaluator`:** contradice la decisión de tres roles; la asignación por curso cubre la anotación ciega y la calificación humana.
- **Renombrar `syllabus` en el código:** no aporta neutralidad real y rompe la trazabilidad con el brief, el notebook y los prompts.

## 4. Consecuencias

- **Positivas:** el producto sirve en otros contextos sin tocar código; el re-base evita migrar datos de roles; tres roles simples de explicar.
- **Negativas y pendientes:**
  - Hay que cambiar el vocabulario en código, prompts, realm, pruebas (las 148 de la API) y documentos; se busca con `grep` en cada fase y en la revisión final (R-14).
  - El brief conserva el vocabulario académico hasta la Fase 10; mientras tanto el glosario traduce (B-01).
  - La matriz de roles del ADR 0004 queda expresada con los códigos heredados; la nueva matriz la define la Fase 3.
