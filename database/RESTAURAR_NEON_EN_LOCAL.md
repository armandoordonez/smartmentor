# Restaurar el respaldo de Neon en tu base local

Prompt listo para pegarle a tu Claude (o para seguir a mano) cuando quieras dejar tu base local de SmartMentor con los datos de Neon. El respaldo lo generó una persona del equipo con `database/scripts/neon-to-local.sh pull`; tú **solo restauras**, sin conectarte a Neon.

**Dónde está el respaldo.** Está versionado en este repositorio, en [database/respaldos-equipo/](respaldos-equipo/), como dos archivos:

- `neon_20261117_224227.tar.gz` (5,4 MB)
- `neon_20261117_224227.tar.gz.sha256`

SHA-256 esperado del `.tar.gz`: `5f3145e2b7bf3941b11da345078dc0042b0ddea6de76071c0bffc70a423297a9`

> **Aviso.** Es una copia de la base compartida de **desarrollo** (datos de prueba de agentes y recorridos), subida a `dev` por decisión explícita del dueño del proyecto. Contiene syllabus y lecturas usados en las pruebas, correos de cuentas de prueba y de personas del equipo, y el realm de Keycloak de desarrollo, con sus llaves. Según el dueño del proyecto, no son datos del piloto. No es una práctica a repetir: para respaldos de entornos con usuarios reales no se versionan.

La carpeta `database/backups/` sigue ignorada por git; los respaldos que generes con `neon-to-local.sh pull` quedan allí y no se suben.

Las contraseñas de los roles de la base y de Keycloak son las mismas para todo el equipo y se piden por el canal privado: no están en este documento ni en el repositorio.

Para generar un respaldo nuevo, o para el detalle del script, ver [database/README.md](README.md#bajar-neon-a-la-base-local-compartir-un-respaldo-con-el-equipo).

## Prompt

```text
OBJETIVO: restaurar en MI base de datos local de SmartMentor un respaldo que YA FUE GENERADO por una persona del equipo desde Neon y está versionado en el repo. Tú NO generas ningún respaldo y NO te conectas a Neon: solo restauras ese respaldo en la base local barriéndola. Trabaja en el repo smartmentor (docs en español, código en inglés), de punta a punta, validando cada paso. Avísame ANTES de cualquier paso destructivo que no esté en esta lista.

REGLAS DE SEGURIDAD
- Nunca imprimas ni copies contraseñas ni el contenido del .env (enmascara valores de PASSWORD/URL/SECRET).
- No hagas push ni PR, no toques stage/main, no subas el .env ni nuevos respaldos al repo.
- NO ejecutes `neon-to-local.sh pull`, bootstrap.sh con ADMIN_DATABASE_URL, ni nada contra Neon. No uses `docker compose down -v` ni borres volúmenes o database/data.

PASO 0 · LOS ARCHIVOS DEL RESPALDO (primero esto)
El respaldo ya está en el repo, versionado en database/respaldos-equipo/ (neon_20261117_224227.tar.gz y su .sha256). Si no aparece tras actualizar dev, DETENTE y dime que falta actualizar la rama; no lo generes tú. Cópialos a database/backups/ de este repo (esa carpeta está ignorada por git) y sigue desde ahí.
SHA-256 esperado del .tar.gz: 5f3145e2b7bf3941b11da345078dc0042b0ddea6de76071c0bffc70a423297a9

PASO 1 · REQUISITOS
Docker y docker compose funcionando (Windows/macOS: con WSL2). Actualiza la rama dev (`git fetch origin` y `git pull`; no descartes cambios míos sin commitear). Debe existir database/scripts/neon-to-local.sh; si no existe en mi copia, avísame que falta actualizar dev y detente; no improvises otro método.

PASO 2 · INTEGRIDAD Y EXTRACCIÓN
Dentro de database/backups/: `sha256sum -c neon_20261117_224227.tar.gz.sha256` (macOS: `shasum -a 256 -c`). Si no dice OK, detente. Luego `tar xzf neon_20261117_224227.tar.gz` y confirma que existe database/backups/neon_20261117_224227/ con smartmentor_<fecha>.dump y keycloak_<fecha>.dump.

PASO 3 · .env APUNTANDO A LA BASE LOCAL
Primero copia: `cp .env ~/.env.smartmentor.bak && chmod 600 ~/.env.smartmentor.bak`. Si no existe .env, créalo desde .env.example y pídeme los valores que falten: las contraseñas de los roles OWNER_/API_/AI_/METRICS_DATABASE_* y KEYCLOAK_DB_* son las MISMAS para todo el equipo y me las da el equipo por el canal privado (no las inventes). Luego:
- Comenta con el prefijo `# [Neon, desactivado <fecha>] ` las líneas DATABASE_HOST, DATABASE_SSL, DATABASE_JDBC_PARAMS y ADMIN_DATABASE_URL (si existen).
- Debajo deja: DATABASE_HOST=postgres · DATABASE_SSL=false · DATABASE_JDBC_PARAMS= (vacío) · DATABASE_PORT=5432.
- ADMIN_DATABASE_URL DEBE quedar comentada o ausente: si está activa, bootstrap.sh actúa sobre la base remota.
- Verifica que estén definidos POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB (smartmentor), KEYCLOAK_DB_NAME (keycloak) y las contraseñas de los roles.

PASO 4 · POSTGRES LOCAL
`docker compose up -d postgres` y espera `pg_isready`. Si es la primera vez (volumen vacío) la base y los roles se crean solos.

PASO 5 · RESTAURAR (destructivo, ya autorizado)
`database/scripts/neon-to-local.sh restore database/backups/neon_20261117_224227`
Hace: copia de mi base local actual con backup.sh (database/backups/), detiene api/ai/ai-worker/keycloak, BORRA mis bases locales smartmentor y keycloak (no toca postgres, plantillas ni smartmentor_test), las recrea con bootstrap.sh y restaura con los dueños de siempre. Pide confirmación escribiendo «si». Cada base se restaura en una sola transacción: si falla no queda nada a medias; avísame y deja intacta la copia previa.

PASO 6 · LEVANTAR TODO
`docker compose --profile ai up -d` (api, app, keycloak e IA; la IA está en el perfil ai). Espera que estén healthy.

PASO 7 · VALIDAR Y REPORTAR
- /ready de la API = 200 (API_PORT del .env, por defecto 8020).
- Dentro del contenedor api: DATABASE_HOST=postgres y DATABASE_SSL=false.
- Conteos esperados: 80 tablas públicas y 66 filas en databasechangelog (base smartmentor), 19 usuarios y 10 cursos en la app, 20 usuarios en user_entity (base keycloak). Consulta con `docker compose exec -T postgres psql -U "$POSTGRES_USER" -d <base> -Atc "..."` cargando el .env solo en ese comando.
- Login con un usuario sembrado (api/scripts/token.sh <correo>, con TOKEN_PASSWORD tomada del .env sin imprimirla) y GET /api/v1/courses?mine=true devuelve cursos.
Entrégame: qué variables cambiaste en el .env (solo nombres), dónde quedó la copia de mi base anterior (database/backups/*_<fecha>.dump), los conteos y cualquier diferencia con lo esperado.

SI ALGO FALLA
- Un error que mencione Neon o la cuota significa que alguna variable sigue apuntando allá: revisa el paso 3.
- Puertos ocupados (POSTGRES_PORT 5442, API_PORT…): dímelo antes de cambiar nada.
- Para volver atrás: `database/scripts/restore.sh database/backups/smartmentor_<fecha>.dump` (y el de keycloak) y devolver el .env desde ~/.env.smartmentor.bak.
```
