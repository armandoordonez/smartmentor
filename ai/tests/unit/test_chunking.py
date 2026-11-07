"""Fragments of about 900 characters by paragraph (plan 5.4.7)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.application.embeddings.chunking import TARGET_CHARS, split_chunks


def test_short_paragraphs_are_joined_up_to_the_target() -> None:
    text = "\n\n".join(f"Párrafo número {n} con algo de texto." for n in range(10))
    chunks = split_chunks(text)
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].text.count("Párrafo") == 10


def test_a_new_fragment_starts_when_the_next_paragraph_does_not_fit() -> None:
    paragraph = "a" * 500
    chunks = split_chunks(f"{paragraph}\n\n{paragraph}\n\n{paragraph}")
    assert [len(c.text) for c in chunks] == [500, 500, 500]
    assert [c.index for c in chunks] == [0, 1, 2]


def test_a_long_paragraph_is_cut_at_sentence_ends() -> None:
    sentence = "Esta es una oración de prueba con varias palabras. "
    chunks = split_chunks(sentence * 60)
    assert len(chunks) > 1
    assert all(len(c.text) <= TARGET_CHARS for c in chunks)
    assert all(c.text.endswith(".") for c in chunks)


def test_a_paragraph_without_spaces_is_still_cut() -> None:
    chunks = split_chunks("x" * 2500)
    assert len(chunks) == 3
    assert all(len(c.text) <= TARGET_CHARS for c in chunks)


def test_empty_text_has_no_fragments() -> None:
    assert split_chunks("  \n\n  \n") == []


def test_token_count_is_an_estimate_of_four_characters_per_token() -> None:
    (chunk,) = split_chunks("a" * 400)
    assert chunk.token_count == 100


@given(st.text(alphabet=st.characters(blacklist_categories=["Cs"]), max_size=4000))
def test_fragments_never_exceed_the_target_and_keep_the_words(text: str) -> None:
    chunks = split_chunks(text)
    assert all(len(c.text) <= TARGET_CHARS for c in chunks)
    assert "".join("".join(c.text.split()) for c in chunks) == "".join(text.split())
