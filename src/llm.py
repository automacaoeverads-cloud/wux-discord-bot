from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

import aiohttp

from . import config

log = logging.getLogger("ddr.llm")


class LLMError(Exception):
    pass


async def chat(
    model: str,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Uma chamada ao OpenRouter, com retry simples.

    Modelos de raciocínio (ex.: tencent/hy3) gastam tokens "pensando" antes de
    escrever. Alguns ignoram o pedido de desligar o raciocínio — então damos um
    colchão de orçamento (REASONING_HEADROOM) e, se ainda assim o content voltar
    vazio por `length`, dobramos o orçamento e tentamos de novo.
    """
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "DDR RPG Bot",
    }
    budget = max_tokens + config.REASONING_HEADROOM
    disable_reasoning = True
    last_err: Optional[Exception] = None

    for attempt in range(3):
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": budget,
        }
        if disable_reasoning:
            # Pede sem raciocínio; modelos que sempre raciocinam ignoram isso
            # (por isso o colchão acima). `exclude` mantém o content limpo.
            body["reasoning"] = {"enabled": False, "exclude": True}
        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(config.OPENROUTER_URL, json=body, headers=headers) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        # provedor rejeitou o parâmetro reasoning? tira e tenta de novo
                        if resp.status == 400 and disable_reasoning and "reasoning" in str(data).lower():
                            disable_reasoning = False
                            log.warning("Modelo %s rejeitou reasoning=off; repetindo sem o parâmetro.", model)
                            continue
                        raise LLMError(f"OpenRouter {resp.status}: {data}")

                    choice = data["choices"][0]
                    content = (choice["message"].get("content") or "").strip()
                    if content:
                        return content

                    finish = choice.get("finish_reason")
                    if finish == "length":
                        # o raciocínio comeu todo o orçamento — dobra e retenta
                        budget *= 2
                        log.warning(
                            "Modelo %s gastou o orçamento raciocinando; "
                            "aumentando max_tokens para %d.", model, budget,
                        )
                    raise LLMError(f"resposta sem conteúdo (finish_reason={finish})")
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("Tentativa %d falhou (%s): %s", attempt + 1, model, e)
            await asyncio.sleep(2 * (attempt + 1))

    raise LLMError(f"OpenRouter falhou após 3 tentativas: {last_err}")


def extract_json(text: str) -> dict[str, Any]:
    """Extrai o primeiro objeto JSON de uma resposta (tolera ```json ... ```)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"Resposta sem JSON: {text[:200]}")
    return json.loads(text[start : end + 1])


async def chat_json(
    model: str,
    system: str,
    user: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Chamada que exige JSON de volta; re-tenta uma vez se o parse falhar."""
    for attempt in range(2):
        raw = await chat(model, system, user, temperature=temperature)
        try:
            return extract_json(raw)
        except (LLMError, json.JSONDecodeError) as e:
            log.warning("JSON inválido (tentativa %d): %s", attempt + 1, e)
    raise LLMError("O modelo não retornou JSON válido.")
