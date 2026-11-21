# Runbook de despliegue y operación de SmartMentor

Runbook operativo que promete el [ADR 0020](../adr/0020-deployment-target.md) (decisión 5). Cubre lo que existe hoy: **despliegue local con Docker Compose** y **base remota (Neon)**. **No cubre un servidor del piloto**: el destino no está decidido (el ADR 0020 sigue en estado «Propuesto»; ver DEF-16 y P-18). La arquitectura que explica cada pieza está en el [Anexo A](anexos/A-arquitectura-y-despliegue.md).

**Reglas de este documento**

- Cada paso termina con una comprobación que dice qué debes ver.
- Los comandos se ejecutan desde la raíz del repositorio, en Bash (Linux o Windows dentro de WSL2). macOS lo declara el script, pero **el equipo no lo ha probado**.
- Nunca imprimas ni pegues el contenido de `.env`. Los ejemplos usan solo nombres de variables.
- Los puertos son los valores por defecto del compose; si los cambiaste en `.env`, usa los tuyos.

| Servicio | Dirección por defecto | Variable |
| --- | --- | --- |
| Interfaz (`app`) | <http://localhost:8501> | `APP_PORT` |
| API (`api`), documentación | <http://localhost:8020/docs> | `API_PORT` |
| Keycloak | <http://localhost:8180> | `KEYCLOAK_PORT` |
| Servicio de IA (`ai`), solo depuración | <http://127.0.0.1:8030/docs> | `AI_PORT` |
| Mailpit (buzón de desarrollo) | <http://127.0.0.1:8025> | `MAILPIT_UI_PORT` |
| PostgreSQL local | `localhost:5442` | `POSTGRES_PORT` |

## 1. Requisitos

1. Docker con Compose v2. Comprobación: `docker compose version` imprime una versión y `docker info` no da error.
2. Bash. En Windows, Docker Desktop con integración WSL2 y todos los comandos dentro de la terminal de WSL2.
3. Un `.env` en la raíz. Se parte de la plantilla: `cp .env.example .env`. El archivo está ignorado por git; **no lo subas**.
4. Para el servicio de IA con proveedor real: `AI_LLM_PROVIDER`, los modelos (`AI_LLM_MODEL_DEFAULT`, `AI_LLM_MODEL_SMALL`) y la clave del proveedor elegido. Con `AI_LLM_PROVIDER=gemini` la clave es `GEMINI_API_KEY`; `scripts/local-up.sh` se detiene si falta. Para probar sin proveedor, usa `AI_LLM_PROVIDER=fake` o la opción `--no-ai`.
5. Si usarás Neon: el host de la conexión **directa** (sin `-pooler`) y las contraseñas de los roles, que el equipo comparte por su canal privado.

Comprobación final: `ls -l .env` muestra el archivo y `grep -c $'\r' .env` imprime `0` (sin saltos de línea de Windows).

## 2. Primer arranque (base local)

1. Crea el `.env` y genera los secretos que estén vacíos:

   ```bash
   cp .env.example .env
   scripts/gen-secrets.sh
   ```

   `gen-secrets.sh` rellena **solo** las contraseñas y secretos vacíos, es idempotente y no imprime valores; al final lista los nombres que debes completar a mano (usuarios, correo, modelos, claves de proveedores). Hazlo **antes** del primer arranque: PostgreSQL ignora los cambios de contraseña si `database/data/postgres` ya existe.

   Comprobación: `scripts/gen-secrets.sh --dry-run` no dice que vaya a rellenar nada.

2. Completa a mano lo que el script indicó. Con el buzón de desarrollo (`mailpit`, activo por defecto) define `SMTP_HOST`, `SMTP_PORT`, `SMTP_STARTTLS`, `SMTP_USER`, `SMTP_PASSWORD` y `SMTP_FROM` como indica `keycloak/README.md` (sección «Correo con Google o con Mailpit»).

3. Levanta todo:

   ```bash
   scripts/local-up.sh --gen-secrets
   ```

   La primera vez descarga imágenes y tarda varios minutos. El script comprueba requisitos, avisa de puertos ocupados, levanta `postgres`, `liquibase`, `api`, `keycloak`, `app`, `mailpit` y el servicio de IA, espera hasta 10 minutos a que cada contenedor esté sano, crea los usuarios de desarrollo `SEED_*_EMAIL` en Keycloak e imprime las URL.

   Comprobación: termina con «Listo» y las URL; `docker compose ps` muestra `smartmentor-postgres`, `smartmentor-keycloak`, `smartmentor-api`, `smartmentor-app`, `smartmentor-ai` y `smartmentor-mailpit` en estado `healthy`, y `smartmentor-ai-worker` en `Up` (no tiene healthcheck). `smartmentor-liquibase` no aparece: terminó con éxito.

