"""Clean-up and deterministic option shuffling of generated items (B-062)."""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from app.application.items.polish import (
    clean_item,
    clean_text,
    item_seed,
    polish_items,
    remap_option_refs,
    shuffle_options,
)
from app.domain.contracts.assessment import AssessmentItemLLM, AssessmentItemsLLM

OPTIONS = ["correcta", "distractor uno", "distractor dos", "distractor tres"]


def mc(item_id: str = "q1", **extra: Any) -> AssessmentItemLLM:
    data: dict[str, Any] = {
        "id": item_id,
        "topic_id": "t1",
        "outcome_id": "lo_1",
        "item_type": "multiple_choice",
        "bloom_level": "apply",
        "difficulty": 2,
        "stem": f"Enunciado del ítem {item_id}",
        "options": list(OPTIONS),
        "correct_option": 0,
        "model_answer": "La correcta lo es porque sí.",
        "rubric": [],
        "equivalence_group": "",
    }
    data.update(extra)
    return AssessmentItemLLM.model_validate(data)


def sa(**extra: Any) -> AssessmentItemLLM:
    return mc(
        item_type="short_answer",
        options=[],
        correct_option=-1,
        rubric=[
            {"criterion": "Menciona **el umbral**", "points": 0.5},
            {"criterion": "Justifica", "points": 0.5},
        ],
        **extra,
    )


# ---------- clean_text ----------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("¿Qué hace **git rebase**?", "¿Qué hace git rebase?"),
        ("**Escenario:** el equipo despliega", "Escenario: el equipo despliega"),
        ("Texto con ** suelto", "Texto con suelto"),
        ("Una palabra *en cursiva* aquí", "Una palabra en cursiva aquí"),
        ("La potencia x**2 + y**2 no es negrita", "La potencia x**2 + y**2 no es negrita"),
        ("El código `a**b` queda igual", "El código `a**b` queda igual"),
        ("Espacios   de   más\t y raros ", "Espacios de más y raros"),
        ("", ""),
    ],
)
def test_clean_text_removes_stray_markdown(raw: str, expected: str) -> None:
    assert clean_text(raw) == expected


def test_clean_text_keeps_the_lines_of_a_file_apart() -> None:
    raw = "Dado este robots.txt:\nUser-agent: *\nDisallow: /privado\nAllow: /publico\n¿Qué se rastrea?"
    assert clean_text(raw) == (
        "Dado este robots.txt: User-agent: *; Disallow: /privado; Allow: /publico; ¿Qué se rastrea?"
    )


def test_clean_text_turns_escaped_breaks_and_fences_into_one_line() -> None:
    assert clean_text("Línea uno.\\nLínea dos") == "Línea uno. Línea dos"
    fenced = "Considere:\n```bash\nexport A=1\necho $A\n```\n¿Qué imprime?"
    assert clean_text(fenced) == "Considere: `export A=1`; `echo $A`; ¿Qué imprime?"
    assert clean_text("Usa `printf 'a\\n'` aquí") == "Usa `printf 'a\\n'` aquí"


def test_clean_item_cleans_every_text_and_keeps_options_that_would_collide() -> None:
    item = clean_item(mc(stem="**¿Cuál?**", options=["**A**", "B", "C", "D"]))
    assert item.stem == "¿Cuál?"
    assert item.options == ["A", "B", "C", "D"]
    colliding = clean_item(mc(options=["**A**", "A", "C", "D"]))
    assert colliding.options == ["**A**", "A", "C", "D"]
    short = clean_item(sa(stem="Explica **por qué**", model_answer="Porque **sí**"))
    assert short.stem == "Explica por qué"
    assert short.model_answer == "Porque sí"
    assert [c.criterion for c in short.rubric] == ["Menciona el umbral", "Justifica"]


# ---------- shuffle_options ----------


def test_shuffle_keeps_the_correct_answer_and_the_same_options() -> None:
    for n in range(40):
        item = mc(f"q{n}")
        shuffled = shuffle_options(item)
        assert sorted(shuffled.options) == sorted(item.options)
        assert shuffled.options[shuffled.correct_option] == "correcta"


def test_shuffle_is_deterministic_per_item_and_does_not_use_the_llm_order() -> None:
    item = mc("q7")
    assert shuffle_options(item) == shuffle_options(mc("q7"))
    assert item_seed(item) == item_seed(mc("q7"))
    assert item_seed(item) != item_seed(mc("q8"))
    # the LLM putting the correct answer first or last gives the same final spread
    last = mc("q7", options=[*OPTIONS[1:], OPTIONS[0]], correct_option=3)
    assert shuffle_options(last).options[shuffle_options(last).correct_option] == "correcta"


def test_shuffle_spreads_the_correct_answer_over_the_four_positions() -> None:
    positions = Counter(shuffle_options(mc(f"q{n}")).correct_option for n in range(200))
    assert set(positions) == {0, 1, 2, 3}
    assert max(positions.values()) < 200 * 0.4


def test_shuffle_leaves_short_answer_untouched() -> None:
    item = sa()
    assert shuffle_options(item) == item


def test_shuffle_remaps_the_options_quoted_in_the_rationale() -> None:
    item = mc(
        "q3",
        model_answer="La opción 0 es correcta. La opción 1 confunde, y las opciones 2 y 3 no aplican.",
    )
    shuffled = shuffle_options(item)
    new = [shuffled.options.index(o) for o in OPTIONS]
    assert shuffled.model_answer == (
        f"La opción {new[0]} es correcta. La opción {new[1]} confunde, "
        f"y las opciones {new[2]} y {new[3]} no aplican."
    )


@pytest.mark.parametrize(
    ("text", "base", "expected"),
    [
        ("La opción 2 es correcta", 0, "La opción 0 es correcta"),
        ("Las opciones 1, 2 y 3 fallan", 0, "Las opciones 2, 0 y 1 fallan"),
        ("La opción 3 es correcta", 1, "La opción 1 es correcta"),
        ("La opción C es correcta y la opción A no", 0, "La opción A es correcta y la opción D no"),
        ("Una opción a elegir y la opción 9", 0, "Una opción a elegir y la opción 9"),
    ],
)
def test_remap_option_refs(text: str, base: int, expected: str) -> None:
    # old 0 -> 3, old 1 -> 2, old 2 -> 0, old 3 -> 1
    assert remap_option_refs(text, [3, 2, 0, 1], base=base) == expected


def test_shuffle_detects_a_rationale_that_counts_from_one() -> None:
    item = mc("q5", correct_option=0, model_answer="La opción 1 es correcta; la opción 4 no.")
    shuffled = shuffle_options(item)
    one_based = shuffled.correct_option + 1
    assert shuffled.model_answer.startswith(f"La opción {one_based} es correcta")


def test_polish_items_cleans_and_shuffles_the_whole_batch() -> None:
    batch = AssessmentItemsLLM(
        items=[mc(f"q{n}", stem=f"**Ítem {n}**") for n in range(10)] + [sa(id="q10")]
    )
    polished = polish_items(batch)
    assert [i.id for i in polished.items] == [i.id for i in batch.items]
    assert all("**" not in i.stem for i in polished.items)
    assert {i.correct_option for i in polished.items[:10]} != {0}
    assert all(i.options[i.correct_option] == "correcta" for i in polished.items[:10])
    assert polished == polish_items(batch)
