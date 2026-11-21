"""Formato de tamaños de archivo (V-063): un archivo pequeño no debe decir «0 KB»."""

import pytest

from components.formatting import file_size, plural


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 B"),
        (800, "800 B"),
        (1536, "1,5 KB"),
        (250_000, "244 KB"),
        (3 * 1024 * 1024, "3,0 MB"),
    ],
)
def test_file_size(size: int, expected: str) -> None:
    assert file_size(size) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, "0 días"), (1, "1 día"), (2, "2 días"), (30, "30 días")],
)
def test_plural(count: int, expected: str) -> None:
    assert plural(count, "día", "días") == expected
