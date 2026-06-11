# -*- coding: utf-8 -*-
"""
Bot de rolagem do WUX — A Senda dos Mil Reinos.

Comandos:
  /rolar dados:<n> [modificador] [exitos_bonus] [dificuldade] [volatil] [rotulo]
  !r  <expressão> [rótulo]    — ex.: !r 8+2 Golpe do Arado   (+2 = dados extras)
  !rv <expressão> [rótulo]    — ação Volátil (destaca Dissonâncias)
  !ajuda                      — resumo dos comandos

Expressão: 8 · 8+2 · 8+2-1 · 8+1e (o sufixo "e" soma ÊXITOS automáticos,
ex.: Supressão de Reino, em vez de dados).

Regra: pool de d6 · 5–6 = Êxito ✦ · 6 explode · 1 = Dissonância.
"""
import os
import re

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from dados import rolar, Resultado, MAX_DADOS

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

COR_VINHO = 0x8B1E2D     # rolagem normal
COR_OURO = 0xC9A227      # rolagem brilhante (5+ êxitos ou 2+ explosões)
COR_CINZA = 0x5C5F66     # 0 êxitos
COR_VERMELHO = 0xD83C3E  # ação Volátil com Dissonância
RODAPE = "✦ 5–6 = Êxito  ·  💥 6 explode  ·  ⚠️ 1 = Dissonância"

intents = discord.Intents.default()
intents.message_content = True  # necessário para os comandos de prefixo (!r)

bot = commands.Bot(command_prefix=("!",), intents=intents, help_command=None)


# ─────────────────────────────  expressão do !r  ─────────────────────────────

EXPR_HEAD = re.compile(r"^\s*(\d+(?:\s*[+\-]\s*\d+\s*[eE✦]?)*)(.*)$")
EXPR_TOKEN = re.compile(r"([+\-]?)\s*(\d+)\s*([eE✦]?)")


def parse_expressao(texto: str):
    """'8 + 2 - 1 +1e Golpe do Arado' → (base, mod_dados, bonus_exitos, mods, rótulo).

    Números somados com +/− viram DADOS; com sufixo e/✦ viram ÊXITOS automáticos.
    Devolve None se o texto não começa com um número.
    """
    m = EXPR_HEAD.match(texto or "")
    if not m or not m.group(1):
        return None
    expr, rotulo = m.group(1), (m.group(2) or "").strip()

    base = None
    mod_dados = 0
    bonus_exitos = 0
    mods = []
    for sinal, num, e in EXPR_TOKEN.findall(expr):
        n = int(num)
        v = -n if sinal == "-" else n
        if base is None and not e:
            base = v
            continue
        simbolo = "+" if v >= 0 else "−"
        if e:
            bonus_exitos += v
            mods.append(f"{simbolo}{abs(v)}✦")
        else:
            mod_dados += v
            mods.append(f"{simbolo}{abs(v)}")
    if base is None or base < 1:
        return None
    return base, mod_dados, bonus_exitos, mods, rotulo


# ─────────────────────────────  formatação  ─────────────────────────────

def _chip(cadeia: list) -> str:
    """Um dado (e suas explosões) como chip: `6→4` — negrito se êxito, riscado se 1."""
    chip = f"`{'→'.join(str(f) for f in cadeia)}`"
    if any(f >= 5 for f in cadeia):
        chip = f"**{chip}**"
    if any(f == 1 for f in cadeia):
        chip = f"~~{chip}~~"
    return chip


