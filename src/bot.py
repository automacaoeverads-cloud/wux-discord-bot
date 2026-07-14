from __future__ import annotations

import json
import logging
import sqlite3
from typing import Optional

import discord
from discord import app_commands

from . import config, rulebook
from .db import Database
from .orchestrator import Orchestrator
from .rules import (
    ATTR_LABELS, CLASSES, MAX_LEVEL, RACES, abilities_for, apply_race_bonus,
    max_hp, max_mp, validate_attributes, xp_to_next,
)

log = logging.getLogger("ddr.bot")

intents = discord.Intents.default()
intents.message_content = True  # necessário para ler o chat da mesa no /narrar

# Mensagens da mesa que começam assim são off-game e ficam fora da narração
OOC_PREFIXES = ("//", "(", "[")
MAX_BEAT_MESSAGES = 60
MAX_MESSAGE_CHARS = 600


class DDRBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.db = Database()
        self.orch = Orchestrator(self.db)

    async def setup_hook(self) -> None:
        self.tree.on_error = on_app_command_error
        await self.tree.sync()
        log.info("Comandos sincronizados.")


async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    """Nenhum comando morre com traceback cru — o jogador sempre recebe resposta."""
    original = getattr(error, "original", error)
    if isinstance(original, discord.NotFound) and original.code == 10062:
        log.warning("Interação expirou antes do defer (%s).", interaction.command)
        return
    log.exception("Erro no comando %s", interaction.command, exc_info=original)
    msg = f"❌ Algo deu errado: `{original}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


bot = DDRBot()


# ─────────────────────────────  ficha  ─────────────────────────────

def _barra(atual: int, total: int, tamanho: int = 10) -> str:
    if total <= 0:
        return "─" * tamanho
    cheio = max(0, min(tamanho, round(atual / total * tamanho)))
    return "█" * cheio + "░" * (tamanho - cheio)


def sheet_embed(row: sqlite3.Row) -> discord.Embed:
    race = RACES.get(row["race"], {}).get("label", row["race"])
    klass = CLASSES.get(row["klass"], {}).get("label", row["klass"])

    if not row["alive"]:
        color = discord.Color.dark_red()
    elif row["hp"] <= row["hp_max"] // 4:
        color = discord.Color.red()
    elif row["hp"] <= row["hp_max"] // 2:
        color = discord.Color.orange()
    else:
        color = discord.Color.green()

    embed = discord.Embed(
        title=f"📜 {row['name']}",
        description=f"**{race} {klass}** · Nível **{row['level']}**",
        color=color,
    )

    embed.add_field(
        name="❤️ Vida",
        value=f"`{_barra(row['hp'], row['hp_max'])}`\n**{row['hp']}** / {row['hp_max']} HP",
        inline=True,
    )
    embed.add_field(
        name="🔮 Magia",
        value=f"`{_barra(row['mp'], row['mp_max'])}`\n**{row['mp']}** / {row['mp_max']} MP",
        inline=True,
    )

    falta = xp_to_next(row["xp"])
    xp_txt = f"**{row['xp']}** XP\n"
    xp_txt += f"-# faltam {falta} p/ o nível {row['level'] + 1}" if falta else f"-# nível máximo ({MAX_LEVEL})"
    embed.add_field(name="✨ Experiência", value=xp_txt, inline=True)

    embed.add_field(
        name="💪 Atributos",
        value="  ".join(
            f"**{ATTR_LABELS[a][:3]}** `{row[a]:+d}`"
            for a in ("forca", "agilidade", "mente", "presenca")
        ),
        inline=False,
    )

    skills = abilities_for(row["klass"], row["level"])
    if skills:
        embed.add_field(
            name="🌟 Habilidades",
            value="\n".join(
                f"• **{a['name']}**" + (f" `{a['mp']} MP`" if a["mp"] else "")
                for a in skills
            ),
            inline=False,
        )

    inventory = json.loads(row["inventory"])
    embed.add_field(
        name="🎒 Inventário",
        value="\n".join(f"• {i}" for i in inventory) or "*vazio*",
        inline=True,
    )
    conditions = json.loads(row["conditions"])
    embed.add_field(
        name="🌀 Condições",
        value="\n".join(f"• {c}" for c in conditions) or "*nenhuma*",
        inline=True,
    )

    if not row["alive"]:
        embed.set_footer(text="☠️ Caído — precisa de ajuda urgente")
    return embed


