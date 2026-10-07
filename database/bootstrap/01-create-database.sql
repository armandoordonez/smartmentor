-- Crea la base de datos de SmartMentor si no existe (idempotente).
-- Nivel 1 del arranque: Liquibase no crea bases de datos, solo gestiona lo que hay dentro.
--
-- La base se toma de la variable de entorno POSTGRES_DB (psql >= 15, \getenv).
--   * Local: el contenedor ejecuta este archivo desde /docker-entrypoint-initdb.d/
--     (solo con el directorio de datos vacío; ahí la base ya existe y no hace nada).
--   * Otros ambientes y recuperación: database/scripts/bootstrap.sh
\getenv target_db POSTGRES_DB

SELECT format('CREATE DATABASE %I', :'target_db')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'target_db')
\gexec
