# Liquibase 5.0.4 con el driver de PostgreSQL.
# Desde la versión 5.0 la imagen oficial no incluye drivers: se instalan con lpm.
FROM liquibase/liquibase:5.0.4

# La descarga del driver falla de forma intermitente («Checksum validation failed», sobre todo en la CI
# cuando varios trabajos construyen la imagen a la vez): se reintenta con espera creciente antes de rendirse.
RUN for intento in 1 2 3 4 5; do \
      lpm add postgresql --global && exit 0; \
      echo "lpm falló (intento $intento de 5); reintentando..." >&2; \
      sleep $((intento * 5)); \
    done; \
    exit 1