4. Opciones útiles (de la cabecera de `scripts/local-up.sh`):

   | Opción | Efecto |
   | --- | --- |
   | `--no-ai` | No levanta `ai` ni `ai-worker` |
   | `--no-mail` | No levanta `mailpit` (usa el SMTP real del `.env`) |
   | `--with-admin` | Además crea al administrador en Keycloak |
   | `--no-build` | No reconstruye las imágenes |

5. Primer ingreso: abre <http://localhost:8501> e inicia sesión con un correo `SEED_*_EMAIL` y la contraseña `SEED_USERS_PASSWORD`. El instructor y el administrador configuran su OTP (código QR con una aplicación de autenticación) en el primer ingreso, **si el realm es el versionado** (ver sección 9.5).

Nota: la API usa por defecto `AI_SERVICE_MODE=fake` (servicio de IA simulado). Para que llame al servicio `ai` real, define `AI_SERVICE_MODE=http` en `.env` y repite el arranque.

## 3. Arranque diario y apagado

**Arrancar**

1. `scripts/local-up.sh` (es idempotente; los usuarios que ya existen no se tocan). Con `--no-build` es más rápido si no cambió el código.

   Comprobación: «Listo» y todos los contenedores `healthy`.

**Apagar**

1. `scripts/local-up.sh --down`. Detiene y elimina los contenedores de todos los perfiles y **conserva los datos** en `database/data/postgres`.

   Comprobación: `docker compose ps` no lista contenedores de `smartmentor-*`.

2. **Apaga el stack cuando no lo uses si trabajas contra Neon.** El `ai-worker` consulta la base cada pocos segundos y no deja que el cómputo gratuito de Neon se suspenda; eso agotó la cuota el 2026-11-17 (sección 9.3 y Anexo A, sección 10.1).

**Ver registros**: `docker compose logs -f <servicio>` con `postgres`, `liquibase`, `api`, `ai`, `ai-worker`, `keycloak`, `app` o `mailpit` (los de `ai` y `ai-worker` solo existen con el perfil `ai`).

## 4. Base remota (Neon): preparación y arranque

Solo datos de prueba. Esto lo hace **una sola persona** la primera vez; el resto del equipo salta al paso 5.

1. En el `.env` del responsable define: `DATABASE_HOST` con el host directo de Neon, `DATABASE_PORT`, `DATABASE_SSL=true`, `DATABASE_JDBC_PARAMS` con `?sslmode=require`, `ADMIN_DATABASE_URL` (administrador de Neon, solo para el bootstrap) y las contraseñas de `OWNER_DATABASE_PASSWORD`, `API_DATABASE_PASSWORD`, `AI_DATABASE_PASSWORD`, `KEYCLOAK_DB_PASSWORD` y `METRICS_DATABASE_PASSWORD`. `POSTGRES_USER` y `POSTGRES_PASSWORD` deben seguir definidos (cualquier valor): el compose los exige.

   Comprobación: `scripts/local-up.sh` muestra «Base de datos remota: <host> (no se levanta el PostgreSQL local)».

2. Crea bases, roles y pgvector (idempotente):

   ```bash
   database/scripts/bootstrap.sh
   ```

   Usa `psql` 15 o superior si lo tienes y, si no, el de la imagen de PostgreSQL por Docker.

   Comprobación: termina sin error y, en Neon, existen las bases `smartmentor` y `keycloak`.

3. Elige **una** de las dos rutas para el esquema:

   - **Base vacía con Liquibase:** `scripts/local-up.sh --bootstrap-db` hace el bootstrap (necesita `ADMIN_DATABASE_URL`), aplica Liquibase y arranca el resto.
   - **Subir los datos locales** (para que todos compartan los mismos): ejecuta `database/scripts/remote-sync.sh push` **antes** de cualquier Liquibase. El volcado trae el esquema y `databasechangelog`, y los `liquibase update` posteriores siguen funcionando. Por eso en esta ruta **no uses `--bootstrap-db`** (que aplicaría Liquibase enseguida): usa `bootstrap.sh` y `remote-sync.sh push` a mano. Es una precaución que sale de combinar `database/README.md` y `scripts/local-up.sh`; el equipo no la tiene probada de punta a punta.

   `remote-sync.sh` se niega a escribir sobre una base remota que ya tiene tablas; para reemplazarla: `database/scripts/remote-sync.sh import --replace --yes`.

   Comprobación: `docker compose --profile ai run --rm --no-deps liquibase update` termina sin error y sin cambios pendientes.

