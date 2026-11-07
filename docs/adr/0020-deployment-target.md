# ADR 0020: Destino de despliegue (cierra D-06)

* **Estado:** Propuesto. Lo cierra DEF-16 (director y responsable de producto), con P-18 (quién opera el servidor), antes del piloto de la Fase 9
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 1.4, 7 (Fases 9 y 10), 17 (P-18) y DEF-16; [`proyecto/decisiones-pendientes.md`](../../proyecto/decisiones-pendientes.md), D-06
* **Relacionados:** [ADR 0001](0001-postgres-pgvector.md), [ADR 0005](0005-keycloak-postgres-realm-versioned.md), [ADR 0014](0014-service-to-service-auth-client-credentials.md), [ADR 0018](0018-personal-data-protection.md), [ADR 0019](0019-least-privilege-db-users.md)

---

## 1. Contexto

El brief sugiere Supabase, Render, Railway o Hugging Face Spaces. El ADR 0001 exige verificar que el destino ofrezca PostgreSQL 17 con pgvector 0.8.x y definir cómo se corre Liquibase. La arquitectura v3 tiene más piezas que desplegar: PostgreSQL, Liquibase, Keycloak, la API, `ai`, `ai-worker` y la app de Streamlit. El piloto es de 15 a 30 aprendices de un curso, con datos personales reales ([ADR 0018](0018-personal-data-protection.md)). El despliegue productivo con datos reales quedó fuera del alcance del plan (1.4), pero el piloto necesita un lugar donde correr.

## 2. Decisión

1. **Primera opción:** desplegar el piloto **localmente en una red de la organización responsable**, con el mismo `docker compose` del repositorio, si se puede.
2. **Si no se puede**, un **servicio gestionado con PostgreSQL 17 + pgvector 0.8.x**, verificado antes de elegirlo (paridad del ADR 0001).
3. **Liquibase corre con la misma imagen** del repositorio, en el despliegue o en CI/CD.
4. **Condiciones para cualquier destino:** HTTPS en Keycloak y en la app; `ai` sin puerto público; secretos solo en variables de entorno, rotados respecto a lo que estuvo en git; usuarios de base de mínimo privilegio ([ADR 0019](0019-least-privilege-db-users.md)); respaldos de las dos bases.
5. **Las pruebas de despliegue y el runbook** (`docs/deploy/runbook.md`) se hacen en la Fase 10.

## 3. Alternativas descartadas

- **Hugging Face Spaces:** pensado para demostraciones de un solo contenedor; no encaja con siete servicios ni con datos personales.
- **Cerrar ya un proveedor gestionado concreto:** sin verificar versiones, precios ni quién opera, la decisión sería prematura.

## 4. Consecuencias

- **Positivas:** el despliegue local reutiliza el compose ya probado y mantiene los datos dentro de la organización.
- **Negativas y pendientes:**
  - Hace falta una persona que opere el servidor durante el piloto (P-18).
  - En un servicio gestionado, `CREATE EXTENSION vector`, la zona horaria y la creación de roles pueden requerir pasos del proveedor.
  - Hasta que se cierre DEF-16, el ADR 0001 sigue con la verificación de paridad pendiente.
