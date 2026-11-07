-- Crea las bases de datos y los roles del proyecto si no existen (idempotente).
-- Nivel 1 del arranque: Liquibase no crea bases de datos ni roles, solo gestiona lo que hay dentro.
--
--   * smartmentor (POSTGRES_DB): la base de la aplicación. Su esquema lo crea Liquibase.
--   * keycloak (KEYCLOAK_DB_NAME): la base de Keycloak, con su propio rol (KEYCLOAK_DB_USER).
--     Keycloak crea y migra sus tablas por su cuenta.
--   * Roles de la aplicación con mínimo privilegio (v2.0.0, ADR 0019): smartmentor_owner, smartmentor_api
--     y smartmentor_ai (ver el final de este archivo).
--
-- Los nombres y las contraseñas se toman de variables de entorno (psql >= 15, \getenv).
--   * Local: el contenedor ejecuta este archivo desde /docker-entrypoint-initdb.d/
--     (solo con el directorio de datos vacío).
--   * Otros ambientes y recuperación: database/scripts/bootstrap.sh
\getenv target_db POSTGRES_DB

SELECT format('CREATE DATABASE %I', :'target_db')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'target_db')
\gexec

-- Keycloak: solo si las tres variables están definidas.
\getenv kc_db KEYCLOAK_DB_NAME
\getenv kc_user KEYCLOAK_DB_USER
\getenv kc_password KEYCLOAK_DB_PASSWORD
\if :{?kc_db}
\if :{?kc_user}
\if :{?kc_password}
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'kc_user', :'kc_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'kc_user')
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'kc_db', :'kc_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'kc_db')
\gexec
\endif
\endif
\endif

-- ---------------------------------------------------------------------------------------------
-- Roles de base de datos con mínimo privilegio (ADR 0019 y ADR 0009), esquema v2.0.0.
-- Son objetos del clúster y llevan contraseña, por eso se crean aquí y no en Liquibase. Los permisos
-- sobre las tablas los otorga el changeset v2.0.0-045-db-roles-grants.
--
--   OWNER_DATABASE_USER (por defecto smartmentor_owner): dueño del esquema; lo usa Liquibase.
--   API_DATABASE_USER   (por defecto smartmentor_api): la API; lectura y escritura en tablas de negocio.
--   AI_DATABASE_USER    (por defecto smartmentor_ai): el servicio de IA; escribe solo sus tablas.
--
-- Cada rol se crea solo si su contraseña (OWNER_/API_/AI_DATABASE_PASSWORD) está definida y no vacía.
-- Si el rol ya existe, se le sincroniza la contraseña. Los nombres por defecto son los que usa el
-- changeset de permisos: no los cambies sin ajustar ese changeset.
-- ---------------------------------------------------------------------------------------------
\getenv owner_user OWNER_DATABASE_USER
\getenv owner_password OWNER_DATABASE_PASSWORD
\getenv api_user API_DATABASE_USER
\getenv api_password API_DATABASE_PASSWORD
\getenv ai_user AI_DATABASE_USER
\getenv ai_password AI_DATABASE_PASSWORD

-- Variables ausentes se tratan como cadena vacía
\if :{?owner_user}
\else
\set owner_user ''
\endif
\if :{?api_user}
\else
\set api_user ''
\endif
\if :{?ai_user}
\else
\set ai_user ''
\endif
\if :{?owner_password}
\else
\set owner_password ''
\endif
\if :{?api_password}
\else
\set api_password ''
\endif
\if :{?ai_password}
\else
\set ai_password ''
\endif

SELECT coalesce(nullif(:'owner_user', ''), 'smartmentor_owner') AS owner_user,
       coalesce(nullif(:'api_user', ''), 'smartmentor_api') AS api_user,
       coalesce(nullif(:'ai_user', ''), 'smartmentor_ai') AS ai_user,
       (:'owner_password' <> '') AS has_owner,
       (:'api_password' <> '') AS has_api,
       (:'ai_password' <> '') AS has_ai
\gset

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'owner_user', :'owner_password')
WHERE :'has_owner'::boolean AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'owner_user')
\gexec
SELECT format('ALTER ROLE %I PASSWORD %L', :'owner_user', :'owner_password')
WHERE :'has_owner'::boolean AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'owner_user')
\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'api_user', :'api_password')
WHERE :'has_api'::boolean AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'api_user')
\gexec
SELECT format('ALTER ROLE %I PASSWORD %L', :'api_user', :'api_password')
WHERE :'has_api'::boolean AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'api_user')
\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'ai_user', :'ai_password')
WHERE :'has_ai'::boolean AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'ai_user')
\gexec
SELECT format('ALTER ROLE %I PASSWORD %L', :'ai_user', :'ai_password')
WHERE :'has_ai'::boolean AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'ai_user')
\gexec

-- El dueño del esquema debe ser dueño de la base: así Liquibase puede crear objetos y fijar la zona horaria
SELECT format('ALTER DATABASE %I OWNER TO %I', :'target_db', :'owner_user')
WHERE :'has_owner'::boolean
\gexec

-- pgvector no es una extensión de confianza: la crea el administrador en la base de la aplicación
\connect :"target_db"
CREATE EXTENSION IF NOT EXISTS vector;
