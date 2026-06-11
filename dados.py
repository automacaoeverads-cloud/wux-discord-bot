# -*- coding: utf-8 -*-
"""
Motor de dados do WUX — A Senda dos Mil Reinos.

Regras:
  • Pool de d6.
  • 5 ou 6  = Êxito (✦).
  • 6       = explode: rola outro d6, que também pode explodir (em cadeia).
  • 1       = Dissonância (relevante em ações Voláteis).

Este módulo é PURO (sem Discord) — dá pra testar isolado.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

MAX_DADOS = 100      # teto de pool, evita abuso
MAX_EXPLOSOES = 50   # trava de segurança contra cadeia infinita de 6


@dataclass
class Resultado:
    pool: int                     # nº de dados efetivamente rolados
    cadeias: list                 # list[list[int]] — cada dado inicial e suas explosões
    exitos: int                   # total de 5 e 6 (inclui os de explosão)
    dissonancias: int             # total de 1 (inclui os de explosão)
    seises: int                   # total de 6 (quantas explosões dispararam)
    dificuldade: "int | None" = None

    @property
    def faces(self) -> list:
        return [f for cadeia in self.cadeias for f in cadeia]

    @property
    def passou(self):
        if self.dificuldade is None:
            return None
        return self.exitos >= self.dificuldade

    @property
    def margem(self):
        if self.dificuldade is None:
            return None
        return self.exitos - self.dificuldade


def rolar(pool: int, dificuldade=None, explodir: bool = True, rng=random) -> Resultado:
    """Rola `pool` d6 com as regras do WUX e devolve um Resultado."""
    pool = max(0, min(int(pool), MAX_DADOS))
    cadeias = []
    for _ in range(pool):
        cadeia = [rng.randint(1, 6)]
        explosoes = 0
        while explodir and cadeia[-1] == 6 and explosoes < MAX_EXPLOSOES:
            cadeia.append(rng.randint(1, 6))
            explosoes += 1
        cadeias.append(cadeia)

    faces = [f for cadeia in cadeias for f in cadeia]
    exitos = sum(1 for f in faces if f >= 5)
    dissonancias = sum(1 for f in faces if f == 1)
    seises = sum(1 for f in faces if f == 6)

    return Resultado(
        pool=pool,
        cadeias=cadeias,
        exitos=exitos,
        dissonancias=dissonancias,
        seises=seises,
        dificuldade=dificuldade,
    )