async def refresh_sheet(guild: discord.Guild, row: sqlite3.Row) -> None:
    """Posta ou edita o embed da ficha no canal de fichas."""
    campaign = bot.db.get_campaign(guild.id)
    if campaign is None:
        return
    channel = guild.get_channel(campaign["fichas_channel_id"])
    if channel is None:
        return
    embed = sheet_embed(row)
    message_id = row["sheet_message_id"]
    if message_id:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=embed)
            return
        except discord.NotFound:
            pass
    msg = await channel.send(embed=embed)
    bot.db.set_sheet_message(row["id"], msg.id)


def _require_campaign(interaction: discord.Interaction) -> Optional[sqlite3.Row]:
    if interaction.guild is None:
        return None
    return bot.db.get_campaign(interaction.guild.id)


# ─────────────────────────────  /iniciar  ─────────────────────────────

@bot.tree.command(
    name="iniciar",
    description="Cria a mesa: categoria + canais de regras, jogo e fichas",
)
@app_commands.describe(nome="Nome da mesa/campanha (padrão: Mesa de RPG)")
@app_commands.default_permissions(manage_guild=True)
async def iniciar(interaction: discord.Interaction, nome: str = "Mesa de RPG") -> None:
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("⚠️ Use dentro de um servidor.", ephemeral=True)
        return

    nome = nome.strip()[:80] or "Mesa de RPG"
    me = guild.me
    somente_leitura = {
        guild.default_role: discord.PermissionOverwrite(send_messages=False),
        me: discord.PermissionOverwrite(send_messages=True),
    }
    try:
        category = await guild.create_category(f"🎲 {nome}")
        regras = await guild.create_text_channel(
            "📖-regras", category=category, overwrites=somente_leitura,
            topic="Como funciona o sistema, as raças, as classes e como escrever na mesa.",
        )
        mesa = await guild.create_text_channel(
            "🎭-mesa", category=category,
            topic="Escreva como seu personagem: **ação** · -- fala · \"pensamento\". "
                  "Use /narrar para o Mestre responder.",
        )
        fichas = await guild.create_text_channel(
            "📜-fichas", category=category, overwrites=somente_leitura,
            topic="Fichas dos personagens — mantidas pelo bot.",
        )
        off = await guild.create_text_channel(
            "💬-off-topic", category=category,
            topic="Papo fora do jogo. O Mestre posta aqui as sugestões de XP "
                  "ao fim de combates e missões.",
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Preciso da permissão **Gerenciar Canais** para criar a mesa. "
            "Dê a permissão ao bot e rode `/iniciar` de novo.",
            ephemeral=True,
        )
        return

    bot.db.setup_campaign(guild.id, mesa.id, fichas.id, regras.id, off.id)
    bot.db.set_last_narrated(guild.id, 0)

    # O livro de regras da mesa
    for embed in rulebook.all_embeds():
        await regras.send(embed=embed)

    await mesa.send(embed=discord.Embed(
        title=f"🎲 {nome}",
        color=discord.Color.purple(),
        description=(
            f"A mesa está posta. Leiam as regras em {regras.mention}.\n\n"
            "**Comecem assim:**\n"
            "1. `/criar_ficha` — escolham raça, classe e atributos\n"
            "2. `/cena` — alguém abre a primeira cena\n"
            "3. **Escrevam aqui como seus personagens:**\n"
            "> `**ação**` · `-- fala` · `\"pensamento\"`\n"
            "4. `/narrar` — quando quiserem a resposta do Mestre\n\n"
            "-# Pensamentos são privados: nenhum NPC os escuta."
        ),
    ))
    await interaction.followup.send(
        f"✅ Mesa criada! **🎲 {nome}** — {regras.mention} · {mesa.mention} · "
        f"{fichas.mention} · {off.mention}",
        ephemeral=True,
    )