4. Los secretos de cliente del realm (`OIDC_UI_CLIENT_SECRET` y `AI_CLIENT_SECRET`) y `KC_HOSTNAME` deben ser **iguales en el `.env` de todo el equipo**, porque todos los Keycloak comparten el realm guardado en Neon.

**Arranque contra Neon (cada integrante)**

5. Copia el `.env` compartido por el canal privado del equipo y ejecuta `scripts/local-up.sh`. No se levanta `postgres`: el script aplica Liquibase en la base remota y arranca `keycloak`, `api`, `app` (y `ai`, `ai-worker`, `mailpit` según las opciones). La primera conexión tras una suspensión del cómputo gratuito puede tardar unos segundos.

   Comprobación: «OK liquibase (migraciones aplicadas en la base remota)» y los servicios sanos; el resumen final dice «PostgreSQL remoto: <host>».

Límites: varios Keycloak sobre la misma base no son un clúster; los cambios de configuración (roles, clientes) debe hacerlos una sola persona y los demás reinician su contenedor de Keycloak. No apuntes las pruebas de integración a la base compartida.

## 5. Respaldo y restauración

### 5.1 Respaldo de la base local

1. Con el contenedor `smartmentor-postgres` en marcha: `database/scripts/backup.sh`. Para borrar copias de más de 30 días: `BACKUP_RETENTION_DAYS=30 database/scripts/backup.sh`.

   Comprobación: aparecen `database/backups/smartmentor_<fecha>.dump` y `database/backups/keycloak_<fecha>.dump` (fecha y hora de Bogotá). Los dos se validan con `pg_restore --list`.

2. Los `.dump` de Keycloak contienen hashes de contraseñas y llaves: son secretos. `database/backups/` está ignorado por git; no los subas.

### 5.2 Restauración de la base local

**Reemplaza los datos de la base de destino.** Hazlo con respaldo previo.

1. Detén lo que usa la base: `docker compose stop api keycloak` (agrega `ai ai-worker` si están arriba).
2. Restaura cada base:

   ```bash
   database/scripts/restore.sh database/backups/smartmentor_<fecha>.dump
   database/scripts/restore.sh database/backups/keycloak_<fecha>.dump
   ```

   Pide confirmación (sin terminal exige `--yes`). Para revisar una copia sin tocar la real: `restore.sh <archivo> <otra_base>`.
3. Levanta de nuevo: `docker compose up -d` (o `scripts/local-up.sh`).

   Comprobación: `GET http://localhost:8020/ready` responde 200 y puedes iniciar sesión.

### 5.3 Respaldo de Neon (solo lectura sobre Neon)

1. Con `DATABASE_HOST` apuntando a Neon y `smartmentor-postgres` en marcha (`docker compose up -d postgres`): `database/scripts/neon-to-local.sh pull`.

   Comprobación: se crea `database/backups/neon_<fecha>/` con un `.dump` de la aplicación y otro de Keycloak. `pull` solo lee de Neon.

2. Para compartirlo: `tar czf neon_<fecha>.tar.gz -C database/backups neon_<fecha>` y `sha256sum` del archivo; se entrega por el canal privado del equipo. El repositorio es público: no se versionan respaldos de entornos con usuarios reales.

### 5.4 Bajar Neon a la base local

1. Con el `.env` apuntando a Neon: `database/scripts/neon-to-local.sh sync` (hace `pull` y luego `restore`), o `restore [CARPETA]` con un respaldo ya generado.
2. `restore` copia antes la base local con `backup.sh`, detiene `api`, `ai`, `ai-worker` y `keycloak`, **borra** las bases locales de la aplicación y de Keycloak, las recrea con `bootstrap.sh` y restaura con los dueños de siempre. Pide confirmación (`--yes` la omite). No toca `postgres`, las plantillas ni `smartmentor_test`.
3. Apunta el `.env` a la base local: `DATABASE_HOST=postgres`, `DATABASE_SSL=false`, `DATABASE_JDBC_PARAMS` vacío, y deja `ADMIN_DATABASE_URL` comentada o ausente. Después `docker compose up -d`.

   Comprobación: `restore` imprime cuántos cambios de Liquibase y usuarios quedaron.

