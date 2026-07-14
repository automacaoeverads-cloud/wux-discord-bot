from __future__ import annotations

import json
import logging
import sqlite3
from typing import Optional

import discord
from discord import app_commands

from . import config
from .db import Database
from .orchestrator import Orchestrator
from .rules import ATTR_LABELS, max_hp, validate_attributes

log = logging.getLogger("ddr.bot")

intents = discord.Intents.default()
intents.message_content = True  # necessário para ler o chat da mesa no /narrar

# Mensagens da mesa que começam assim são off-game e ficam fora da narração
OOC_PREFIXES = ("//", "(", "[")
MAX_BEAT_MESSAGES = 60      # teto de mensagens processadas por /narrar
MAX_MESSAGE_CHARS = 400     # teto de tamanho por mensagem


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

    # Interação expirada (bot demorou > 3s para o defer): não dá para responder.
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


def sheet_embed(row: sqlite3.Row) -> discord.Embed:
    color = discord.Color.green() if row["alive"] else discord.Color.dark_red()
    embed = discord.Embed(title=f"📜 {row['name']}", color=color)
    embed.add_field(name="HP", value=f"{row['hp']} / {row['hp_max']}", inline=True)
    attrs = "\n".join(
        f"**{ATTR_LABELS[a]}**: {row[a]:+d}"
        for a in ("forca", "agilidade", "mente", "presenca")
    )
    embed.add_field(name="Atributos", value=attrs, inline=True)
    inventory = json.loads(row["inventory"])
    conditions = json.loads(row["conditions"])
    embed.add_field(
        name="Inventário", value="\n".join(f"• {i}" for i in inventory) or "*vazio*", inline=False
    )
    if conditions:
        embed.add_field(name="Condições", value=", ".join(conditions), inline=False)
    if not row["alive"]:
        embed.set_footer(text="☠️ Caído")
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
    description="Cria a mesa: categoria + canais de narração e fichas, tudo automático",
)
@app_commands.describe(nome="Nome da mesa/campanha (padrão: Mesa de RPG)")
@app_commands.default_permissions(manage_guild=True)
async def iniciar(interaction: discord.Interaction, nome: str = "Mesa de RPG") -> None:
    # defer PRIMEIRO: o Discord invalida a interação se não responder em 3s
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("⚠️ Use dentro de um servidor.", ephemeral=True)
        return

    nome = nome.strip()[:80] or "Mesa de RPG"
    me = guild.me
    try:
        category = await guild.create_category(f"🎲 {nome}")
        mesa = await guild.create_text_channel(
            "🎭-mesa", category=category,
            topic="A mesa de jogo: fale como seu personagem. // ou ( ) = fora do jogo. "
                  "Use /narrar quando quiserem a resposta do Mestre.",
        )
        fichas = await guild.create_text_channel(
            "📜-fichas", category=category,
            topic="Fichas dos personagens — mantidas pelo bot.",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(send_messages=False),
                me: discord.PermissionOverwrite(send_messages=True),
            },
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Preciso da permissão **Gerenciar Canais** para criar a mesa. "
            "Dê a permissão ao bot (ou reconvide com o link de convite atualizado) e rode `/iniciar` de novo.",
            ephemeral=True,
        )
        return

    bot.db.setup_campaign(guild.id, mesa.id, fichas.id)
    bot.db.set_last_narrated(guild.id, 0)

    await mesa.send(embed=discord.Embed(
        title=f"🎲 {nome}",
        color=discord.Color.purple(),
        description=(
            "Bem-vindos à mesa! **Fantasia medieval** — reinos, masmorras e magia.\n\n"
            "**Como jogar:**\n"
            "1. Crie seu personagem com `/criar_ficha` (ela aparece em 📜-fichas)\n"
            "2. Abram uma cena com `/cena`\n"
            "3. **Conversem e ajam neste canal**, como seus personagens\n"
            "4. Quando quiserem a resposta do Mestre, usem `/narrar`\n\n"
            "-# Mensagens começando com `//`, `(` ou `[` são fora do jogo e o Mestre ignora."
        ),
    ))
    await interaction.followup.send(
        f"✅ Mesa criada! Categoria **🎲 {nome}** com {mesa.mention} e {fichas.mention}.",
        ephemeral=True,
    )


