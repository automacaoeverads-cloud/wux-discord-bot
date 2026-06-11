# -*- coding: utf-8 -*-
"""Testes do motor de dados (sem Discord). Rode: python3 test_dados.py"""
import random

from dados import rolar


def test_contagem_basica():
    # RNG controlado: sequência fixa de faces
    class FakeRNG:
        def __init__(self, faces):
            self.faces = list(faces)
        def randint(self, a, b):
            return self.faces.pop(0)

    # 5 dados: 6→(explode)2, 5, 1, 3, 6→(explode)6→(explode)1
    rng = FakeRNG([6, 2,  5,  1,  3,  6, 6, 1])
    res = rolar(5, rng=rng)
    assert res.pool == 5
    assert res.cadeias == [[6, 2], [5], [1], [3], [6, 6, 1]]
    # êxitos: 6,5,6,6 = 4
    assert res.exitos == 4, res.exitos
    # dissonâncias: dois 1 = 2
    assert res.dissonancias == 2, res.dissonancias
    # seises (explosões): 6,6,6 = 3
    assert res.seises == 3, res.seises
    print("✓ contagem básica (êxitos, dissonâncias, explosões em cadeia)")


def test_dificuldade():
    class FakeRNG:
        def randint(self, a, b):
            return 5  # tudo êxito, sem explosão
    res = rolar(4, dificuldade=3, rng=FakeRNG())
    assert res.exitos == 4
    assert res.passou is True
    assert res.margem == 1
    res2 = rolar(2, dificuldade=3, rng=FakeRNG())
    assert res2.passou is False
    assert res2.margem == -1
    print("✓ dificuldade / margem / passou-falhou")


def test_estatistico():
    # média de êxitos por dado com explosão deve ficar ~0.4 (2/6 base + explosões)
    random.seed(42)
    total = sum(rolar(1).exitos for _ in range(20000))
    media = total / 20000
    assert 0.35 < media < 0.45, media
    print(f"✓ média de êxitos por dado ≈ {media:.3f} (esperado ~0.40)")


def test_teto_pool():
    res = rolar(999)
    assert res.pool == 100  # MAX_DADOS
    print("✓ teto de pool respeitado (100)")


if __name__ == "__main__":
    test_contagem_basica()
    test_dificuldade()
    test_estatistico()
    test_teto_pool()
    print("\nTodos os testes passaram. ✦")
