# -*- coding: utf-8 -*-
"""
Bot de rolagem do WUX — A Senda dos Mil Reinos.

Comandos:
  /rolar dados:<n> [modificador] [dificuldade] [volatil] [rotulo]   — comando de barra
  !r <n> [rótulo...]      — prefixo (normal)
  !rv <n> [rótulo...]     — prefixo (ação Volátil: destaca Dissonâncias)

Regra: pool de d6 · 5–6 = Êxito ✦ · 6 explode · 1 = Dissonância.
"""
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from dados import rolar, Resultado, MAX_DADOS

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

COR_VINHO = 0x8B1E2D
RODAPE = "5–6 = Êxito ✦  ·  6 explode  ·  1 = Dissonância"

intents = discord.Intents.default()
intents.message_content = True  # necessário para os comandos de prefixo (!r)

bot = commands.Bot(command_prefix=("!",), intents=intents, help_command=None)


# ─────────────────────────────  formatação  ─────────────────────────────

def _fmt_face(f: int) -> str:
    if f >= 5:
        return f"**{f}**"      # êxito (5 ou 6) em negrito
    if f == 1:
        return f"~~{f}~~"      # dissonância riscada
    return str(f)


def _fmt_cadeia(cadeia: list) -> str:
    # explosões ligadas por seta: 6→4 , 6→6→2 ...
    return "→".join(_fmt_face(f) for f in cadeia)


def montar_embed(res: Resultado, rotulo: str = None, volatil: bool = False,
                 modificador: int = 0, base: int = None) -> discord.Embed:
    titulo = f"🎲 {rotulo}" if rotulo else "🎲 Rolagem WUX"
    emb = discord.Embed(title=titulo, color=COR_VINHO)

    # linha do pool (mostra base + modificador quando houver)
    if modificador and base is not None:
        sinal = f"+{modificador}" if modificador > 0 else str(modificador)
        pool_txt = f"**{res.pool}d6**  ({base} {sinal})"
    else:
        pool_txt = f"**{res.pool}d6**"
    emb.add_field(name="Pool", value=pool_txt, inline=True)

    if res.seises:
        emb.add_field(name="Explosões", value=f"💥 {res.seises}", inline=True)

    # os dados
    if res.cadeias:
        linha = "  ".join(_fmt_cadeia(c) for c in res.cadeias)
    else:
        linha = "—"
    if len(linha) > 1010:
        linha = linha[:1010] + " …"
    emb.add_field(name="Dados", value=linha, inline=False)

    # resultado
    plural = "Êxito" if res.exitos == 1 else "Êxitos"
    partes = [f"# {res.exitos} ✦ {plural}"]

    if res.dificuldade is not None:
        if res.passou:
            partes.append(f"✅ **Passou** — Margem **+{res.margem}**")
        else:
            partes.append(f"❌ **Falhou** — faltou **{-res.margem}**")

    if res.dissonancias:
        if volatil:
            partes.append(f"⚠️ **{res.dissonancias} Dissonância(s)** (ação Volátil!)")
        else:
            partes.append(f"⚠️ {res.dissonancias} Dissonância(s)")

    emb.add_field(name="Resultado", value="\n".join(partes), inline=False)
    emb.set_footer(text=RODAPE)
    return emb


# ─────────────────────────────  eventos  ─────────────────────────────

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✓ {len(synced)} comando(s) de barra sincronizado(s).")
    except Exception as e:
        print("✗ Erro ao sincronizar comandos de barra:", e)
    print(f"✓ Logado como {bot.user} (id {bot.user.id}).")
    print("  Pronto para rolar os dados dos Mil Reinos.")


# ─────────────────────────────  comando de barra  ─────────────────────────────

@bot.tree.command(name="rolar", description="Rola um pool de d6 (WUX): 5–6 êxito, 6 explode, 1 dissonância.")
@app_commands.describe(
    dados="Quantos d6 rolar (a reserva).",
    modificador="Bônus/penalidade de dados (ex.: +2 postura, -1 ferido).",
    dificuldade="Nº de êxitos do alvo (opcional — mostra passou/falhou e margem).",
    volatil="A ação é Volátil? Destaca as Dissonâncias.",
    rotulo="Nome da rolagem (ex.: Golpe do Arado).",
)
async def rolar_cmd(
    interaction: discord.Interaction,
    dados: app_commands.Range[int, 1, MAX_DADOS],
    modificador: int = 0,
    dificuldade: app_commands.Range[int, 0, 99] = None,
    volatil: bool = False,
    rotulo: str = None,
):
    base = dados
    pool = max(0, dados + (modificador or 0))
    res = rolar(pool, dificuldade=dificuldade)
    emb = montar_embed(res, rotulo=rotulo, volatil=volatil,
                       modificador=modificador or 0, base=base)
    await interaction.response.send_message(embed=emb)


# ─────────────────────────────  comandos de prefixo  ─────────────────────────────

async def _prefixo_rolar(ctx: commands.Context, pool: int, rotulo: str, volatil: bool):
    if pool < 1:
        await ctx.reply("Preciso de pelo menos **1** dado. Ex.: `!r 8 Golpe do Arado`")
        return
    res = rolar(pool)
    emb = montar_embed(res, rotulo=rotulo or None, volatil=volatil)
    await ctx.reply(embed=emb)


@bot.command(name="r", aliases=["rolar"])
async def r_cmd(ctx: commands.Context, pool: int = None, *, rotulo: str = ""):
    """!r <n> [rótulo] — rolagem normal."""
    if pool is None:
        await ctx.reply("Uso: `!r <dados> [rótulo]`  ·  ex.: `!r 8 Golpe do Arado`")
        return
    await _prefixo_rolar(ctx, pool, rotulo, volatil=False)


@bot.command(name="rv", aliases=["rolarv"])
async def rv_cmd(ctx: commands.Context, pool: int = None, *, rotulo: str = ""):
    """!rv <n> [rótulo] — rolagem de ação Volátil (destaca Dissonâncias)."""
    if pool is None:
        await ctx.reply("Uso: `!rv <dados> [rótulo]`  ·  ex.: `!rv 8 Técnica volátil`")
        return
    await _prefixo_rolar(ctx, pool, rotulo, volatil=True)


@r_cmd.error
@rv_cmd.error
async def _erro_prefixo(ctx: commands.Context, error):
    if isinstance(error, commands.BadArgument):
        await ctx.reply("O número de dados precisa ser inteiro. Ex.: `!r 8 Golpe do Arado`")
    else:
        raise error


# ─────────────────────────────  main  ─────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN não encontrado. Crie um arquivo .env com:\n"
            "DISCORD_TOKEN=seu_token_aqui"
        )
    bot.run(TOKEN)