# ─────────────────────────────  fichas  ─────────────────────────────

@bot.tree.command(name="criar_ficha", description="Cria seu personagem (atributos de -1 a +3, soma máx. 5)")
@app_commands.describe(
    nome="Nome do personagem",
    forca="Força (-1 a +3) — HP = 10 + 2×Força",
    agilidade="Agilidade (-1 a +3)",
    mente="Mente (-1 a +3)",
    presenca="Presença (-1 a +3)",
)
async def criar_ficha(
    interaction: discord.Interaction,
    nome: str,
    forca: int,
    agilidade: int,
    mente: int,
    presenca: int,
) -> None:
    campaign = _require_campaign(interaction)
    if campaign is None:
        await interaction.response.send_message("⚠️ Rode `/iniciar` primeiro.", ephemeral=True)
        return
    error = validate_attributes(forca, agilidade, mente, presenca)
    if error:
        await interaction.response.send_message(f"⚠️ {error}", ephemeral=True)
        return
    if bot.db.get_character(interaction.guild.id, interaction.user.id):
        await interaction.response.send_message(
            "⚠️ Você já tem um personagem. Use `/apagar_ficha` para recomeçar.", ephemeral=True
        )
        return
    bot.db.create_character(
        interaction.guild.id, interaction.user.id, nome[:50],
        forca, agilidade, mente, presenca, max_hp(forca),
    )
    row = bot.db.get_character(interaction.guild.id, interaction.user.id)
    await refresh_sheet(interaction.guild, row)
    await interaction.response.send_message(
        f"⚔️ **{nome}** entrou na aventura! Ficha publicada no canal de fichas."
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
    # A cena zera o "checkpoint": conversas antigas não entram na próxima narração
    bot.db.set_last_narrated(interaction.guild.id, msg.id)
    if interaction.channel_id != campaign["mesa_channel_id"]:
        await interaction.followup.send(f"🎬 Cena aberta em {mesa.mention}!")
    else:
        await interaction.followup.send("🎬 *A cena se abre...*", ephemeral=True)


def _coletar_acoes(
    messages: list[discord.Message],
    chars_by_user: dict[int, sqlite3.Row],
) -> tuple[list[tuple[str, str]], int]:
    """Filtra as mensagens da mesa → [(personagem, texto)] e conta as ignoradas."""
    actions: list[tuple[str, str]] = []
    ignoradas = 0
    for m in messages:
        if m.author.bot:
            continue
        text = (m.content or "").strip()
        if not text or text.startswith(OOC_PREFIXES):
            continue
        char = chars_by_user.get(m.author.id)
        if char is None or not char["alive"]:
            ignoradas += 1
            continue
        actions.append((char["name"], text[:MAX_MESSAGE_CHARS]))
    return actions, ignoradas


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

    # coleta as mensagens desde o checkpoint
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
    actions, ignoradas = _coletar_acoes(history, chars_by_user)

    if not actions:
        dica = " (mensagens de quem não tem ficha são ignoradas — `/criar_ficha`)" if ignoradas else ""
        await interaction.followup.send(
            f"🤷 Nada novo na mesa desde a última narração{dica}.", ephemeral=True
        )
        return

    try:
        outcome = await bot.orch.narrate_beat(guild.id, actions)
    except Exception as e:  # noqa: BLE001
        log.exception("Erro ao narrar")
        await interaction.followup.send(f"❌ O Mestre tropeçou nos bastidores: `{e}`")
        return

    embed = discord.Embed(description=outcome.narration[:4000], color=discord.Color.dark_teal())
    embed.set_author(name="🎭 O Mestre narra")
    if outcome.roll_lines:
        embed.add_field(
            name="🎲 Testes",
            value="\n".join(outcome.roll_lines)[:1000],
            inline=False,
        )
    if outcome.delta_lines:
        embed.add_field(
            name="📋 Fichas",
            value="\n".join(outcome.delta_lines)[:1000],
            inline=False,
        )
    narr_msg = await mesa.send(embed=embed)

    # checkpoint: a narração cobre tudo até aqui
    bot.db.set_last_narrated(guild.id, narr_msg.id)

    for row in outcome.updated_rows:
        await refresh_sheet(guild, row)

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
