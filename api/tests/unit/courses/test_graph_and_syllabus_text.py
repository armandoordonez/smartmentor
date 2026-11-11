"""Detección de ciclos de prerrequisitos y extracción de texto del syllabus."""

import pytest

from app.common.exceptions import (
    BusinessRuleError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.domains.courses import graph
from app.domains.courses.syllabus_text import (
    MAX_TEXT_CHARACTERS,
    extract_from_pdf,
    extract_from_text,
)
from tests.pdf_helpers import blank_pdf, text_pdf

# --- grafo ------------------------------------------------------------------------------------


def test_an_acyclic_graph_has_no_cycle() -> None:
    assert graph.find_cycle(graph.build_graph([(3, 2), (3, 1), (2, 1)])) is None


def test_a_direct_cycle_is_reported_as_a_closed_path() -> None:
    cycle = graph.find_cycle(graph.build_graph([(12, 11), (11, 12)]), starts=[12])
    assert cycle == [12, 11, 12]


def test_a_long_cycle_is_found_from_any_node_of_the_graph() -> None:
    cycle = graph.find_cycle(graph.build_graph([(1, 2), (2, 3), (3, 4), (4, 2)]))
    assert cycle is not None
    assert cycle[0] == cycle[-1]
    assert set(cycle) == {2, 3, 4}


def test_a_self_loop_is_a_cycle() -> None:
    assert graph.find_cycle(graph.build_graph([(5, 5)])) == [5, 5]


def test_diamonds_are_not_cycles() -> None:
    edges = [(4, 2), (4, 3), (2, 1), (3, 1)]
    assert graph.find_cycle(graph.build_graph(edges)) is None


def test_starting_from_a_node_outside_the_cycle_still_reports_it_when_reachable() -> None:
    cycle = graph.find_cycle(graph.build_graph([(1, 2), (2, 3), (3, 2)]), starts=[1])
    assert cycle == [2, 3, 2]


def test_a_deep_chain_does_not_overflow_the_stack() -> None:
    edges = [(n, n + 1) for n in range(1, 5000)]
    assert graph.find_cycle(graph.build_graph(edges)) is None


# --- texto del syllabus -----------------------------------------------------------------------


async def test_text_is_extracted_from_a_pdf() -> None:
    extracted = await extract_from_pdf(text_pdf("Introduccion a Machine Learning"), "plan.pdf")
    assert "Machine Learning" in extracted.text
    assert extracted.source_type == "pdf"
    assert extracted.page_count == 1
    assert extracted.char_count > 20
    assert len(extracted.sha256) == 64
    assert extracted.file_name == "plan.pdf"


async def test_a_pdf_without_text_is_rejected_with_syllabus_no_text() -> None:
    with pytest.raises(BusinessRuleError) as error:
        await extract_from_pdf(blank_pdf(), "escaneo.pdf")
    assert error.value.code == "SYLLABUS_NO_TEXT"
    assert error.value.status_code == 422


async def test_a_file_that_is_not_a_pdf_is_unsupported() -> None:
    with pytest.raises(UnsupportedMediaTypeError) as error:
        await extract_from_pdf(b"MZ\x90\x00 esto es un ejecutable", "virus.pdf")
    assert error.value.code == "SYLLABUS_UNSUPPORTED_TYPE"


async def test_a_corrupt_pdf_is_unsupported_not_a_500() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        await extract_from_pdf(b"%PDF-1.4\nesto no es un pdf de verdad", "roto.pdf")


def test_plain_text_is_accepted_and_hashed() -> None:
    extracted = extract_from_text("  Tema 1: regresión lineal\n\nTema 2: árboles  ")
    assert extracted.source_type == "text"
    assert extracted.text.startswith("Tema 1")
    assert extracted.page_count is None
    assert (
        extracted.sha256 == extract_from_text("Tema 1: regresión lineal\n\nTema 2: árboles").sha256
    )


@pytest.mark.parametrize("text", ["", "   \n\t  ", "\x00\x00"])
def test_empty_or_blank_text_is_syllabus_no_text(text: str) -> None:
    with pytest.raises(BusinessRuleError) as error:
        extract_from_text(text)
    assert error.value.code == "SYLLABUS_NO_TEXT"


def test_a_huge_text_is_too_large() -> None:
    with pytest.raises(PayloadTooLargeError) as error:
        extract_from_text("a" * (MAX_TEXT_CHARACTERS + 1))
    assert error.value.code == "SYLLABUS_TOO_LARGE"
    assert error.value.status_code == 413


def test_the_nul_character_is_removed_because_postgres_cannot_store_it() -> None:
    assert extract_from_text("Tema\x00 uno").text == "Tema uno"


def test_fragmented_pdf_text_falls_back_to_layout_mode() -> None:
    from app.domains.courses.syllabus_text import choose_page_text, squeeze_spaces, words_per_line

    sentence = "Este curso tiene como propósito formar al estudiante"
    one_word_per_line = "\n".join(sentence.split())
    layout = "Este   curso  tiene como\npropósito    formar al   estudiante"
    assert words_per_line(one_word_per_line) == 1.0
    chosen = choose_page_text(one_word_per_line, layout)
    assert chosen == "Este curso tiene como\npropósito formar al estudiante"
    assert words_per_line(chosen) > 3
    assert squeeze_spaces("a   b\t\tc  ") == "a b c"


def test_normal_pdf_text_is_kept_as_is() -> None:
    from app.domains.courses.syllabus_text import choose_page_text

    normal = "Introducción al curso de bases de datos\nObjetivos del curso y evaluación"
    assert choose_page_text(normal, "otro   texto") == normal


def test_fragmented_text_stays_if_layout_is_not_better() -> None:
    from app.domains.courses.syllabus_text import choose_page_text

    fragmented = "uno\ndos\ntres"
    assert choose_page_text(fragmented, "uno\ndos") == fragmented


def test_fit_to_length_keeps_short_values_and_shortens_long_ones_uniquely() -> None:
    from app.domains.courses.ingestion import fit_to_length

    assert fit_to_length("lo_corto_1", 50) == "lo_corto_1"
    base = "lo_arquitecturas_y_modelos_de_almacenamiento_de_datos_"
    first, second = fit_to_length(base + "1", 50), fit_to_length(base + "2", 50)
    assert len(first) == 50
    assert len(second) == 50
    assert first != second  # el sufijo de hash conserva la unicidad
    assert fit_to_length(base + "1", 50) == first  # determinista