# ─────────────────────────────  fichas  ─────────────────────────────

RACE_CHOICES = [
    app_commands.Choice(name=data["label"], value=key) for key, data in RACES.items()
]
CLASS_CHOICES = [
    app_commands.Choice(name=data["label"], value=key) for key, data in CLASSES.items()
]
ATTR_CHOICES = [
    app_commands.Choice(name=label, value=key) for key, label in ATTR_LABELS.items()
]


@bot.tree.command(name="criar_ficha", description="Cria seu personagem (atributos de -1 a +3, soma máx. 5)")
@app_commands.describe(
    nome="Nome do personagem",
    raca="Sua raça (dá +1 num atributo)",
    classe="Sua classe (define HP e MP)",
    forca="Força (-1 a +3)",
    agilidade="Agilidade (-1 a +3)",
    mente="Mente (-1 a +3)",
    presenca="Presença (-1 a +3)",
    bonus_humano="Só para Humanos: em qual atributo cai o +1 racial",
)
@app_commands.choices(raca=RACE_CHOICES, classe=CLASS_CHOICES, bonus_humano=ATTR_CHOICES)
async def criar_ficha(
    interaction: discord.Interaction,
    nome: str,
    raca: app_commands.Choice[str],
    classe: app_commands.Choice[str],
    forca: int,
    agilidade: int,
    mente: int,
    presenca: int,
    bonus_humano: Optional[app_commands.Choice[str]] = None,
) -> None:
    campaign = _require_campaign(interaction)
    if campaign is None:
        await interaction.response.send_message("⚠️ Rode `/iniciar` primeiro.", ephemeral=True)
        return

    error = validate_attributes(forca, agilidade, mente, presenca)
    if error:
        await interaction.response.send_message(f"⚠️ {error}", ephemeral=True)
        return

    race_key = raca.value
    if RACES[race_key]["attr"] is None and bonus_humano is None:
        await interaction.response.send_message(
            f"⚠️ **{raca.name}** escolhe onde cai o +1 racial — "
            f"informe também o parâmetro `bonus_humano`.",
            ephemeral=True,
        )
        return

    if bot.db.get_character(interaction.guild.id, interaction.user.id):
        await interaction.response.send_message(
            "⚠️ Você já tem um personagem. Use `/apagar_ficha` para recomeçar.", ephemeral=True
        )
        return

    base = {"forca": forca, "agilidade": agilidade, "mente": mente, "presenca": presenca}
    final, beneficiado = apply_race_bonus(
        base, race_key, bonus_humano.value if bonus_humano else None
    )
    klass_key = classe.value
    hp = max_hp(final["forca"], race_key, klass_key, 1)
    mp = max_mp(final["mente"], race_key, klass_key, 1)

    bot.db.create_character(
        interaction.guild.id, interaction.user.id, nome[:50], race_key, klass_key,
        final["forca"], final["agilidade"], final["mente"], final["presenca"], hp, mp,
    )
    row = bot.db.get_character(interaction.guild.id, interaction.user.id)
    await refresh_sheet(interaction.guild, row)

    fichas = interaction.guild.get_channel(campaign["fichas_channel_id"])
    await interaction.response.send_message(
        f"⚔️ **{nome}**, {raca.name} {classe.name}, entrou na aventura!\n"
        f"-# Bônus racial: **+1 {ATTR_LABELS[beneficiado]}** · "
        f"**{hp} HP** · **{mp} MP** · ficha em {fichas.mention if fichas else '#fichas'}"
    )


@bot.tree.command(name="ficha", description="Mostra sua ficha atual")
async def ficha(interaction: discord.Interaction) -> None:
    row = bot.db.get_character(interaction.guild.id, interaction.user.id)
    if row is None:
        await interaction.response.send_message("⚠️ Você não tem personagem. Use `/criar_ficha`.", ephemeral=True)
        return
    await interaction.response.send_message(embed=sheet_embed(row), ephemeral=True)


