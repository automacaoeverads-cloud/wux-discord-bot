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


class DDRBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.db = Database()
        self.orch = Orchestrator(self.db)

    async def setup_hook(self) -> None:
        await self.tree.sync()
        log.info("Comandos sincronizados.")


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


@bot.tree.command(name="iniciar", description="Configura a campanha: canal da mesa e canal das fichas")
@app_commands.describe(mesa="Canal onde a narração acontece", fichas="Canal onde as fichas ficam")
async def iniciar(
    interaction: discord.Interaction,
    mesa: discord.TextChannel,
    fichas: discord.TextChannel,
) -> None:
    bot.db.setup_campaign(interaction.guild.id, mesa.id, fichas.id)
    await interaction.response.send_message(
        f"✅ Campanha configurada! Mesa: {mesa.mention} • Fichas: {fichas.mention}\n"
        f"Criem personagens com `/criar_ficha` e abram a primeira cena com `/cena`."
    )


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


@bot.tree.command(name="cena", description="Abre uma nova cena (o Narrador descreve)")
@app_commands.describe(descricao="Descreva onde o grupo está e o que está acontecendo")
async def cena(interaction: discord.Interaction, descricao: str) -> None:
    campaign = _require_campaign(interaction)
    if campaign is None:
        await interaction.response.send_message("⚠️ Rode `/iniciar` primeiro.", ephemeral=True)
        return
    await interaction.response.defer()
    try:
        narration = await bot.orch.open_scene(interaction.guild.id, descricao)
    except Exception as e:  # noqa: BLE001
        log.exception("Erro ao abrir cena")
        await interaction.followup.send(f"❌ O Narrador tropeçou: `{e}`")
        return
    mesa = interaction.guild.get_channel(campaign["mesa_channel_id"])
    embed = discord.Embed(description=narration, color=discord.Color.purple())
    embed.set_author(name="🎭 Nova cena")
    await mesa.send(embed=embed)
    if interaction.channel_id != campaign["mesa_channel_id"]:
        await interaction.followup.send(f"🎬 Cena aberta em {mesa.mention}!")
    else:
        await interaction.followup.send("🎬 *A cena se abre...*", ephemeral=True)


@bot.tree.command(name="acao", description="Declara a ação do seu personagem")
@app_commands.describe(descricao="O que seu personagem tenta fazer")
async def acao(interaction: discord.Interaction, descricao: str) -> None:
    campaign = _require_campaign(interaction)
    if campaign is None:
        await interaction.response.send_message("⚠️ Rode `/iniciar` primeiro.", ephemeral=True)
        return
    char = bot.db.get_character(interaction.guild.id, interaction.user.id)
    if char is None:
        await interaction.response.send_message("⚠️ Crie um personagem com `/criar_ficha`.", ephemeral=True)
        return
    if not char["alive"]:
        await interaction.response.send_message("☠️ Seu personagem está caído...", ephemeral=True)
        return

    await interaction.response.defer()
    try:
        outcome = await bot.orch.handle_action(
            interaction.guild.id, interaction.user.id, descricao[:500]
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Erro na ação")
        await interaction.followup.send(f"❌ Algo deu errado nos bastidores: `{e}`")
        return

    mesa = interaction.guild.get_channel(campaign["mesa_channel_id"])
    embed = discord.Embed(description=outcome.narration, color=discord.Color.blue())
    embed.set_author(name=f"⚔️ {char['name']}: {descricao[:200]}")
    footer_parts = []
    if outcome.roll_text:
        footer_parts.append(outcome.roll_text.replace("**", ""))
    if outcome.delta_text:
        footer_parts.append(f"📋 {outcome.delta_text}")
    if footer_parts:
        embed.set_footer(text=" | ".join(footer_parts))
    await mesa.send(embed=embed)

    if outcome.delta_text and outcome.character_updated is not None:
        await refresh_sheet(interaction.guild, outcome.character_updated)

    if interaction.channel_id != campaign["mesa_channel_id"]:
        await interaction.followup.send(f"✅ Ação resolvida em {mesa.mention}.")
    else:
        await interaction.followup.send("🎲", ephemeral=True)


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
