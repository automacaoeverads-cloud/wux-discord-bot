from __future__ import annotations

"""Escriba: lê a narração e extrai deltas de estado em JSON, por personagem.

Só ele propõe mudanças de ficha — e o código valida e aplica com clamps.
"""

from typing import Any

from .. import config, llm

SYSTEM = """Você é o Escriba de uma mesa de RPG. Leia a narração e extraia APENAS mudanças \
de estado explícitas ou claramente implicadas, para CADA personagem do grupo afetado.

Seja conservador: na dúvida, não mude nada. Dano leve = 1-3, moderado = 4-6, grave = 7-10.

Responda APENAS com JSON, sem outro texto:
{"deltas": [{"character": "nome exato do personagem",
             "hp_change": inteiro (negativo = dano, positivo = cura, 0 = nada),
             "items_added": ["item", ...],
             "items_removed": ["item", ...],
             "conditions_added": ["condição", ...],
             "conditions_removed": ["condição", ...]}]}

Só inclua personagens que tiveram alguma mudança. Se ninguém mudou, responda {"deltas": []}."""

EMPTY_DELTA: dict[str, Any] = {
    "hp_change": 0,
    "items_added": [],
    "items_removed": [],
    "conditions_added": [],
    "conditions_removed": [],
}


def _sanitize(item: dict[str, Any]) -> dict[str, Any]:
    delta = dict(EMPTY_DELTA)
    hp = item.get("hp_change", 0)
    if isinstance(hp, int) and -15 <= hp <= 15:
        delta["hp_change"] = hp
    for key in ("items_added", "items_removed", "conditions_added", "conditions_removed"):
        value = item.get(key, [])
        if isinstance(value, list):
            delta[key] = [str(v)[:60] for v in value[:5]]
    return delta


async def extract_deltas(narration: str, party_brief: str) -> dict[str, dict[str, Any]]:
    """Retorna {nome_do_personagem: delta} apenas para quem mudou."""
    user = (
        f"GRUPO: {party_brief}\n\n"
        f"NARRAÇÃO:\n{narration}\n\n"
        f"Extraia os deltas de estado de cada personagem afetado."
    )
    try:
        result = await llm.chat_json(config.MODEL_UTILITY, SYSTEM, user)
    except llm.LLMError:
        return {}

    deltas: dict[str, dict[str, Any]] = {}
    for item in (result.get("deltas") or [])[:10]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("character", "")).strip()
        if name:
            deltas[name] = _sanitize(item)
    return deltas