## 6. Restaurar el respaldo del equipo

El respaldo de Neon de desarrollo está versionado en `database/respaldos-equipo/` (`neon_20261117_224227.tar.gz` y su `.sha256`). Es una copia de la base compartida de **desarrollo**: contiene datos de prueba, correos de cuentas de prueba y de personas del equipo, y el realm de Keycloak con sus llaves. El detalle y un prompt listo para pegarle a un asistente están en [`database/RESTAURAR_NEON_EN_LOCAL.md`](../../database/RESTAURAR_NEON_EN_LOCAL.md). Pasos a mano:

1. Actualiza la rama `dev` y verifica que existan `database/respaldos-equipo/neon_20261117_224227.tar.gz` y `database/scripts/neon-to-local.sh`. Si no aparecen, detente: falta actualizar la rama.
2. Copia los dos archivos a `database/backups/` y verifica la integridad:

   ```bash
   cp database/respaldos-equipo/neon_20261117_224227.tar.gz* database/backups/
   cd database/backups && sha256sum -c neon_20261117_224227.tar.gz.sha256 && cd -
   ```

   Comprobación: «neon_20261117_224227.tar.gz: La suma coincide» (en macOS, `shasum -a 256 -c`). El hash esperado está en `RESTAURAR_NEON_EN_LOCAL.md`.
3. Extrae: `tar xzf database/backups/neon_20261117_224227.tar.gz -C database/backups`.

   Comprobación: existe `database/backups/neon_20261117_224227/` con `smartmentor_<fecha>.dump` y `keycloak_<fecha>.dump`.
4. Haz copia de tu `.env` fuera del repositorio y deja el original apuntando a la base local (paso 5.4.3). Las contraseñas de los roles son las mismas para todo el equipo y se piden por el canal privado.
5. Levanta solo PostgreSQL: `docker compose up -d postgres`.
6. Restaura (**destructivo**: barre tus bases locales `smartmentor` y `keycloak`, con copia previa):

   ```bash
   database/scripts/neon-to-local.sh restore database/backups/neon_20261117_224227
   ```

7. Levanta el resto: `docker compose --profile ai up -d`.

   Comprobación (cifras del documento de restauración): 80 tablas públicas y 66 filas en `databasechangelog` en la base `smartmentor`; 19 usuarios y 10 cursos en la aplicación; 20 usuarios en `user_entity` de la base `keycloak`; `GET http://localhost:8020/ready` responde 200. Para contar sin cargar el `.env` en tu shell:

   ```bash
   docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d smartmentor -Atc "select count(*) from databasechangelog"'
   ```

Para volver atrás: `restore.sh` de la copia que hizo el paso 6 (`database/backups/*_<fecha>.dump`) y devolver el `.env`.

## 7. Aplicar cambios de esquema (Liquibase)

1. Local: `docker compose run --rm liquibase update`. El esquema se aplica también en cada `scripts/local-up.sh`.
2. Base remota: `docker compose --profile ai run --rm --no-deps liquibase update`. El script de arranque ya lo hace.
3. Si el volumen de PostgreSQL ya existía y faltan los roles (`smartmentor_api`, `smartmentor_ai`): `database/scripts/bootstrap.sh` y luego Liquibase (`database/README.md`, sección «Local»).
4. Un changeset ya aplicado que se modifica detiene a Liquibase por checksum: las correcciones siempre van en un changeset nuevo.

Comprobación: Liquibase termina con código 0 (`docker inspect -f '{{.State.ExitCode}}' smartmentor-liquibase` imprime `0` en modo local).

## 8. Rotación de secretos y limpieza

### 8.1 Rotar secretos

Un secreto publicado, filtrado o vencido se rota así (`keycloak/README.md`, «Rotar secretos»):

1. Vacía en `.env` la línea del secreto y ejecuta `scripts/gen-secrets.sh` (solo rellena lo vacío), o edita el valor a mano.
2. Reinicia los servicios que lo reciben: `docker compose up -d keycloak app api`.
3. Aplica al realm ya importado los secretos y el correo: `keycloak/scripts/apply-secrets.sh` (usa `kcadm.sh` dentro del contenedor y no imprime valores).
4. Reinicia `app` y `api` para que relean el secreto.

