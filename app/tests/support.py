"""Rutas y utilidades comunes de las pruebas."""

from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = APP_DIR / "src"
FIXTURES_DIR = APP_DIR / "tests" / "fixtures"
REPO_ROOT = APP_DIR.parent
