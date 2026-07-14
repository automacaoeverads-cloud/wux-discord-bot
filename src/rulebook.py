from __future__ import annotations

"""Os embeds do canal 📖-regras — postados pelo bot no /iniciar."""

import discord

from .rules import (
    ABILITIES, ATTR_SUM_MAX, CLASSES, DIFFICULTIES, MAX_LEVEL, RACES, XP_TABLE,
)

ROXO = discord.Color.purple()
OURO = discord.Color.gold()
AZUL = discord.Color.blue()
VERDE = discord.Color.green()


def embed_sistema() -> discord.Embed:
    e = discord.Embed(
        title="⚔️ Como funciona o sistema",
        color=OURO,
        description=(
            "Um RPG de **fantasia medieval**. Simples de aprender, fácil de jogar.\n"
            "O Mestre é uma IA — mas os **dados são rolados por código**, nunca por ela. "
            "Sucesso é sucesso, falha é falha."
        ),
    )
    e.add_field(
        name="🎲 O teste",
        value=(
            "Quando você tenta algo arriscado, rola-se **1d20 + atributo** contra uma dificuldade:\n"
            f"• **Fácil** — CD {DIFFICULTIES['facil']}\n"
            f"• **Médio** — CD {DIFFICULTIES['medio']}\n"
            f"• **Difícil** — CD {DIFFICULTIES['dificil']}\n"
            "**20 natural** = sucesso crítico · **1 natural** = desastre"
        ),
        inline=False,
    )
    e.add_field(
        name="💪 Os 4 atributos",
        value=(
            "**Força** — bater, carregar, aguentar\n"
            "**Agilidade** — esquivar, escalar, furtar, mirar\n"
            "**Mente** — saber, perceber, magia arcana\n"
            "**Presença** — persuadir, intimidar, liderar, magia divina"
        ),
        inline=True,
    )
    e.add_field(
        name="❤️ Recursos",
        value=(
            "**HP** — sua vida. A 0 você cai.\n"
            "**MP** — sua magia. Cada feitiço custa.\n"
            f"**XP** — sobe até o nível {MAX_LEVEL} (tabela abaixo).\n"
            "Subir de nível: **+2 HP** e **+1 MP**."
        ),
        inline=True,
    )
    e.add_field(
        name="🧙 Criando seu personagem",
        value=(
            "Use **`/criar_ficha`**: escolha nome, **raça**, **classe** e distribua os atributos.\n"
            f"Cada atributo vai de **-1 a +3**, e a **soma não pode passar de {ATTR_SUM_MAX}**.\n"
            "Depois disso, sua **raça soma +1** num atributo (podendo chegar a +4)."
        ),
        inline=False,
    )
    return e


def embed_narrativa() -> discord.Embed:
    e = discord.Embed(
        title="✍️ Como escrever na mesa",
        color=ROXO,
        description=(
            "No canal da mesa, **escreva como seu personagem**. Use estas marcações — "
            "o Mestre entende cada uma de um jeito diferente, e isso muda o jogo."
        ),
    )
    e.add_field(
        name="**negrito** → AÇÃO",
        value=(
            "O que seu personagem **faz** no mundo. Os NPCs **veem**.\n"
            "> `**saco a espada e avanço contra o goblin**`"
        ),
        inline=False,
    )
    e.add_field(
        name="-- travessão → FALA",
        value=(
            "O que seu personagem **diz em voz alta**. Os NPCs **ouvem** — mas só quem estiver perto.\n"
            "> `-- Largue a arma, ou eu largo por você.`"
        ),
        inline=False,
    )
    e.add_field(
        name='"aspas" → PENSAMENTO',
        value=(
            "O que seu personagem **pensa**. É **PRIVADO**: nenhum NPC ouve, adivinha ou reage.\n"
            "O Mestre lê só para entender sua intenção — o mundo **não fica sabendo**.\n"
            '> `"não confio nesse taverneiro"`'
        ),
        inline=False,
    )
    e.add_field(
        name="🎭 Exemplo completo",
        value=(
            "```\n"
            "**empurro a porta devagar, adaga em punho**\n"
            "-- Tem alguém aí? Viemos em paz.\n"
            '"se for uma emboscada, corro"\n'
            "```"
        ),
        inline=False,
    )
    e.set_footer(text="Texto sem marcação nenhuma é lido como AÇÃO.")
    return e


def embed_mestre() -> discord.Embed:
    e = discord.Embed(
        title="🎩 O que o Mestre pode (e não pode) fazer",
        color=AZUL,
        description="As regras que **a IA é obrigada a seguir**. Se ela furar alguma, avise o grupo.",
    )
    e.add_field(
        name="✅ O Mestre controla",
        value="O mundo, os NPCs, as criaturas, o ambiente e as **consequências** das suas ações.",
        inline=False,
    )
    e.add_field(
        name="🚫 O Mestre NUNCA controla",
        value=(
            "**Você.** Ele não escreve suas ações, falas, reações, emoções nem decisões. "
            "Se surge uma ameaça, ele descreve e **passa a vez** — quem reage é você."
        ),
        inline=False,
    )
    e.add_field(
        name="🤫 Sem onisciência",
        value=(
            "Um NPC **só sabe** o que lhe foi dito na frente dele, ou o que ele podia ver.\n"
            "Ele **não lê pensamentos**, não escuta o que foi falado longe, e não sabe "
            "segredos que ninguém contou a ele."
        ),
        inline=False,
    )
    return e