Casos especiales:

| Qué | Cómo |
| --- | --- |
| Contraseñas de roles de PostgreSQL | PostgreSQL ignora los cambios de `.env` si `database/data/postgres` ya existe: `ALTER ROLE ... PASSWORD ...` en la base y el mismo valor en el `.env` (o `bootstrap.sh`, que sincroniza la contraseña de los roles existentes) |
| Contraseña del administrador de Keycloak | Se cambia en la consola (realm `master`); `KEYCLOAK_ADMIN_PASSWORD` solo vale en el primer arranque |
| Llaves de firma de los tokens | Consola de Keycloak, *Realm settings, Keys, Providers*: crear llaves nuevas con mayor prioridad y borrar las viejas pasado el tiempo de vida de los tokens |

Pendiente, **no existe todavía**: rotar los secretos que estuvieron versionados en el historial de git y limpiar el historial (T-050).

### 8.2 Limpieza

| Qué | Comando | Efecto |
| --- | --- | --- |
| Detener sin perder datos | `scripts/local-up.sh --down` | Elimina contenedores; conserva `database/data/postgres` |
| Copias antiguas | `BACKUP_RETENTION_DAYS=30 database/scripts/backup.sh` | Borra `.dump` de más de 30 días de `database/backups/` |
| Rehacer las bases de la aplicación | `database/scripts/reset-app-schema.sh` (`--yes` omite la confirmación) | **Borra** y recrea `smartmentor` y `smartmentor_test` y aplica Liquibase. Nunca toca la base de Keycloak. Haz `backup.sh` antes |
| Vaciar todo PostgreSQL local | Parar el stack y `sudo rm -rf database/data/postgres` | **Destructivo.** Los datos son del uid 999; tu usuario no puede borrarlos sin `sudo`. Haz `backup.sh` antes |
| Recrear el realm de Keycloak | Detener `keycloak`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION <KEYCLOAK_DB_USER>;` en la base `keycloak` y levantarlo (`keycloak/README.md`, «Compartir un cambio de configuración») | Borra usuarios y sesiones; Keycloak importa de nuevo el realm versionado |

No uses `docker compose down -v` ni borres volúmenes: los datos no están en volúmenes de Docker sino en `database/data/`.

## 9. Diagnóstico de problemas comunes

### 9.1 Puertos ocupados

- **Síntoma:** `scripts/local-up.sh` termina con «Puertos ocupados por otro programa: POSTGRES_PORT=5442 ...».
- **Causa:** otro programa usa un puerto del `.env`. El script revisa `POSTGRES_PORT` (si la base es local), `API_PORT`, `KEYCLOAK_PORT`, `APP_PORT`, `AI_PORT` y `MAILPIT_UI_PORT`; si ya hay contenedores `smartmentor-*` en marcha, no hace la revisión y los actualiza en su sitio.
- **Arreglo:** cambia el puerto en `.env` o libera el puerto. Con `ss -ltnp | grep :5442` (Linux) ves quién lo usa. Si cambias `APP_PORT`, agrega la URI de retorno y el *Web origin* del cliente `smartmentor-ui` en Keycloak con el nuevo puerto (`keycloak/README.md`).
- **Comprobación:** vuelve a ejecutar `scripts/local-up.sh`; la sección «Revisando puertos» dice «Libres.».

### 9.2 `/ready` responde 503

- **API** (`GET http://localhost:8020/ready`): responde `NOT_READY` con `failed_check` igual a `database` o `vector_extension`. Si es `database`: revisa `DATABASE_HOST`, `DATABASE_SSL`, el usuario y la contraseña de `API_DATABASE_*`, y que `smartmentor-postgres` esté sano (o, con Neon, que la cuota no se haya agotado: 9.3). Si es `vector_extension`: la extensión no está instalada; ejecuta `database/scripts/bootstrap.sh` y Liquibase. Detalle en `docker compose logs api`.
- **Servicio de IA** (`GET http://127.0.0.1:8030/ready`): responde `NOT_READY` con la lista `missing`. Las causas que el código enumera son: variables sin definir (proveedor, modelos, presupuesto con proveedor real), base no configurada o inaccesible (`AI_DATABASE_USER`, `AI_DATABASE_PASSWORD`), prompts que no coinciden con `prompts/catalog.yaml` (ver 9.4), precios ausentes en `ai/config/prices.yaml` para un modelo configurado. Con las variables sin definir, `ai-worker` sale con código 1.
- **Comprobación:** `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8020/ready` imprime `200`.

