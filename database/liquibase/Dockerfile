# Liquibase 5.0.4 con el driver de PostgreSQL.
# Desde la versión 5.0 la imagen oficial no incluye drivers. Antes se instalaban con `lpm add postgresql`,
# que falla de forma intermitente en la CI («Checksum validation failed») aun con reintentos. Ahora el
# driver se descarga de Maven Central con una versión fija y se verifica su SHA-256: el resultado es
# determinista y el build no depende del gestor de paquetes de Liquibase.
FROM liquibase/liquibase:5.0.4

# postgresql-42.7.13.jar: SHA-1 a6e1bd21b412d6ffb3df23cd13d507bc2cc9e37d (coincide con el publicado por Maven Central).
ADD --checksum=sha256:6e0e4cc2d8cae902084f8a2b18728b073a6fd9d1f87c9d8bff8f298c18185b93 \
    --chown=liquibase:liquibase \
    https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.13/postgresql-42.7.13.jar \
    /liquibase/lib/postgresql-42.7.13.jar
