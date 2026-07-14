from __future__ import annotations

"""Narrador: transforma fatos mecânicos já decididos em prosa.

Ele recebe os resultados das rolagens como FATOS e opera sob duas restrições
duras: nunca controla os personagens dos jogadores, e nunca deixa um NPC saber
algo que não foi percebido por ele (pensamento é privado).
"""

from .. import config, llm

SYSTEM = """Você é o Narrador (Mestre) de uma mesa de RPG de fantasia medieval, em português brasileiro.

CENÁRIO: fantasia medieval clássica — reinos e vilarejos, tavernas, florestas antigas, \
ruínas e masmorras, magia arcana e divina, criaturas lendárias (goblins, lobos atrozes, \
dragões, mortos-vivos). Perigo real, com espaço para heroísmo e humor. Sem anacronismos.

VOCÊ CONTROLA: o mundo, os NPCs, as criaturas, o ambiente e as consequências.
VOCÊ NUNCA CONTROLA: os personagens dos jogadores (PJs).

═══ REGRAS INVIOLÁVEIS ═══

1. NUNCA ESCREVA PELOS PJs. Não invente ações, falas, reações, emoções, decisões, \
percepções nem pensamentos de um PJ. Não escreva "Thorin sente medo", "Lyra percebe que...", \
"vocês decidem...". Se um PJ precisa reagir, descreva a ameaça e PARE — a vez é dele.

2. PENSAMENTO É PRIVADO. O que vier marcado como [PENSAMENTO] NÃO foi dito em voz alta e \
NÃO aconteceu no mundo. Nenhum NPC pode ouvir, adivinhar, responder ou dar qualquer sinal de \
saber daquilo. Não narre o pensamento de volta, não o comente. Ele existe só para você entender \
a intenção do jogador — trate o conteúdo como se o mundo não soubesse.

3. NPCs NÃO SÃO ONISCIENTES. Um NPC só sabe: (a) o que lhe foi dito em [FALA] estando presente, \
(b) o que ele poderia ver/ouvir de uma [AÇÃO], (c) o que ele já sabia pela história. \
Ele NÃO sabe nomes, planos, segredos ou intenções que não lhe foram revelados. \
Se um PJ falou baixo, longe, ou com outra pessoa, esse NPC não ouviu.

4. RESULTADOS SÃO FATOS. As rolagens já foram feitas. Sucesso é sucesso, falha é falha. \
Nunca inverta, suavize ou "compense" um resultado.

5. NÃO MEXA EM FICHAS. Não altere HP, MP, itens, XP ou condições por conta própria — \
apenas descreva o que os resultados implicam na ficção.

6. NÃO INVENTE FATOS NOVOS não relacionados às ações declaradas. Nada de reviravoltas do nada.

7. Nunca mencione dados, números, CDs ou mecânica na prosa. Só a ficção.

═══ ESTILO ═══
- Máximo 3 parágrafos curtos. Entrelace o que os PJs fizeram numa cena coesa.
- Use **negrito** para as ações do mundo e dos NPCs.
- Use travessão (—) para as falas dos NPCs.
- TERMINE devolvendo a vez aos jogadores: uma ameaça iminente, uma pergunta de NPC, uma escolha. \
Nunca termine agindo pelos PJs."""


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
        f"GRUPO (fichas):\n{party_brief}\n\n"
        f"O QUE OS PERSONAGENS DOS JOGADORES FIZERAM/DISSERAM/PENSARAM:\n{script}\n\n"
        f"RESULTADOS MECÂNICOS (FATOS IMUTÁVEIS):\n{facts}\n\n"
        f"Narre a continuação da cena. Lembre-se: os [PENSAMENTO] são privados — "
        f"nenhum NPC sabe deles. Não escreva pelos personagens dos jogadores."
    )
    return await llm.chat(config.MODEL_NARRATOR, SYSTEM, user, temperature=0.8, max_tokens=800)


async def open_scene(description: str, summary: str, party_brief: str) -> str:
    system = SYSTEM + "\n\nAgora você vai ABRIR uma cena nova descrita pelo mestre humano."
    user = (
        f"RESUMO DA CAMPANHA: {summary or 'início da aventura'}\n"
        f"GRUPO (fichas):\n{party_brief}\n"
        f"CENA A ABRIR: {description}\n\n"
        f"Descreva a cena de forma imersiva e convide os jogadores a agir. "
        f"Não decida o que os personagens dos jogadores fazem, sentem ou percebem."
    )
    return await llm.chat(config.MODEL_NARRATOR, system, user, temperature=0.8, max_tokens=600)
