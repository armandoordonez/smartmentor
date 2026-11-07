"""Configuración común de las pruebas: modo `fixtures`, sin login ni API.

Las variables se fijan **antes** de importar la configuración (que se guarda en caché), y valen
aunque el entorno (CI, `dev.sh`) traiga otras.
"""

import os
from collections.abc import Iterator

import pytest

os.environ["APP_DATA_SOURCE"] = "fixtures"
os.environ["APP_ENV"] = "test"
os.environ.pop("APP_FIXTURES_DIR", None)


@pytest.fixture(autouse=True)
def _fresh_settings() -> Iterator[None]:
    from core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
