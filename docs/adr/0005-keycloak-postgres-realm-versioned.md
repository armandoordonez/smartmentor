# ADR 0005: Keycloak sobre PostgreSQL y realm versionado

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** eduar.troyano
* **Fuente:** [`proyecto/brief.md`](../../proyecto/brief.md), sección "Gestión del proyecto y continuidad entre grupos" (repositorio que cada cohorte recibe y reconstruye en días)
* **Relacionados:** [ADR 0001](0001-postgres-pgvector.md), [ADR 0004](0004-authentication-keycloak-bearer.md), [`keycloak/README.md`](../../keycloak/README.md)

## 1. Contexto

La primera versión desplegó Keycloak en modo `start-dev` con su base H2 de archivos, guardada en `keycloak/data/`, para que los datos viajaran con la carpeta del proyecto. Pero el proyecto se desarrolla en varios PC y hay que trasladar la configuración y los usuarios, y esa forma no sirve:

- Los archivos de H2 son binarios del motor y dependen de la versión; copiados con el contenedor encendido se corrompen.
- Cada PC acaba con un Keycloak distinto (otras llaves de firma, otros clientes) y no hay manera de combinarlos.
- H2 está documentado por Keycloak como solo para desarrollo.

## 2. Decisión

1. **Keycloak guarda sus datos en el PostgreSQL del proyecto**, en una base `keycloak` con un rol propio (`keycloak`). Queda separada de la base `smartmentor`: ninguno de los dos roles ve los datos del otro. Keycloak crea y migra sus propias tablas; Liquibase no las toca.
2. **La configuración del realm se versiona en git:** `keycloak/realm/smartmentor-realm.json` incluye roles, clientes, mappers y usuarios. Keycloak lo importa al arrancar con `--import-realm`, **solo si el realm no existe** (nunca pisa datos existentes).
3. **Se trasladan datos lógicos, no archivos de motor:**
   - configuración: el JSON del realm (git), regenerado con `keycloak/scripts/export-realm.sh`;
   - datos acumulados: `backup.sh` (que ahora respalda también la base `keycloak`) y `restore.sh`.
4. **Un PC nuevo arranca solo:** clonar, copiar `.env.example` a `.env` y `docker compose up -d`. Se crean las bases y el rol de Keycloak (`01-create-database.sql`), Liquibase aplica el esquema y Keycloak importa el realm, con las mismas llaves de firma que los demás PC.
5. **No hay volumen propio de Keycloak.** Todo el estado de las dos bases está en `database/data/`.

## 3. Datos sensibles en git (decisión explícita)

El export incluye, a petición del proyecto y por ser **datos de prueba**: los *client secrets*, las **llaves privadas** con las que Keycloak firma los tokens y los hashes de contraseñas de los usuarios. Consecuencia: quien tenga el repositorio puede firmar tokens que la API aceptaría.

Condiciones de esta decisión:
- Solo mientras el repositorio sea privado y no existan usuarios ni datos reales.
- Antes de datos reales o de hacer público el repositorio: regenerar llaves y secretos, dejar de versionar usuarios y secretos del realm (`.gitignore`) y limpiar el historial de git. Está anotado en `HANDOFF.md`.

## 4. Alternativas descartadas

- **Seguir con H2 y copiar la carpeta:** frágil y sin forma de combinar cambios entre PC.
- **Una instancia compartida de Keycloak:** es lo correcto para el piloto con datos reales (nadie traslada nada), pero exige hosting y deja de permitir trabajar sin conexión. Queda como evolución natural (D-06).
- **Exportar el realm sin usuarios ni secretos:** más seguro, pero cada PC tendría que recrear los clientes con otros secretos y crear sus usuarios a mano. Se descartó por ahora por comodidad con datos de prueba.

## 5. Consecuencias

- **Positivas:** un solo motor y un solo mecanismo de respaldo para aplicación e identidades; PC nuevo sin pasos manuales; la configuración de Keycloak se revisa en pull requests; los tokens emitidos en un PC los valida la API de otro.
- **Negativas:**
  - Los cambios hechos en la consola de un PC no llegan solos a otro: hay que exportar el realm, hacer commit y, en el otro PC, recrear el realm o restaurar los datos (procedimiento en `keycloak/README.md`). El export pisa lo anterior, así que dos personas que cambien el realm a la vez generan conflictos en el JSON.
  - El archivo con secretos es un riesgo mientras esté en git (sección 3).
  - Si se pierde `database/data/` sin respaldo, se pierden los usuarios creados después del último export; se recupera la configuración, no los usuarios nuevos.
