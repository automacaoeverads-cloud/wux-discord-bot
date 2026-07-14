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

XP_PER_LEVEL = 100
MAX_LEVEL = 10


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


# ──────────────────────────────  Fórmulas  ─────────────────────────────

def level_from_xp(xp: int) -> int:
    return max(1, min(MAX_LEVEL, 1 + int(xp) // XP_PER_LEVEL))


def xp_to_next(xp: int) -> int | None:
    """Quanto falta para o próximo nível (None se já está no máximo)."""
    level = level_from_xp(xp)
    if level >= MAX_LEVEL:
        return None
    return level * XP_PER_LEVEL - int(xp)


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
