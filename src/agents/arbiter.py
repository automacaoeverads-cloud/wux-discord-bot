from __future__ import annotations

"""Árbitro: decide SE a ação exige rolagem, qual atributo e qual CD.

Retorna apenas JSON estruturado — nunca narra, nunca rola dados.
"""

from typing import Any

from .. import config, llm
from ..rules import ATTRIBUTES, DIFFICULTIES, RULES_SUMMARY

SYSTEM = f"""Você é o Árbitro de regras de um RPG de mesa. {RULES_SUMMARY}

Dada a ação de um jogador, decida se ela exige um teste de dado.
Ações triviais (falar, andar, olhar algo óbvio) NÃO exigem teste.
Ações com risco ou chance de falha exigem teste.

Responda APENAS com JSON neste formato, sem nenhum outro texto:
{{"needs_roll": true/false, "attribute": "forca"|"agilidade"|"mente"|"presenca", "difficulty": "facil"|"medio"|"dificil", "reason": "justificativa curta em português"}}

Se needs_roll for false, attribute e difficulty podem ser null."""


async def judge(action: str, character_brief: str, scene: str) -> dict[str, Any]:
    user = (
        f"CENA ATUAL: {scene or 'início da aventura'}\n"
        f"PERSONAGEM: {character_brief}\n"
        f"AÇÃO DECLARADA: {action}"
    )
    result = await llm.chat_json(config.MODEL_UTILITY, SYSTEM, user)

    # Validação dura: se a IA inventar valores, cai em defaults seguros
    needs_roll = bool(result.get("needs_roll", False))
    attribute = result.get("attribute")
    difficulty = result.get("difficulty")
    if needs_roll:
        if attribute not in ATTRIBUTES:
            attribute = "agilidade"
        if difficulty not in DIFFICULTIES:
            difficulty = "medio"
    return {
        "needs_roll": needs_roll,
        "attribute": attribute,
        "difficulty": difficulty,
        "reason": str(result.get("reason", "")),
    }
