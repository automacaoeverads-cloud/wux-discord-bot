from __future__ import annotations

"""Tesoureiro: detecta o fim de um combate ou quest e SUGERE XP.

Ele nunca concede nada — só propõe. A sugestão vai para o canal off-topic e o
mestre humano decide com /xp.
"""

from typing import Any, Optional

from .. import config, llm

SYSTEM = """Você acompanha uma mesa de RPG de fantasia medieval como assistente do mestre.
Sua única função: detectar se, NESTE trecho, um MARCO se concluiu — um combate terminou
(inimigos derrotados, rendidos ou em fuga definitiva) ou uma missão/objetivo foi completado.

Seja MUITO conservador:
- Combate ainda em andamento, exploração, conversa, viagem: NÃO é marco.
- Só é marco quando a narração deixa claro que o desafio ACABOU.

Se houver marco, sugira XP para cada personagem que participou:
- escaramuça fácil: 20-30 · combate sério: 40-60 · chefe/feito heroico: 70-100
- missão secundária: 30-50 · missão principal: 60-100
- Todos que participaram recebem o mesmo valor (ajuste ±10 por atuação decisiva).

Responda APENAS com JSON, sem outro texto:
{"milestone": true/false,
 "title": "título curto do marco (ex.: 'Goblins da estrada derrotados')",
 "awards": [{"character": "nome exato", "xp": inteiro, "reason": "por quê, curto"}]}

Sem marco: {"milestone": false, "title": "", "awards": []}"""


async def suggest(
    script: str, facts: str, narration: str, party_brief: str
) -> Optional[dict[str, Any]]:
    """Retorna {"title": ..., "awards": [...]} ou None se não houve marco."""
    user = (
        f"GRUPO:\n{party_brief}\n\n"
        f"O QUE OS JOGADORES FIZERAM:\n{script}\n\n"
        f"RESULTADOS MECÂNICOS:\n{facts}\n\n"
        f"NARRAÇÃO DO MESTRE:\n{narration}\n\n"
        f"Houve um marco concluído neste trecho?"
    )
    try:
        result = await llm.chat_json(config.MODEL_UTILITY, SYSTEM, user)
    except llm.LLMError:
        return None

    if not result.get("milestone"):
        return None

    awards = []
    for item in (result.get("awards") or [])[:10]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("character", "")).strip()
        xp = item.get("xp", 0)
        if name and isinstance(xp, int) and 0 < xp <= 150:
            awards.append({
                "character": name,
                "xp": min(xp, 100),
                "reason": str(item.get("reason", ""))[:100],
            })
    if not awards:
        return None
    return {"title": str(result.get("title", "Marco concluído"))[:100], "awards": awards}
