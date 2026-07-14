from __future__ import annotations

"""Sistema de regras do DDR — fantasia medieval.

- 4 atributos: forca, agilidade, mente, presenca (-1 a +3 na criação, soma máx. 5)
- A raça dá +1 num atributo (pode chegar a +4)
- Teste: d20 + atributo vs CD (fácil 10, médio 14, difícil 18)
- 20 natural = crítico, 1 natural = desastre
- HP  = 10 + 2×Força + bônus de classe/raça + 2 por nível acima do 1º
- MP  = base da classe + Mente + bônus de raça + 1 por nível acima do 1º
- XP  = 100 por nível (máx. nível 10)
"""

ATTRIBUTES = ("forca", "agilidade", "mente", "presenca")

ATTR_LABELS = {
    "forca": "Força",
    "agilidade": "Agilidade",
    "mente": "Mente",
    "presenca": "Presença",
}

DIFFICULTIES = {"facil": 10, "medio": 14, "dificil": 18}

ATTR_MIN = -1
ATTR_MAX = 3
ATTR_SUM_MAX = 5

MAX_LEVEL = 10

# XP TOTAL acumulado necessário para estar em cada nível (progressão crescente)
XP_TABLE = {
    1: 0,
    2: 100,
    3: 250,
    4: 450,
    5: 700,
    6: 1000,
    7: 1400,
    8: 1900,
    9: 2500,
    10: 3200,
}


# ───────────────────────────────  Raças  ───────────────────────────────

RACES: dict[str, dict] = {
    "humano": {
        "label": "Humano",
        "attr": None,          # escolhe o atributo (+1)
        "hp": 2, "mp": 1,
        "trait": "Versátil — +1 no atributo à sua escolha, e um pouco de tudo.",
    },
    "elfo": {
        "label": "Elfo",
        "attr": "agilidade",
        "hp": 0, "mp": 3,
        "trait": "Sentidos Élficos — visão aguçada e afinidade natural com a magia.",
    },
    "anao": {
        "label": "Anão",
        "attr": "forca",
        "hp": 4, "mp": 0,
        "trait": "Rocha Viva — corpo resistente, fôlego de mineiro, teimosia de pedra.",
    },
    "halfling": {
        "label": "Halfling",
        "attr": "agilidade",
        "hp": 1, "mp": 1,
        "trait": "Pés Leves — pequeno, silencioso e absurdamente sortudo.",
    },
    "orc": {
        "label": "Orc",
        "attr": "forca",
        "hp": 5, "mp": 0,
        "trait": "Sangue Feroz — músculo, cicatrizes e uma fúria que não sabe recuar.",
    },
    "gnomo": {
        "label": "Gnomo",
        "attr": "mente",
        "hp": 0, "mp": 3,
        "trait": "Engenhoso — curiosidade insaciável e talento para truques e engenhocas.",
    },
    "tiefling": {
        "label": "Tiefling",
        "attr": "presenca",
        "hp": 1, "mp": 2,
        "trait": "Herança Infernal — chifres, cheiro de enxofre e uma presença que incomoda.",
    },
}


# ──────────────────────────────  Classes  ──────────────────────────────

CLASSES: dict[str, dict] = {
    "guerreiro": {
        "label": "Guerreiro",
        "hp": 5, "mp": 0,
        "perk": "Mestre das Armas — treinado em toda arma e armadura; testes de Força em combate são o seu ofício.",
    },
    "ladino": {
        "label": "Ladino",
        "hp": 1, "mp": 2,
        "perk": "Golpe Oportuno — furtividade, fechaduras e o punhal que aparece do nada.",
    },
    "mago": {
        "label": "Mago",
        "hp": -1, "mp": 8,
        "perk": "Arcanista — magias de fogo, gelo, força e ilusão. Corpo frágil, mente perigosa.",
    },
    "clerigo": {
        "label": "Clérigo",
        "hp": 3, "mp": 6,
        "perk": "Bênção Divina — cura os aliados e repele mortos-vivos em nome do seu deus.",
    },
    "patrulheiro": {
        "label": "Patrulheiro",
        "hp": 3, "mp": 3,
        "perk": "Filho da Mata — arco, rastreio e sobrevivência; a floresta é sua aliada.",
    },
    "bardo": {
        "label": "Bardo",
        "hp": 2, "mp": 5,
        "perk": "Inspiração — a palavra e a canção abrem portas que a espada não abre.",
    },
}


# ────────────────────────  Árvore de habilidades  ──────────────────────
# Cada classe desbloqueia uma habilidade nos níveis 1, 3 e 5.
# custo_mp = None → habilidade física/passiva, sem custo de magia.

