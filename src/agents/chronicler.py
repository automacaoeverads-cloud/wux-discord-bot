from __future__ import annotations

"""Cronista: compacta eventos antigos no resumo da campanha.

Mantém o contexto do Narrador pequeno e fiel ao que aconteceu.
"""

from .. import config, llm

SYSTEM = """Você é o Cronista de uma mesa de RPG. Atualize o resumo da campanha incorporando os novos eventos.

Regras:
1. Preserve fatos importantes do resumo anterior (nomes, lugares, objetivos, promessas, inimigos).
2. Registre apenas o que está nos eventos — não invente nem especule.
3. Máximo de 250 palavras, em português, terceira pessoa, tom neutro de crônica."""


async def update_summary(current_summary: str, old_events: str) -> str:
    user = (
        f"RESUMO ATUAL:\n{current_summary or '(vazio — campanha nova)'}\n\n"
        f"NOVOS EVENTOS A INCORPORAR:\n{old_events}\n\n"
        f"Escreva o resumo atualizado."
    )
    return await llm.chat(config.MODEL_UTILITY, SYSTEM, user, temperature=0.3, max_tokens=500)
