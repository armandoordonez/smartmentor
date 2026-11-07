"""Extracción de texto del syllabus (D1b, D1d). La API lo hace con `pypdf`; `ai/` no lee archivos.

Un PDF sin texto extraíble (escaneado, solo imágenes) o un texto vacío se rechazan con
`422 SYLLABUS_NO_TEXT` antes de gastar una llamada al LLM.
"""

import asyncio
import hashlib
import io
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.common.constants import SyllabusSourceType
from app.common.exceptions import (
    BusinessRuleError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)

PDF_MAGIC = b"%PDF"
# Un syllabus real no llega a esto; evita guardar un volcado enorme como «texto».
MAX_TEXT_CHARACTERS = 200_000


@dataclass(frozen=True)
class ExtractedSyllabus:
    source_type: SyllabusSourceType
    text: str
    sha256: str
    byte_size: int
    page_count: int | None
    char_count: int
    file_name: str | None


def _clean(text: str) -> str:
    # PostgreSQL no admite el carácter NUL en columnas `text`.
    return text.replace("\x00", "").strip()


def _count_characters(text: str) -> int:
    """Caracteres que no son espacio: un PDF de solo saltos de línea cuenta como vacío."""
    return len("".join(text.split()))


def _read_pdf(data: bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise UnsupportedMediaTypeError(
                "The PDF is password protected.", code="SYLLABUS_UNSUPPORTED_TYPE"
            )
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PyPdfError, ValueError, OSError, KeyError) as exc:
        raise UnsupportedMediaTypeError(
            "The file is not a readable PDF.", code="SYLLABUS_UNSUPPORTED_TYPE"
        ) from exc
    return "\n".join(pages), len(pages)


async def extract_from_pdf(data: bytes, file_name: str | None) -> ExtractedSyllabus:
    if not data.startswith(PDF_MAGIC):
        raise UnsupportedMediaTypeError("The file is not a PDF.", code="SYLLABUS_UNSUPPORTED_TYPE")
    # pypdf es síncrono y puede tardar con PDF grandes: se ejecuta fuera del event loop.
    raw, pages = await asyncio.to_thread(_read_pdf, data)
    text = _clean(raw)
    return _finish(SyllabusSourceType.PDF, text, data, pages, file_name)


def extract_from_text(text: str) -> ExtractedSyllabus:
    cleaned = _clean(text)
    if len(cleaned) > MAX_TEXT_CHARACTERS:
        raise PayloadTooLargeError(
            f"The syllabus text exceeds {MAX_TEXT_CHARACTERS} characters.",
            code="SYLLABUS_TOO_LARGE",
        )
    return _finish(SyllabusSourceType.TEXT, cleaned, cleaned.encode(), None, None)


def _finish(
    source_type: SyllabusSourceType,
    text: str,
    raw: bytes,
    pages: int | None,
    file_name: str | None,
) -> ExtractedSyllabus:
    chars = _count_characters(text)
    if chars == 0:
        raise BusinessRuleError(
            "The syllabus has no extractable text (a scanned PDF needs OCR or a text copy).",
            code="SYLLABUS_NO_TEXT",
        )
    return ExtractedSyllabus(
        source_type=source_type,
        text=text,
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_size=len(raw),
        page_count=pages,
        char_count=chars,
        file_name=file_name,
    )
