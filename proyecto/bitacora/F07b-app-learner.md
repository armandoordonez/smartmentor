# Bitácora F07b · `feature/app-v3-learner`

Fase 7, parte 2: páginas del aprendiz (E3 a E14, U1x). Rama creada desde `origin/dev` y con `origin/dev` fusionado (Authlib en `streamlit[auth]`).

## Hecho

- Análisis de la base (`app/`): el cliente ya tiene las operaciones del aprendiz; faltan la verificación pública del badge y las metas de estudio.
- Línea base: 274 pruebas pasan en `app/scripts/dev.sh test`.

## Diseño acordado (por implementar)

- Operaciones nuevas en `clients/ops_learner.py`, modelos en `clients/models_learner.py`, JSON en `tests/fixtures/learner/`.
- Escenarios de fixtures por estado de la inscripción; los errores y la falta de conexión se simulan en las pruebas.
- Sondeo de trabajos con `st.fragment(run_every=...)`; ayudantes de flujo en `core/`.

## Desviaciones frente al plan o al brief

- Ninguna todavía.

## Decisiones

- Los pasos de las pantallas U1x se estiman con el estado del trabajo (la API solo da `progress_label`).

## Problemas y lecciones

- La ejecución anterior se cortó por el límite de uso antes de escribir código; se retoma desde cero.

## Métricas

- Base: 274 pruebas.

## Impacto en el brief

- Ninguno todavía.

## Cambios pedidos a archivos compartidos

- `clients/models.py`: `AssessmentItem` necesita `topic_name` y `bloom_level` opcionales (E3 muestra «Tema · … · Bloom · …»).

## Qué falta

- Todo el código de páginas, fixtures y pruebas.
