"""Texto de un apunte del curso (R-004): PDF, TXT o MD, con la misma extracción del syllabus.

Reutiliza `syllabus_text` y solo cambia los códigos de error para que la interfaz distinga un
apunte rechazado de un syllabus rechazado: `MATERIAL_NO_TEXT` (422), `MATERIAL_TOO_LARGE` (413) y
`MATERIAL_UNSUPPORTED_TYPE` (415).
"""

import dataclasses
from pathlib import PurePath

from app.common.exceptions import (
    BusinessRuleError,
    DomainError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.domains.courses.syllabus_text import (
    ExtractedSyllabus,
    extract_from_pdf,
    extract_from_text,
)

PDF_SUFFIXES = frozenset({".pdf"})
TEXT_SUFFIXES = frozenset({".txt", ".md", ".markdown"})
ALLOWED_SUFFIXES = PDF_SUFFIXES | TEXT_SUFFIXES

_CODES = {
    "SYLLABUS_NO_TEXT": "MATERIAL_NO_TEXT",
    "SYLLABUS_TOO_LARGE": "MATERIAL_TOO_LARGE",
    "SYLLABUS_UNSUPPORTED_TYPE": "MATERIAL_UNSUPPORTED_TYPE",
}


def _suffix(file_name: str) -> str:
    return PurePath(file_name).suffix.lower()


def _as_material_error(error: DomainError) -> DomainError:
    code = _CODES.get(error.code, error.code)
    return type(error)(error.detail.replace("syllabus", "material"), code=code)


def too_large(max_bytes: int) -> PayloadTooLargeError:
    return PayloadTooLargeError(
        f"The material exceeds {max_bytes // (1024 * 1024)} MB.", code="MATERIAL_TOO_LARGE"
    )


def unsupported() -> UnsupportedMediaTypeError:
    return UnsupportedMediaTypeError(
        "Only PDF, TXT or MD files are accepted as course materials.",
        code="MATERIAL_UNSUPPORTED_TYPE",
    )


async def extract_material(data: bytes, file_name: str) -> ExtractedSyllabus:
    """Texto del archivo según su extensión; el nombre se conserva para mostrarlo en la lista."""
    suffix = _suffix(file_name)
    if suffix not in ALLOWED_SUFFIXES:
        raise unsupported()
    try:
        if suffix in PDF_SUFFIXES:
            return await extract_from_pdf(data, file_name)
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise UnsupportedMediaTypeError(
                "The text file must be UTF-8.", code="MATERIAL_UNSUPPORTED_TYPE"
            ) from exc
        extracted = extract_from_text(text)
    except (BusinessRuleError, PayloadTooLargeError, UnsupportedMediaTypeError) as error:
        raise _as_material_error(error) from error
    return dataclasses.replace(extracted, file_name=file_name)
