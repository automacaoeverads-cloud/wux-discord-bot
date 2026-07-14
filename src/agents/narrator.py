from __future__ import annotations

"""Narrador: transforma fatos mecânicos já decididos em prosa.

Ele recebe o resultado da rolagem como FATO — não pode mudar o desfecho,
inventar itens, matar personagens nem contradizer o estado das fichas.
"""

from .. import config, llm

SYSTEM = """Você é o Narrador de uma mesa de RPG em português brasileiro.

Regras invioláveis:
1. O RESULTADO MECÂNICO já foi decidido e é um fato. Sucesso é sucesso, falha é falha. Nunca inverta.
2. Narre APENAS as consequências da ação declarada. Não crie eventos novos não relacionados.
3. Não altere HP, itens ou condições por conta própria — apenas descreva o que o resultado implica.
4. Não fale pelos personagens dos jogadores além do que eles declararam.
5. Use no máximo 2 parágrafos curtos. Termine deixando um gancho para os jogadores agirem.
6. Nunca mencione dados, números ou mecânica na prosa — só a ficção."""


async def narrate(
    action: str,
    actor_name: str,
    mechanical_result: str,
    scene: str,
    summary: str,
    recent: str,
    party_brief: str,
) -> str:
    user = (
        f"RESUMO DA CAMPANHA ATÉ AQUI: {summary or 'a aventura está começando'}\n\n"
        f"CENA ATUAL: {scene or 'não definida'}\n\n"
        f"EVENTOS RECENTES:\n{recent or '(nenhum)'}\n\n"
        f"GRUPO: {party_brief}\n\n"
        f"AÇÃO DE {actor_name}: {action}\n"
        f"RESULTADO MECÂNICO (FATO IMUTÁVEL): {mechanical_result}\n\n"
        f"Narre a consequência."
    )
    return await llm.chat(config.MODEL_NARRATOR, SYSTEM, user, temperature=0.8, max_tokens=600)


async def open_scene(description: str, summary: str, party_brief: str) -> str:
    system = SYSTEM + "\nAgora você vai ABRIR uma cena nova descrita pelo mestre humano."
    user = (
        f"RESUMO DA CAMPANHA: {summary or 'início da aventura'}\n"
        f"GRUPO: {party_brief}\n"
        f"CENA A ABRIR: {description}\n\n"
        f"Descreva a cena de forma imersiva e convide os jogadores a agir."
    )
    return await llm.chat(config.MODEL_NARRATOR, system, user, temperature=0.8, max_tokens=600)
