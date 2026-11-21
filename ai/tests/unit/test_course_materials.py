"""A row of ``course_materials`` as a RAG source (R-004); the query is covered by integration."""

from app.adapters.postgres.course_materials import (
    DEFAULT_LICENSE,
    ORIGIN_LICENSES,
    material_source,
)


def test_the_origin_becomes_the_license_and_the_file_name_the_title() -> None:
    source = material_source(
        {"id": 7, "file_name": "apuntes_u1.pdf", "origin": "open_license", "extracted_text": "x"}
    )
    assert source.title == "Apuntes del curso (apuntes_u1.pdf)"
    assert source.license == ORIGIN_LICENSES["open_license"]
    assert source.text == "x"


def test_a_material_without_name_or_known_origin_still_has_a_title_and_license() -> None:
    source = material_source({"id": 7, "file_name": None, "origin": "other", "extracted_text": "x"})
    assert source.title == "Apuntes del curso #7"
    assert source.license == DEFAULT_LICENSE


def test_every_origin_of_the_api_has_a_license_text() -> None:
    assert set(ORIGIN_LICENSES) == {"own_notes", "open_license", "permitted"}
