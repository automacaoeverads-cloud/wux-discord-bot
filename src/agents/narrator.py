from __future__ import annotations

"""Narrador: transforma fatos mecânicos já decididos em prosa.

Ele recebe os resultados das rolagens como FATOS — não pode mudar desfechos,
inventar itens, matar personagens nem contradizer o estado das fichas.
"""

from .. import config, llm

SYSTEM = """Você é o Narrador (Mestre) de uma mesa de RPG em português brasileiro.

CENÁRIO: fantasia medieval clássica — reinos e vilarejos, tavernas, florestas antigas, \
ruínas e masmorras, magia arcana e divina, criaturas lendárias (goblins, lobos atrozes, \
dragões, mortos-vivos). Tom de aventura: perigo real, mas espaço para heroísmo e humor. \
Sem tecnologia moderna, sem anacronismos.

Regras invioláveis:
1. Os RESULTADOS MECÂNICOS já foram decididos e são fatos. Sucesso é sucesso, falha é falha. Nunca inverta.
2. Narre APENAS as consequências das ações declaradas pelos jogadores. Não crie eventos novos não relacionados.
3. Não altere HP, itens ou condições por conta própria — apenas descreva o que os resultados implicam.
4. Não fale pelos personagens dos jogadores além do que eles declararam.
5. Entrelace as ações de TODOS os personagens que agiram numa cena única e coesa, na ordem que fizer sentido.
6. Use no máximo 3 parágrafos curtos. Termine deixando um gancho para os jogadores agirem.
7. Nunca mencione dados, números ou mecânica na prosa — só a ficção."""


async def narrate_beat(
    script: str,
    facts: str,
    scene: str,
    summary: str,
    recent: str,
    party_brief: str,
) -> str:
    """Narra um 'beat': tudo que os jogadores declararam desde a última narração."""
    user = (
        f"RESUMO DA CAMPANHA ATÉ AQUI: {summary or 'a aventura está começando'}\n\n"
        f"CENA ATUAL: {scene or 'não definida'}\n\n"
        f"EVENTOS RECENTES:\n{recent or '(nenhum)'}\n\n"
        f"GRUPO: {party_brief}\n\n"
        f"O QUE OS PERSONAGENS FIZERAM/DISSERAM (na ordem):\n{script}\n\n"
        f"RESULTADOS MECÂNICOS (FATOS IMUTÁVEIS):\n{facts}\n\n"
        f"Narre a continuação da cena costurando tudo isso."
    )
    return await llm.chat(config.MODEL_NARRATOR, SYSTEM, user, temperature=0.8, max_tokens=800)


async def open_scene(description: str, summary: str, party_brief: str) -> str:
    system = SYSTEM + "\nAgora você vai ABRIR uma cena nova descrita pelo mestre humano."
    user = (
        f"RESUMO DA CAMPANHA: {summary or 'início da aventura'}\n"
        f"GRUPO: {party_brief}\n"
        f"CENA A ABRIR: {description}\n\n"
        f"Descreva a cena de forma imersiva e convide os jogadores a agir."
    )
    return await llm.chat(config.MODEL_NARRATOR, system, user, temperature=0.8, max_tokens=600)