ABILITIES: dict[str, list[dict]] = {
    "guerreiro": [
        {"level": 1, "name": "Golpe Poderoso", "mp": None,
         "desc": "1×/combate, declare antes de atacar: se acertar, o dano é devastador."},
        {"level": 3, "name": "Grito de Guerra", "mp": 2,
         "desc": "Inimigos próximos vacilam; aliados ganham coragem na próxima ação."},
        {"level": 5, "name": "Fúria do Campeão", "mp": 4,
         "desc": "Por uma cena, ignora dor e ataca como um turbilhão. Ao final, exausto."},
    ],
    "ladino": [
        {"level": 1, "name": "Ataque Furtivo", "mp": None,
         "desc": "Atacando sem ser visto ou um alvo distraído, o golpe fere muito mais fundo."},
        {"level": 3, "name": "Truque de Sombras", "mp": 2,
         "desc": "Desaparece de vista por instantes — reposiciona-se ou some da cena."},
        {"level": 5, "name": "Golpe Fatal", "mp": 4,
         "desc": "1×/combate, contra alvo ferido: tenta encerrar a luta com um único golpe preciso."},
    ],
    "mago": [
        {"level": 1, "name": "Dardo Arcano", "mp": 1,
         "desc": "Projétil de pura energia que raramente erra o alvo."},
        {"level": 3, "name": "Bola de Fogo", "mp": 3,
         "desc": "Explosão flamejante que atinge uma área inteira."},
        {"level": 5, "name": "Tempestade Arcana", "mp": 5,
         "desc": "Relâmpagos e força bruta varrem o campo — devastador, mas exaure."},
    ],
    "clerigo": [
        {"level": 1, "name": "Toque Curativo", "mp": 2,
         "desc": "Fecha ferimentos com a imposição das mãos (cura moderada)."},
        {"level": 3, "name": "Expulsar Mortos-Vivos", "mp": 3,
         "desc": "A luz divina força mortos-vivos a recuar ou fugir."},
        {"level": 5, "name": "Círculo de Proteção", "mp": 5,
         "desc": "Barreira sagrada que protege o grupo por uma cena."},
    ],
    "patrulheiro": [
        {"level": 1, "name": "Tiro Certeiro", "mp": None,
         "desc": "Mirando com calma, o disparo encontra brechas na defesa."},
        {"level": 3, "name": "Companheiro Animal", "mp": None,
         "desc": "Um animal leal (lobo, falcão...) ajuda a rastrear, vigiar e lutar."},
        {"level": 5, "name": "Chuva de Flechas", "mp": 4,
         "desc": "Uma saraivada cobre a área e atinge vários inimigos."},
    ],
    "bardo": [
        {"level": 1, "name": "Canção Inspiradora", "mp": 1,
         "desc": "Sua música dá a um aliado confiança para a próxima ação."},
        {"level": 3, "name": "Zombaria Cruel", "mp": 2,
         "desc": "Palavras afiadas distraem e enfurecem um inimigo, que baixa a guarda."},
        {"level": 5, "name": "Acorde Hipnótico", "mp": 4,
         "desc": "Uma melodia que prende a atenção de todos que a ouvem por instantes."},
    ],
}


def abilities_for(klass: str, level: int) -> list[dict]:
    """Habilidades já desbloqueadas por um personagem dessa classe/nível."""
    return [a for a in ABILITIES.get(klass, []) if a["level"] <= level]


# ──────────────────────────────  Fórmulas  ─────────────────────────────

def level_from_xp(xp: int) -> int:
    level = 1
    for lvl, needed in XP_TABLE.items():
        if int(xp) >= needed:
            level = lvl
    return level


def xp_to_next(xp: int) -> int | None:
    """Quanto falta para o próximo nível (None se já está no máximo)."""
    level = level_from_xp(xp)
    if level >= MAX_LEVEL:
        return None
    return XP_TABLE[level + 1] - int(xp)


def max_hp(forca: int, race: str, klass: str, level: int = 1) -> int:
    r, c = RACES[race], CLASSES[klass]
    return max(1, 10 + 2 * forca + r["hp"] + c["hp"] + 2 * (level - 1))


def max_mp(mente: int, race: str, klass: str, level: int = 1) -> int:
    r, c = RACES[race], CLASSES[klass]
    return max(0, c["mp"] + max(0, mente) + r["mp"] + (level - 1))


def apply_race_bonus(
    attrs: dict[str, int], race: str, escolha: str | None = None
) -> tuple[dict[str, int], str]:
    """Aplica o +1 racial. Retorna (atributos finais, atributo beneficiado)."""
    target = RACES[race]["attr"] or escolha
    if target not in ATTRIBUTES:
        target = "mente"
    final = dict(attrs)
    final[target] = final[target] + 1
    return final, target


def validate_attributes(forca: int, agilidade: int, mente: int, presenca: int) -> str | None:
    """Valida a distribuição BASE (antes do bônus racial)."""
    values = {"Força": forca, "Agilidade": agilidade, "Mente": mente, "Presença": presenca}
    for label, v in values.items():
        if not (ATTR_MIN <= v <= ATTR_MAX):
            return f"{label} deve estar entre {ATTR_MIN} e {ATTR_MAX} (recebi {v})."
    total = sum(values.values())
    if total > ATTR_SUM_MAX:
        return f"A soma dos atributos deve ser no máximo {ATTR_SUM_MAX} (a sua deu {total})."
    return None


RULES_SUMMARY = (
    "Sistema: d20 + atributo vs CD (fácil 10, médio 14, difícil 18). "
    "Atributos: Força, Agilidade, Mente, Presença (-1 a +4). "
    "20 natural = sucesso crítico, 1 natural = desastre. "
    "Magias e habilidades especiais custam MP."
)