@bot.tree.command(name="apagar_ficha", description="Apaga seu personagem (irreversível)")
async def apagar_ficha(interaction: discord.Interaction) -> None:
    row = bot.db.get_character(interaction.guild.id, interaction.user.id)
    if row is None:
        await interaction.response.send_message("⚠️ Você não tem personagem.", ephemeral=True)
        return
    bot.db.delete_character(interaction.guild.id, interaction.user.id)
    await interaction.response.send_message(f"🪦 {row['name']} deixou a história.", ephemeral=True)


@bot.tree.command(name="xp", description="Dá XP a um jogador (mestre da mesa)")
@app_commands.describe(jogador="Quem recebe o XP", quantidade="Quanto XP (pode ser negativo)")
@app_commands.default_permissions(manage_guild=True)
async def xp(interaction: discord.Interaction, jogador: discord.Member, quantidade: int) -> None:
    row = bot.db.get_character(interaction.guild.id, jogador.id)
    if row is None:
        await interaction.response.send_message(
            f"⚠️ {jogador.display_name} não tem personagem.", ephemeral=True
        )
        return
    antes, depois = bot.db.grant_xp(row["id"], quantidade)
    atualizado = bot.db.get_character(interaction.guild.id, jogador.id)
    await refresh_sheet(interaction.guild, atualizado)

    msg = f"✨ **{row['name']}** recebeu **{quantidade:+d} XP** (total: {atualizado['xp']})."
    if depois > antes:
        msg += (
            f"\n🎉 **SUBIU PARA O NÍVEL {depois}!** "
            f"Agora tem **{atualizado['hp_max']} HP** e **{atualizado['mp_max']} MP**."
        )
    await interaction.response.send_message(msg)


# ─────────────────────────────  cena & narração  ─────────────────────────────

@bot.tree.command(name="cena", description="Abre uma nova cena (o Narrador descreve)")
@app_commands.describe(descricao="Descreva onde o grupo está e o que está acontecendo")
async def cena(interaction: discord.Interaction, descricao: str) -> None:
    await interaction.response.defer()
    campaign = _require_campaign(interaction)
    if campaign is None:
        await interaction.followup.send("⚠️ Rode `/iniciar` primeiro.", ephemeral=True)
        return
    try:
        narration = await bot.orch.open_scene(interaction.guild.id, descricao)
    except Exception as e:  # noqa: BLE001
        log.exception("Erro ao abrir cena")
        await interaction.followup.send(f"❌ O Narrador tropeçou: `{e}`")
        return
    mesa = interaction.guild.get_channel(campaign["mesa_channel_id"])
    embed = discord.Embed(description=narration, color=discord.Color.purple())
    embed.set_author(name="🎭 Nova cena")
    msg = await mesa.send(embed=embed)
    bot.db.set_last_narrated(interaction.guild.id, msg.id)
    if interaction.channel_id != campaign["mesa_channel_id"]:
        await interaction.followup.send(f"🎬 Cena aberta em {mesa.mention}!")
    else:
        await interaction.followup.send("🎬 *A cena se abre...*", ephemeral=True)


def _coletar_mensagens(
    messages: list[discord.Message],
    chars_by_user: dict[int, sqlite3.Row],
) -> tuple[list[tuple[str, str]], int]:
    """Filtra as mensagens da mesa → [(personagem, texto cru)] e conta as ignoradas."""
    coletadas: list[tuple[str, str]] = []
    sem_ficha = 0
    for m in messages:
        if m.author.bot:
            continue
        text = (m.content or "").strip()
        if not text or text.startswith(OOC_PREFIXES):
            continue
        char = chars_by_user.get(m.author.id)
        if char is None or not char["alive"]:
            sem_ficha += 1
            continue
        coletadas.append((char["name"], text[:MAX_MESSAGE_CHARS]))
    return coletadas, sem_ficha