### 9.3 Cuota de Neon agotada

- **Síntoma:** con la base remota, `liquibase`, `api`, `keycloak` y `ai` no conectan; `/ready` falla en `database`.
- **Causa conocida (2026-11-17):** el plan gratis de Neon superó una cuota mensual (lo más probable, las 100 CU-horas de cómputo) y la base dejó de aceptar conexiones hasta el siguiente mes de facturación. El `ai-worker` y el barrido de la API consultan la base de forma periódica y no dejan suspenderse al cómputo (`HANDOFF.md`, «Deuda técnica»).
- **Arreglo:** (a) pasar a un plan de pago; (b) trabajar en local: con el respaldo del equipo (sección 6) o `neon-to-local.sh` si Neon aún responde, y apuntar el `.env` a la base local (sección 5.4.3).
- **Prevención:** `scripts/local-up.sh --down` cuando no se use, o `--no-ai` si no se necesita la IA.

### 9.4 Prompts con CRLF en Windows

- **Síntoma:** `ai-worker` no arranca y `GET /ready` del servicio `ai` reporta `prompts:...` (los hashes de `prompts/catalog.yaml` no coinciden). También: «`.env` tiene saltos de línea de Windows (CRLF)» al ejecutar `local-up.sh`.
- **Causa:** al clonar con conversión automática de fin de línea, los archivos de `prompts/` quedan con CRLF y su SHA-256 cambia (`.gitattributes` fuerza LF en `prompts/**`, `*.sh`, `*.py` y `*.yml`; `proyecto/brief-v2.md` lo registra como diferencia entre Windows y Linux).
- **Arreglo:**
  1. Clona o actualiza el repositorio **dentro del sistema de archivos de WSL2** (no en `/mnt/c`).
  2. Para el `.env`: `sed -i 's/\r$//' .env` (el propio script lo indica).
  3. Para `prompts/`: renormaliza con git (`git add --renormalize prompts` y `git checkout -- prompts`) o conviértelos con `sed -i 's/\r$//'`. Este procedimiento **no está documentado ni probado por el equipo** en el repositorio; el documentado es el arreglo local descrito en `proyecto/brief-v2.md`.
- **Comprobación:** `docker compose logs ai-worker` ya no muestra el error y `GET http://127.0.0.1:8030/ready` responde 200.

### 9.5 OTP de Keycloak

- **Qué se espera:** el flujo `browser-role-otp` pide OTP al iniciar sesión a quien tenga el rol `instructor` o `admin`; la primera vez muestra un código QR para configurarlo. El aprendiz entra sin OTP (`keycloak/README.md`).
- **El instructor o el admin entra sin OTP:** el realm de esa base de Keycloak es anterior al 2026-11-07 y `--import-realm` no reimporta un realm que ya existe (B-035). En local se acepta; en QA y producción hay que crear Keycloak con una base nueva y comprobar que `browserFlow` sea `browser-role-otp`.
- **`REQUIRE_SECOND_FACTOR=true` rechaza a todo el personal:** la API exige que el token indique segundo factor; actívala solo tras verificar que el token del instructor trae el OTP en `amr`. Déjala en `false` para los scripts de desarrollo (`dev-seed-recorrido-users.sh`, `dev-seed-evaluator.sh`), que piden el token con `smartmentor-dev-tools`, que no pide OTP.
- **Código rechazado o dispositivo perdido:** el repositorio no documenta un procedimiento. Es una operación de la consola de Keycloak (realm `smartmentor`, usuario, *Credentials*); si lo haces, queda como paso a documentar.
- **Correo de verificación que no llega:** con el perfil `mail`, se lee en <http://127.0.0.1:8025>; en `.env` deben estar `SMTP_HOST=mailpit`, `SMTP_PORT=1025` y `SMTP_STARTTLS=false`. Sin SMTP, el administrador puede marcar *Email verified* a mano en la consola.

### 9.6 Otros

