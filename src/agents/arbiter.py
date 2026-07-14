from __future__ import annotations

"""Árbitro: lê tudo que os personagens declararam e decide QUAIS ações exigem
rolagem, com qual atributo e CD.

Retorna apenas JSON estruturado — nunca narra, nunca rola dados.
"""

from typing import Any

from .. import config, llm
from ..rules import ATTRIBUTES, DIFFICULTIES, RULES_SUMMARY

SYSTEM = f"""Você é o Árbitro de regras de um RPG de mesa de fantasia medieval. {RULES_SUMMARY}

Você vai receber TUDO que os personagens declararam desde a última narração, marcado por tipo:
  [AÇÃO] — o personagem agiu no mundo
  [FALA (em voz alta)] — o personagem falou
  [PENSAMENTO — PRIVADO, ninguém ouve] — só um pensamento

Para cada PERSONAGEM, decida se algo que ele fez exige um teste de dado.
- [PENSAMENTO] NUNCA exige teste. Pensar não é agir — ignore por completo.
- [FALA] só exige teste se for persuasão/intimidação/enganação sob pressão real (use Presença).
- Falar casualmente, andar, olhar algo óbvio: NÃO exige teste.
- [AÇÃO] arriscada — atacar, escalar, esquivar, furtar, lançar magia difícil: exige teste.
- No MÁXIMO um teste por personagem (o mais importante do que ele declarou).
- Personagens que só pensaram ou só conversaram casualmente NÃO entram na lista.

Responda APENAS com JSON neste formato, sem nenhum outro texto:
{{"rolls": [{{"character": "nome exato do personagem",
             "attribute": "forca"|"agilidade"|"mente"|"presenca",
             "difficulty": "facil"|"medio"|"dificil",
             "reason": "justificativa curta em português"}}]}}

Se ninguém precisar rolar, responda {{"rolls": []}}."""

# Modelos gostam de inventar atributos de outros sistemas (percepção, destreza...).
# Em vez de cair num default arbitrário, traduzimos para o atributo equivalente.
ATTR_ALIASES = {
    "percepcao": "mente", "percepção": "mente", "inteligencia": "mente",
    "inteligência": "mente", "sabedoria": "mente", "intelecto": "mente",
    "destreza": "agilidade", "reflexos": "agilidade", "furtividade": "agilidade",
    "carisma": "presenca", "presença": "presenca", "vontade": "presenca",
    "força": "forca", "constituicao": "forca", "constituição": "forca",
    "vigor": "forca",
}


def _normalize_attr(value: Any) -> str:
    attr = str(value or "").strip().lower()
    if attr in ATTRIBUTES:
        return attr
    return ATTR_ALIASES.get(attr, "agilidade")


async def judge_beat(script: str, party_brief: str, scene: str) -> list[dict[str, Any]]:
    """Julga o beat inteiro. Retorna a lista validada de rolagens necessárias."""
    user = (
        f"CENA ATUAL: {scene or 'início da aventura'}\n"
        f"GRUPO: {party_brief}\n\n"
        f"DECLARAÇÕES DOS PERSONAGENS (na ordem):\n{script}"
    )
    try:
        result = await llm.chat_json(config.MODEL_UTILITY, SYSTEM, user)
    except llm.LLMError:
        return []

    rolls: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in (result.get("rolls") or [])[:8]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("character", "")).strip()
        if not name or name.lower() in seen:
            continue
        attribute = _normalize_attr(item.get("attribute"))
        difficulty = str(item.get("difficulty") or "").strip().lower()
        if difficulty not in DIFFICULTIES:
            difficulty = "medio"
        seen.add(name.lower())
        rolls.append({
            "character": name,
            "attribute": attribute,
            "difficulty": difficulty,
            "reason": str(item.get("reason", ""))[:150],
        })
    return rolls