@bot.tree.command(
    name="narrar",
    description="O Mestre lê tudo que foi dito na mesa desde a última narração e responde",
)
async def narrar(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    campaign = _require_campaign(interaction)
    if campaign is None:
        await interaction.followup.send("⚠️ Rode `/iniciar` primeiro.", ephemeral=True)
        return
    guild = interaction.guild
    mesa = guild.get_channel(campaign["mesa_channel_id"])
    if mesa is None:
        await interaction.followup.send(
            "⚠️ Canal da mesa não encontrado. Rode `/iniciar` de novo.", ephemeral=True
        )
        return

    last_id = campaign["last_narrated_id"]
    after = discord.Object(id=last_id) if last_id else None
    try:
        history = [
            m async for m in mesa.history(limit=MAX_BEAT_MESSAGES, after=after, oldest_first=True)
        ]
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Preciso das permissões **Ver Canal** e **Ler Histórico de Mensagens** na mesa."
        )
        return

    chars_by_user = {r["user_id"]: r for r in bot.db.get_characters(guild.id)}
    mensagens, sem_ficha = _coletar_mensagens(history, chars_by_user)

    if not mensagens:
        dica = " (quem não tem ficha é ignorado — use `/criar_ficha`)" if sem_ficha else ""
        await interaction.followup.send(
            f"🤷 Nada novo na mesa desde a última narração{dica}.", ephemeral=True
        )
        return

    try:
        outcome = await bot.orch.narrate_beat(guild.id, mensagens)
    except Exception as e:  # noqa: BLE001
        log.exception("Erro ao narrar")
        await interaction.followup.send(f"❌ O Mestre tropeçou nos bastidores: `{e}`")
        return

    embed = discord.Embed(description=outcome.narration[:4000], color=discord.Color.dark_teal())
    embed.set_author(name="🎭 O Mestre narra")
    if outcome.roll_lines:
        embed.add_field(name="🎲 Testes", value="\n".join(outcome.roll_lines)[:1000], inline=False)
    if outcome.delta_lines:
        embed.add_field(name="📋 Fichas", value="\n".join(outcome.delta_lines)[:1000], inline=False)
    narr_msg = await mesa.send(embed=embed)

    bot.db.set_last_narrated(guild.id, narr_msg.id)

    for row in outcome.updated_rows:
        await refresh_sheet(guild, row)

    # marco concluído? sugestão de XP vai para o off-topic (o mestre decide com /xp)
    if outcome.reward:
        off = guild.get_channel(campaign["off_channel_id"])
        if off is not None:
            linhas = "\n".join(
                f"• **{a['character']}** — `{a['xp']} XP` — {a['reason']}"
                for a in outcome.reward["awards"]
            )
            sugestao = discord.Embed(
                title=f"✨ Marco: {outcome.reward['title']}",
                color=discord.Color.gold(),
                description=(
                    f"{linhas}\n\n"
                    f"-# Sugestão do Mestre-IA. Quem decide é o mestre da mesa, "
                    f"com `/xp jogador quantidade`."
                ),
            )
            await off.send(embed=sugestao)

    if interaction.channel_id != campaign["mesa_channel_id"]:
        await interaction.followup.send(f"✅ Narração publicada em {mesa.mention}.")
    else:
        await interaction.followup.send("🎭", ephemeral=True)


@bot.tree.command(name="historia", description="Mostra o resumo da campanha até aqui")
async def historia(interaction: discord.Interaction) -> None:
    campaign = _require_campaign(interaction)
    if campaign is None:
        await interaction.response.send_message("⚠️ Rode `/iniciar` primeiro.", ephemeral=True)
        return
    summary = campaign["summary"] or "*A história ainda está sendo escrita...*"
    embed = discord.Embed(title="📖 Crônica da campanha", description=summary[:4000],
                          color=discord.Color.gold())
    if campaign["scene"]:
        embed.add_field(name="Cena atual", value=campaign["scene"][:1000], inline=False)
    await interaction.response.send_message(embed=embed)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if not config.DISCORD_TOKEN or not config.OPENROUTER_API_KEY:
        raise SystemExit("Configure DISCORD_TOKEN e OPENROUTER_API_KEY no .env")
    bot.run(config.DISCORD_TOKEN)
