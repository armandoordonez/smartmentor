-- Crea las bases de datos del proyecto si no existen (idempotente).
-- Nivel 1 del arranque: Liquibase no crea bases de datos, solo gestiona lo que hay dentro.
--
--   * smartmentor (POSTGRES_DB): la base de la aplicación. Su esquema lo crea Liquibase.
--   * keycloak (KEYCLOAK_DB_NAME): la base de Keycloak, con su propio rol (KEYCLOAK_DB_USER).
--     Keycloak crea y migra sus tablas por su cuenta.
--
-- Los nombres y la contraseña se toman de variables de entorno (psql >= 15, \getenv).
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