def montar_embed(res: Resultado, rotulo: str = None, volatil: bool = False,
                 base: int = None, mods: list = None, bonus_exitos: int = 0,
                 dificuldade: int = None, autor: discord.abc.User = None) -> discord.Embed:
    total = max(0, res.exitos + bonus_exitos)

    if volatil and res.dissonancias:
        cor = COR_VERMELHO
    elif total == 0:
        cor = COR_CINZA
    elif res.seises >= 2 or total >= 5:
        cor = COR_OURO
    else:
        cor = COR_VINHO

    linhas = []

    # pool + explosões
    pool_txt = f"**{res.pool}d6**"
    if mods and base is not None:
        pool_txt += f"  ({base} {' '.join(mods)})"
    if res.seises:
        pool_txt += f"   ·   💥 {res.seises} explos{'ões' if res.seises > 1 else 'ão'}"
    if volatil:
        pool_txt += "   ·   🌀 Volátil"
    linhas.append(pool_txt)
    linhas.append("")

    # os dados, em chips
    if res.cadeias:
        dados_txt = "  ".join(_chip(c) for c in res.cadeias)
        if len(dados_txt) > 3500:
            dados_txt = dados_txt[:3500] + " …"
        linhas.append(dados_txt)
    linhas.append("")

    # resultado grande
    plural = "Êxito" if total == 1 else "Êxitos"
    linhas.append(f"# {total} ✦ {plural}")
    if bonus_exitos:
        sim = "+" if bonus_exitos > 0 else "−"
        linhas.append(f"-# {res.exitos} rolado(s) {sim} {abs(bonus_exitos)} automático(s)")

    if dificuldade is not None:
        margem = total - dificuldade
        if margem >= 0:
            linhas.append(f"✅ **Passou** (dif. {dificuldade}) — Margem **+{margem}**")
        else:
            linhas.append(f"❌ **Falhou** (dif. {dificuldade}) — faltou **{-margem}**")

    if res.dissonancias:
        if volatil:
            linhas.append(f"⚠️ **{res.dissonancias} Dissonância{'s' if res.dissonancias > 1 else ''}** — ação Volátil!")
        else:
            linhas.append(f"-# ⚠️ {res.dissonancias} Dissonância{'s' if res.dissonancias > 1 else ''}")

    emb = discord.Embed(
        title=f"🎲  {rotulo}" if rotulo else "🎲  Rolagem WUX",
        description="\n".join(linhas),
        color=cor,
    )
    if autor is not None:
        emb.set_author(name=autor.display_name, icon_url=autor.display_avatar.url)
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
    modificador="Bônus/penalidade de DADOS (ex.: +2 postura, -1 ferido).",
    exitos_bonus="Êxitos AUTOMÁTICOS somados ao resultado (ex.: Supressão de Reino).",
    dificuldade="Nº de êxitos do alvo (opcional — mostra passou/falhou e margem).",
    volatil="A ação é Volátil? Destaca as Dissonâncias.",
    rotulo="Nome da rolagem (ex.: Golpe do Arado).",
)
async def rolar_cmd(
    interaction: discord.Interaction,
    dados: app_commands.Range[int, 1, MAX_DADOS],
    modificador: int = 0,
    exitos_bonus: app_commands.Range[int, -10, 10] = 0,
    dificuldade: app_commands.Range[int, 0, 99] = None,
    volatil: bool = False,
    rotulo: str = None,
):
    pool = max(0, dados + (modificador or 0))
    res = rolar(pool, dificuldade=dificuldade)
    mods = []
    if modificador:
        mods.append(f"{'+' if modificador > 0 else '−'}{abs(modificador)}")
    if exitos_bonus:
        mods.append(f"{'+' if exitos_bonus > 0 else '−'}{abs(exitos_bonus)}✦")
    emb = montar_embed(res, rotulo=rotulo, volatil=volatil, base=dados,
                       mods=mods, bonus_exitos=exitos_bonus,
                       dificuldade=dificuldade, autor=interaction.user)
    await interaction.response.send_message(embed=emb)


# ─────────────────────────────  comandos de prefixo  ─────────────────────────────

USO_R = ("Uso: `!r <dados>[+bônus] [rótulo]`\n"
         "ex.: `!r 8` · `!r 8+2 Golpe do Arado` · `!r 8+2-1` · `!r 8+1e` (+1 êxito automático)")


async def _prefixo_rolar(ctx: commands.Context, args: str, volatil: bool):
    parsed = parse_expressao(args)
    if parsed is None:
        await ctx.reply(USO_R)
        return
    base, mod_dados, bonus_exitos, mods, rotulo = parsed
    pool = max(0, base + mod_dados)
    res = rolar(pool)
    emb = montar_embed(res, rotulo=rotulo or None, volatil=volatil, base=base,
                       mods=mods, bonus_exitos=bonus_exitos, autor=ctx.author)
    await ctx.reply(embed=emb)


@bot.command(name="r", aliases=["rolar"])
async def r_cmd(ctx: commands.Context, *, args: str = ""):
    """!r <expressão> [rótulo] — rolagem normal."""
    await _prefixo_rolar(ctx, args, volatil=False)


@bot.command(name="rv", aliases=["rolarv"])
async def rv_cmd(ctx: commands.Context, *, args: str = ""):
    """!rv <expressão> [rótulo] — rolagem de ação Volátil (destaca Dissonâncias)."""
    await _prefixo_rolar(ctx, args, volatil=True)


@bot.command(name="ajuda", aliases=["help", "comandos"])
async def ajuda_cmd(ctx: commands.Context):
    emb = discord.Embed(
        title="🎲  Comandos do WUX",
        color=COR_VINHO,
        description=(
            "**`!r 8`** — rola 8d6\n"
            "**`!r 8+2 Golpe do Arado`** — +2 **dados** (postura etc.) e rótulo\n"
            "**`!r 8+2-1`** — soma e subtrai dados\n"
            "**`!r 8+1e`** — **+1 êxito automático** (ex.: Supressão de Reino)\n"
            "**`!rv 8`** — ação **Volátil** (destaca Dissonâncias)\n"
            "**`/rolar`** — versão completa, com dificuldade (passou/falhou + margem)\n"
        ),
    )
    emb.set_footer(text=RODAPE)
    await ctx.reply(embed=emb)


# ─────────────────────────────  main  ─────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN não encontrado. Crie um arquivo .env com:\n"
            "DISCORD_TOKEN=seu_token_aqui"
        )
    bot.run(TOKEN)
