from __future__ import annotations

"""Escriba: lê a narração e extrai deltas de estado em JSON.

Só ele propõe mudanças de ficha — e o código valida e aplica com clamps.
"""

from typing import Any

from .. import config, llm

SYSTEM = """Você é o Escriba de uma mesa de RPG. Leia a narração e extraia APENAS mudanças de estado explícitas ou claramente implicadas para o personagem que agiu.

Seja conservador: na dúvida, não mude nada. Dano leve = 1-3, moderado = 4-6, grave = 7-10.

Responda APENAS com JSON, sem outro texto:
{"hp_change": inteiro (negativo = dano, positivo = cura, 0 = nada),
 "items_added": ["item", ...],
 "items_removed": ["item", ...],
 "conditions_added": ["condição", ...],
 "conditions_removed": ["condição", ...]}"""


EMPTY_DELTA: dict[str, Any] = {
    "hp_change": 0,
    "items_added": [],
    "items_removed": [],
    "conditions_added": [],
    "conditions_removed": [],
}


async def extract_delta(narration: str, actor_name: str, character_brief: str) -> dict[str, Any]:
    user = (
        f"PERSONAGEM QUE AGIU: {actor_name} — {character_brief}\n\n"
        f"NARRAÇÃO:\n{narration}\n\n"
        f"Extraia os deltas de estado de {actor_name}."
    )
    try:
        result = await llm.chat_json(config.MODEL_UTILITY, SYSTEM, user)
    except llm.LLMError:
        return dict(EMPTY_DELTA)

    delta = dict(EMPTY_DELTA)
    hp = result.get("hp_change", 0)
    if isinstance(hp, int) and -15 <= hp <= 15:
        delta["hp_change"] = hp
    for key in ("items_added", "items_removed", "conditions_added", "conditions_removed"):
        value = result.get(key, [])
        if isinstance(value, list):
            delta[key] = [str(v)[:60] for v in value[:5]]
    return delta