| Síntoma | Causa y arreglo |
| --- | --- |
| El compose se niega a arrancar con «required variable X is missing a value» | Falta una credencial obligatoria: define `X` en `.env` (o `scripts/gen-secrets.sh`) |
| `Faltan valores en .env: ...` | `local-up.sh` exige `POSTGRES_USER`, `POSTGRES_PASSWORD`, `KEYCLOAK_PORT`, `API_PORT`, `APP_PORT`, `POSTGRES_PORT` y `SEED_USERS_PASSWORD` |
| `AI_LLM_PROVIDER=gemini pero GEMINI_API_KEY está vacía` | Define la clave, usa `AI_LLM_PROVIDER=fake` o `--no-ai` |
| Cambié `POSTGRES_PASSWORD` y no hace efecto | PostgreSQL ignora esas variables si `database/data/postgres` ya existe: `ALTER ROLE` o vaciar el directorio (borra datos) |
| Aviso de `check-env-coherence.py` | Diferencias entre `.env.example` y el código; no bloquea. Ejecútalo con `python3 -I scripts/check-env-coherence.py` y corrige |
| Un contenedor termina con error | `local-up.sh` imprime los últimos 30 renglones de su registro; `docker compose logs <servicio>` para el resto |
| `D1b` muestra «El servicio no está disponible» al subir el syllabus con Neon lenta | Sube `API_UPLOAD_TIMEOUT_SECONDS` (hasta 600) (`.env.example`) |
| El realm no refleja un cambio de configuración | `--import-realm` solo importa si el realm no existe: recrea el realm (sección 8.2) |

## 10. Verificación tras desplegar

Marca cada punto. Todos deben cumplirse antes de dar por bueno un despliegue.

1. **Contenedores.** `docker compose ps`: `postgres` (si es local), `keycloak`, `api`, `app` en `healthy`; con IA, `ai` en `healthy` y `ai-worker` en `Up`; con correo, `mailpit` en `healthy`. `smartmentor-liquibase` terminó con código 0.
2. **API viva y lista.** `curl -s http://localhost:8020/health` responde `{"status":"ok"}` y `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8020/ready` imprime `200`. La documentación abre en <http://localhost:8020/docs>.
3. **Servicio de IA** (si el perfil `ai` está activo). `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8030/ready` imprime `200` (con `503`, mira `missing` en la respuesta).
4. **Keycloak.** `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8180/realms/smartmentor/.well-known/openid-configuration` imprime `200`.
5. **Interfaz.** `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8501/_stcore/health` imprime `200` y <http://localhost:8501> muestra el inicio de sesión.
6. **Esquema.** `docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d smartmentor -Atc "select count(*) from databasechangelog"'` imprime un número mayor que 0 y no cambia al volver a ejecutar Liquibase (con base remota, usa el cliente `psql` contra la conexión directa).
7. **Usuarios y rol.** Inicia sesión con un `SEED_*_EMAIL` y `GET /api/v1/me` (por ejemplo con `api/scripts/token.sh <correo>` y la contraseña en `TOKEN_PASSWORD`) devuelve el usuario y sus roles.
8. **Segundo factor.** Un instructor o administrador de prueba configura OTP en su primer ingreso (si el realm es el versionado).
9. **Correo.** Un registro nuevo genera el correo de verificación visible en Mailpit (perfil `mail`).
10. **Coherencia de configuración.** `python3 -I scripts/check-env-coherence.py` no reporta diferencias.
11. **Respaldo.** `database/scripts/backup.sh` genera los dos `.dump`. Guarda una copia fuera de la máquina (no existe copia automática).
12. **Para un destino fuera del equipo local** (ADR 0020, condiciones): HTTPS en Keycloak y la app, `ai` sin puerto público, secretos rotados respecto del historial de git, `smartmentor-dev-tools` eliminado del realm y Keycloak en `start`. **Hoy ninguno de estos cinco está resuelto en el compose** (excepto que `ai` publica solo en `127.0.0.1`); son T-050 y el cierre del ADR 0020.

## 11. Lo que este runbook no cubre

- Un servidor del piloto: el destino (red de la organización o servicio gestionado) y quién lo opera no están decididos (ADR 0020, DEF-16, P-18).
- HTTPS, proxy inverso y dominios: no existen en el repositorio.
- Despliegue continuo y publicación de imágenes: no existen (la CI solo valida; ver Anexo A, sección 7).
- Copias automáticas de la base y recuperación ante desastres.
- Monitoreo y alertas.
- La prueba en macOS.
