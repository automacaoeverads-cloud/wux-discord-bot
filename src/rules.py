from __future__ import annotations

"""Sistema de regras próprio do DDR.

- 4 atributos: forca, agilidade, mente, presenca (-1 a +3, soma máxima 5)
- Teste: d20 + atributo vs CD (fácil 10, médio 14, difícil 18)
- 20 natural = crítico, 1 natural = desastre
- HP = 10 + 2 × Força
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


def validate_attributes(forca: int, agilidade: int, mente: int, presenca: int) -> str | None:
    """Retorna mensagem de erro, ou None se a distribuição é válida."""
    values = {"Força": forca, "Agilidade": agilidade, "Mente": mente, "Presença": presenca}
    for label, v in values.items():
        if not (ATTR_MIN <= v <= ATTR_MAX):
            return f"{label} deve estar entre {ATTR_MIN} e {ATTR_MAX} (recebi {v})."
    total = sum(values.values())
    if total > ATTR_SUM_MAX:
        return f"A soma dos atributos deve ser no máximo {ATTR_SUM_MAX} (a sua deu {total})."
    return None


def max_hp(forca: int) -> int:
    return 10 + 2 * forca


RULES_SUMMARY = (
    "Sistema: d20 + atributo vs CD (fácil 10, médio 14, difícil 18). "
    "Atributos: Força, Agilidade, Mente, Presença (-1 a +3). "
    "20 natural = sucesso crítico, 1 natural = desastre. HP = 10 + 2×Força."
)
