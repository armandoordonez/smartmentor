# Liquibase 5.0.4 con el driver de PostgreSQL.
# Desde la versión 5.0 la imagen oficial no incluye drivers. Antes se instalaban con `lpm add postgresql`,
# que falla de forma intermitente en la CI («Checksum validation failed»). Ahora el driver se descarga con
# una versión fija y se verifica su SHA-256: el resultado es determinista.
#
# Se prueban tres orígenes en orden (Maven Central, su host alterno y el sitio oficial del driver), cada uno
# con `curl --fail` y reintentos, y se acepta el primer archivo cuyo SHA-256 coincide. Con `ADD --checksum` de
# un solo origen, un nodo de caché que sirve un contenido malo de forma estable (se vio en la CI de GitHub:
# el mismo hash equivocado en tres intentos seguidos) hacía fallar el build sin remedio. El checksum no se
# relaja: un archivo distinto no entra.
FROM liquibase/liquibase:5.0.4

# postgresql-42.7.13.jar: SHA-1 a6e1bd21b412d6ffb3df23cd13d507bc2cc9e37d (coincide con el publicado por Maven Central).
ARG PG_DRIVER_VERSION=42.7.13
ARG PG_DRIVER_SHA256=6e0e4cc2d8cae902084f8a2b18728b073a6fd9d1f87c9d8bff8f298c18185b93
RUN set -eu; \
    jar="/liquibase/lib/postgresql-${PG_DRIVER_VERSION}.jar"; \
    for url in \
      "https://repo1.maven.org/maven2/org/postgresql/postgresql/${PG_DRIVER_VERSION}/postgresql-${PG_DRIVER_VERSION}.jar" \
      "https://repo.maven.apache.org/maven2/org/postgresql/postgresql/${PG_DRIVER_VERSION}/postgresql-${PG_DRIVER_VERSION}.jar" \
      "https://jdbc.postgresql.org/download/postgresql-${PG_DRIVER_VERSION}.jar"; do \
      for intento in 1 2; do \
        if curl --fail --silent --show-error --location --retry 3 --retry-delay 2 --output "$jar" "$url" \
          && echo "${PG_DRIVER_SHA256}  ${jar}" | sha256sum --check --status; then \
          echo "Driver ${PG_DRIVER_VERSION} verificado desde ${url}"; exit 0; \
        fi; \
        echo "SHA-256 distinto o descarga fallida desde ${url} (intento ${intento} de 2)" >&2; \
        rm -f "$jar"; sleep 2; \
      done; \
    done; \
    echo "No se pudo obtener postgresql-${PG_DRIVER_VERSION}.jar con el SHA-256 esperado desde ningún origen" >&2; \
    exit 1
