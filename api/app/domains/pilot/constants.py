"""Constantes del piloto (los valores coinciden con los CHECK de la base)."""

from enum import StrEnum


class PilotStatus(StrEnum):
    DRAFT = "draft"
    RANDOMIZED = "randomized"
    RUNNING = "running"
    CLOSED = "closed"


class PilotArm(StrEnum):
    PERSONALIZED = "personalized"
    FIXED = "fixed"


# Para comparar los dos brazos hace falta al menos una persona con consentimiento en cada uno.
MIN_PARTICIPANTS = 2
