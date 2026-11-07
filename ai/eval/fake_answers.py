"""Answers of the fake LLM that depend on the request (tests and the offline evaluation run).

``FakeLlmProvider`` answers each prompt with a fixed example, whose ids do not match the topics of
the run. These functions read the data blocks of the rendered prompt (topic, fragments, items,
rubric...) and build an answer that follows the same rules a real model must follow, so the whole
pipeline can be exercised end to end without a key or network. They are deterministic.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any

from app.adapters.fake_llm import FakeLlmProvider
from app.ports.llm import LlmRequest

_BLOCK = re.compile(r"^<<<\n(.*?)\n>>>$", re.DOTALL | re.MULTILINE)
_FRAGMENT_LINE = re.compile(r"^\[(\d+)\]", re.MULTILINE)
_MC_AND_SA = re.compile(r"(\d+) ítems de opción múltiple.*?y (\d+) de respuesta corta")
_SHORT_ANSWERS = re.compile(r"Además (\d+) ítems de respuesta corta")
_VERSIONS = re.compile(r"escribe (\d+) versión")
_WORD = re.compile(r"\w+", re.UNICODE)

BLOOM_BY_LEVEL = {1: "remember", 2: "apply", 3: "analyze"}
DIFFICULTY_BY_BLOOM = {
    "remember": 1,
    "understand": 1,
    "apply": 2,
    "analyze": 3,
    "evaluate": 3,
    "create": 3,
}
# Distinct words so that two generated stems never look alike to the repetition check.
_VOCABULARY = [
    "ferretería",
    "café",
    "aeropuerto",
    "panadería",
    "hospital",
    "biblioteca",
    "estadio",
    "farmacia",
    "cosecha",
    "puerto",
    "tranvía",
    "vivero",
    "laboratorio",
    "taller",
    "observatorio",
    "mercado",
    "estación",
    "granja",
    "museo",
    "cantera",
    "astillero",
    "invernadero",
    "peluquería",
    "gimnasio",
    "lavandería",
    "librería",
    "carpintería",
    "imprenta",
    "cervecería",
    "joyería",
    "zapatería",
    "floristería",
    "papelería",
    "ladrillera",
    "aserradero",
    "relojería",
    "tintorería",
    "heladería",
    "pastelería",
    "verdulería",
    "carnicería",
    "pescadería",
    "quesería",
    "bodega",
    "salinera",
    "hilandería",
    "curtiduría",
    "fundición",
    "cooperativa",
    "logística",
    "mensajería",
    "acueducto",
    "subestación",
    "refinería",
    "ingenio",
    "trapiche",
    "beneficiadero",
    "secadora",
    "despulpadora",
    "tostadora",
    "molino",
    "cultivo",
    "apiario",
    "piscifactoría",
    "criadero",
    "establo",
    "aviario",
    "cabaña",
    "mirador",
    "sendero",
    "reserva",
    "humedal",
    "páramo",
    "manglar",
    "arrecife",
    "glaciar",
    "cañón",
    "meseta",
    "archipiélago",
    "delta",
    "península",
    "fiordo",
    "estepa",
]


def data_blocks(user: str) -> list[str]:
    return _BLOCK.findall(user)


def _json_block(user: str, position: int) -> Any:
    return json.loads(data_blocks(user)[position])


def _fragment_count(fragments: str) -> int:
    return len(_FRAGMENT_LINE.findall(fragments))


def _pick(seed: int, count: int) -> list[str]:
    start = (seed * 7) % len(_VOCABULARY)
    return [_VOCABULARY[(start + i * 3) % len(_VOCABULARY)] for i in range(count)]


def _stable(text: str, modulo: int) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % modulo


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


# ---------- explanations ----------


def _cite(i: int, n: int) -> str:
    return f"[{min(i, n)}]"


def explanation(kind: str) -> Callable[[LlmRequest], str]:
    def build(request: LlmRequest) -> str:
        blocks = data_blocks(request.user)
        topic = json.loads(blocks[0])
        n = _fragment_count(blocks[-1])
        outcomes = topic["learning_outcomes"]
        count = 3 if kind == "main" else 2
        sections = []
        for i in range(count):
            outcome = outcomes[i % len(outcomes)]["statement"] if outcomes else topic["name"]
            sections.append(
                {
                    "heading": f"{topic['name']}: parte {i + 1}",
                    "body": f"Para lograr «{outcome}» conviene revisar el material "
                    f"{_cite(i + 1, n)}. "
                    f"¿Qué cambiaría si los datos fueran distintos?",
                }
            )
        return _dump(
            {
                "title": topic["name"],
                "sections": sections,
                "worked_example": f"Caso resuelto paso a paso sobre {topic['name']} {_cite(1, n)}.",
                "summary": f"{topic['name']} se resume en los fragmentos {_cite(1, n)}.",
                "reflection_questions": [
                    f"¿Cómo aplicarías {topic['name']} en tu trabajo?",
                    "¿Qué supuesto del método revisarías primero?",
                ],
                "gaps_detected": [],
            }
        )

    return build


def faithfulness(request: LlmRequest) -> str:
    blocks = data_blocks(request.user)
    n = _fragment_count(blocks[1])
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", blocks[0]) if "[" in s]
    claims = []
    for sentence in sentences[:8]:
        cited = sorted({int(c) for c in re.findall(r"\[(\d+)\]", sentence) if 1 <= int(c) <= n})
        claims.append(
            {
                "text": re.sub(r"\s*\[\d+\]", "", sentence),
                "citations": cited,
                "supported": bool(cited),
                "comment": "Soportada por los fragmentos citados." if cited else "Sin cita.",
            }
        )
    return _dump({"claims": claims})


# ---------- item banks ----------


def _stem(index: int, statement: str, seed: int) -> str:
    frames = (
        "En {w0} usan «{s}» como criterio. ¿Qué conclusión es válida en el caso {w1} {w2}?",
        "Un equipo de {w0} revisa «{s}». Con los datos de {w1}, ¿qué decisión conviene tomar?",
        "Al analizar {w0} y {w1} se aplica «{s}». ¿Cuál afirmación describe mejor el resultado?",
        "Durante una auditoría en {w0} aparece «{s}» junto a {w1}. ¿Qué es lo correcto hacer?",
    )
    w = _pick(seed + index, 7)
    stem = frames[index % len(frames)].format(w0=w[0], w1=w[1], w2=w[2], s=statement)
    return f"{stem} Contexto: {w[3]} {w[4]} {w[5]} {w[6]}."


def _options(index: int, seed: int) -> list[str]:
    w = _pick(seed + index + 50, 4)
    return [f"Opción {chr(65 + k)}: {w[k]} {w[(k + 1) % 4]}" for k in range(4)]


def _mc_item(
    item_id: str,
    topic: dict[str, Any],
    outcome: dict[str, Any],
    index: int,
    seed: int,
    group: str,
    bloom: str | None = None,
) -> dict[str, Any]:
    level = bloom or outcome.get("bloom_level") or "understand"
    return {
        "id": item_id,
        "topic_id": topic["topic_id"],
        "outcome_id": outcome["id"],
        "item_type": "multiple_choice",
        "bloom_level": level,
        "difficulty": DIFFICULTY_BY_BLOOM[level],
        "stem": _stem(index, outcome["statement"], seed),
        "options": _options(index, seed),
        "correct_option": (index + seed) % 4,
        "model_answer": "Solo una opción es correcta; las demás confunden conceptos cercanos.",
        "rubric": [],
        "equivalence_group": group,
    }


def _sa_item(
    item_id: str,
    topic: dict[str, Any],
    outcome: dict[str, Any],
    index: int,
    seed: int,
    group: str,
    bloom: str | None = None,
) -> dict[str, Any]:
    level = bloom or outcome.get("bloom_level") or "apply"
    w = _pick(seed + index + 90, 7)
    return {
        "id": item_id,
        "topic_id": topic["topic_id"],
        "outcome_id": outcome["id"],
        "item_type": "short_answer",
        "bloom_level": level,
        "difficulty": DIFFICULTY_BY_BLOOM[level],
        "stem": f"Explica con tus palabras cómo aplicarías «{outcome['statement']}» en {w[0]} "
        f"considerando {w[1]} y {w[2]}. Contexto: {w[3]} {w[4]} {w[5]} {w[6]}.",
        "options": [],
        "correct_option": -1,
        "model_answer": f"Debe relacionar {outcome['statement']} con el caso y justificar.",
        "rubric": [
            {
                "criterion": f"Relaciona el caso de {w[0]} con el resultado de aprendizaje",
                "points": 0.5,
            },
            {"criterion": f"Justifica la decisión considerando {w[1]}", "points": 0.5},
        ],
        "equivalence_group": group,
    }


def quiz_bank(request: LlmRequest) -> str:
    blocks = data_blocks(request.user)
    topic = json.loads(blocks[0])
    previous = json.loads(blocks[-1])
    match = _MC_AND_SA.search(request.user)
    n_mc, n_sa = (int(match[1]), int(match[2])) if match else (4, 1)
    outcomes = topic["learning_outcomes"]
    seed = len(previous) + 1
    items: list[dict[str, Any]] = []
    for i in range(n_mc + n_sa):
        outcome = outcomes[i % len(outcomes)]
        maker = _mc_item if i < n_mc else _sa_item
        items.append(maker(f"q{i + 1}", topic, outcome, i, seed, ""))
    return _dump({"items": items})


def final_bank(request: LlmRequest) -> str:
    blocks = data_blocks(request.user)
    topics = json.loads(blocks[0])
    previous = json.loads(blocks[-1])
    short = _SHORT_ANSWERS.search(request.user)
    versions = _VERSIONS.search(request.user)
    n_sa = int(short[1]) if short else 2
    n_versions = int(versions[1]) if versions else 2
    seed = len(previous) + 1000  # another region of the vocabulary than the quiz banks
    items: list[dict[str, Any]] = []
    slots: list[tuple[dict[str, Any], dict[str, Any], str, bool]] = []
    for topic in topics:
        outcomes = topic["learning_outcomes"]
        slots.append((topic, outcomes[0], "apply", False))
        slots.append((topic, outcomes[-1], "analyze", False))
    for i in range(n_sa):
        topic = topics[i % len(topics)]
        slots.append((topic, topic["learning_outcomes"][-1], "analyze", True))
    for number, (topic, outcome, bloom, is_short) in enumerate(slots, start=1):
        maker = _sa_item if is_short else _mc_item
        for k in range(1, n_versions + 1):
            items.append(
                maker(
                    f"f{number}_v{k}", topic, outcome, number * 5 + k, seed, f"eg_{number}", bloom
                )
            )
    return _dump({"items": items})


# ---------- grading, example, badge, simulated learner ----------


def grading(request: LlmRequest) -> str:
    blocks = data_blocks(request.user)
    rubric = json.loads(blocks[2])
    answer = {w for w in _WORD.findall(blocks[3].casefold()) if len(w) >= 4}
    criteria = []
    for entry in rubric:
        words = {w for w in _WORD.findall(entry["criterion"].casefold()) if len(w) >= 4}
        met = bool(words) and len(words & answer) / len(words) >= 0.4
        criteria.append(
            {
                "criterion": entry["criterion"],
                "met": met,
                "points_awarded": entry["points"] if met else 0.0,
                "evidence": blocks[3][:120] if met else "No aparece en la respuesta.",
            }
        )
    return _dump(
        {
            "criteria": criteria,
            "feedback": "Revisa qué aspectos del caso aún no justificas y replantea tu idea.",
        }
    )


def personal_example(request: LlmRequest) -> str:
    blocks = data_blocks(request.user)
    topic = json.loads(blocks[0])
    return _dump(
        {
            "example": f"Imagina que aplicas {topic['name']} en tu trabajo con tus propios datos.",
            "connection": f"Conecta {topic['name']} con tu experiencia declarada.",
        }
    )


def badge(request: LlmRequest) -> str:
    blocks = data_blocks(request.user)
    topics = json.loads(blocks[2])
    competencies = [f"Aplica {name}" for name in topics[:3]]
    competencies += ["Justifica decisiones", "Interpreta resultados"][
        : max(0, 3 - len(competencies))
    ]
    return _dump(
        {
            "name": blocks[0][:80],
            "description": f"Acredita el dominio de {len(topics)} temas del curso.",
            "criteria": "Aprobar los quices de los temas y la evaluación final.",
            "competencies": competencies,
        }
    )


def simulated_learner(request: LlmRequest) -> str:
    blocks = data_blocks(request.user)
    profile = blocks[0]
    answers = []
    for item in json.loads(blocks[2]):
        if item["item_type"] == "multiple_choice":
            answers.append(
                {
                    "item_id": item["id"],
                    "selected_option": _stable(profile + item["id"], 4),
                    "dont_know": False,
                    "text_answer": "",
                }
            )
        else:
            answers.append(
                {
                    "item_id": item["id"],
                    "selected_option": -1,
                    "dont_know": False,
                    "text_answer": "Lo aplicaría según el caso y justificaría con los datos.",
                }
            )
    return _dump({"answers": answers})


def install_content_fakes(provider: FakeLlmProvider) -> FakeLlmProvider:
    """Make ``provider`` answer the content prompts from the data of each request."""
    provider.set_default("topic_explanation", explanation("main"))
    provider.set_default("remedial_explanation", explanation("remedial"))
    provider.set_default("rag_faithfulness", faithfulness)
    provider.set_default("topic_quiz", quiz_bank)
    provider.set_default("final_assessment", final_bank)
    provider.set_default("short_answer_grading", grading)
    provider.set_default("personalized_example", personal_example)
    provider.set_default("badge_text", badge)
    provider.set_default("simulated_learner", simulated_learner)
    return provider
