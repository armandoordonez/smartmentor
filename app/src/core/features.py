"""Interruptores de funciones que la interfaz ya tiene pero la API todavía no soporta.

Cada interruptor se lee **en el momento de usarlo** (`features.NOMBRE`, nunca
`from core.features import NOMBRE`), para que una prueba pueda cambiarlo con `monkeypatch`.
"""

# Prueba de retención (E14, P2). Apagada porque `POST /me/enrollments/{id}/steps/{step_id}/attempts`
# con tipo `retention` responde 422: `AssessmentService.start_topic` solo admite intentos `topic`
# (B-042). Apagada, E11 no muestra la tarjeta ni «Empezar prueba» y E14 solo avisa que aún no está
# disponible, sin llamar a la API. Cuando la API soporte la retención, se cambia a `True` aquí.
RETENTION_AVAILABLE = False