def _tabela(itens: dict, extra_key: str) -> str:
    linhas = []
    for data in itens.values():
        bonus = []
        if data.get("attr"):
            from .rules import ATTR_LABELS
            bonus.append(f"+1 {ATTR_LABELS[data['attr']]}")
        elif "attr" in data:
            bonus.append("+1 à escolha")
        if data.get("hp"):
            bonus.append(f"{data['hp']:+d} HP")
        if data.get("mp"):
            bonus.append(f"{data['mp']:+d} MP")
        selo = f" *({', '.join(bonus)})*" if bonus else ""
        linhas.append(f"**{data['label']}**{selo}\n> {data[extra_key]}")
    return "\n\n".join(linhas)


def embed_racas() -> discord.Embed:
    return discord.Embed(
        title="🧝 Raças",
        color=VERDE,
        description="Sua raça soma **+1 num atributo** (podendo chegar a +4) e ajusta HP/MP.\n\n"
                    + _tabela(RACES, "trait"),
    )


def embed_classes() -> discord.Embed:
    return discord.Embed(
        title="🗡️ Classes",
        color=discord.Color.dark_red(),
        description="Sua classe define quanto **HP** e **MP** você tem, e o que você faz de melhor.\n\n"
                    + _tabela(CLASSES, "perk"),
    )


def embed_xp() -> discord.Embed:
    linhas = []
    anterior = 0
    for lvl, total in XP_TABLE.items():
        if lvl == 1:
            linhas.append("Nível  1 — início")
            continue
        linhas.append(f"Nível {lvl:>2} — {total:>5} XP total  (+{total - anterior})")
        anterior = total
    e = discord.Embed(
        title="✨ Tabela de experiência",
        color=discord.Color.gold(),
        description=(
            "XP vem de **combates vencidos** e **missões concluídas**. "
            "Ao final de cada marco, o Mestre-IA posta uma **sugestão de XP** no canal "
            "off-topic — e o mestre da mesa concede com `/xp`.\n"
            "```\n" + "\n".join(linhas) + "\n```"
            "**Referência por marco:** escaramuça 20-30 · combate sério 40-60 · "
            "chefe 70-100 · missão secundária 30-50 · missão principal 60-100"
        ),
    )
    e.set_footer(text=f"Subir de nível: +2 HP e +1 MP. Nível máximo: {MAX_LEVEL}.")
    return e


def embed_habilidades() -> discord.Embed:
    e = discord.Embed(
        title="🌟 Árvore de habilidades (até o nível 5)",
        color=discord.Color.teal(),
        description=(
            "Cada classe desbloqueia uma habilidade nos níveis **1**, **3** e **5**. "
            "Elas aparecem na sua ficha automaticamente — para usar, basta **descrever na mesa** "
            "(ex.: `**uso Golpe Poderoso no ogro**`). As que têm custo gastam **MP**."
        ),
    )
    for klass, data in CLASSES.items():
        linhas = []
        for a in ABILITIES[klass]:
            custo = f" `{a['mp']} MP`" if a["mp"] else ""
            linhas.append(f"**N{a['level']} · {a['name']}**{custo}\n> {a['desc']}")
        e.add_field(name=f"⚔️ {data['label']}", value="\n".join(linhas), inline=False)
    return e


def embed_comandos() -> discord.Embed:
    e = discord.Embed(title="📋 Comandos", color=discord.Color.greyple())
    e.add_field(
        name="Jogadores",
        value=(
            "**`/criar_ficha`** — cria seu personagem\n"
            "**`/ficha`** — vê sua ficha\n"
            "**`/narrar`** — pede a resposta do Mestre\n"
            "**`/historia`** — o resumo da campanha\n"
            "**`/apagar_ficha`** — recomeça do zero"
        ),
        inline=False,
    )
    e.add_field(
        name="Mestre da mesa",
        value=(
            "**`/cena`** — abre uma cena nova\n"
            "**`/xp`** — dá XP a um jogador\n"
            "**`/iniciar`** — cria a mesa"
        ),
        inline=False,
    )
    e.add_field(
        name="🔄 O ritmo do jogo",
        value=(
            "1. Alguém abre uma cena com `/cena`\n"
            "2. **Vocês conversam e agem livremente na mesa** (quantas mensagens quiserem)\n"
            "3. Quando quiserem a resposta do mundo, alguém usa **`/narrar`**\n"
            "4. O Mestre lê tudo desde a última narração, rola os dados e responde"
        ),
        inline=False,
    )
    e.set_footer(text="Mensagens começando com //, ( ou [ são off-game e o Mestre ignora.")
    return e


def all_embeds() -> list[discord.Embed]:
    return [
        embed_sistema(),
        embed_narrativa(),
        embed_mestre(),
        embed_racas(),
        embed_classes(),
        embed_habilidades(),
        embed_xp(),
        embed_comandos(),
    ]
