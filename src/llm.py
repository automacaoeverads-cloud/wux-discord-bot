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
    """Uma chamada ao OpenRouter, com retry simples."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "DDR RPG Bot",
    }
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            timeout = aiohttp.ClientTimeout(total=90)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(config.OPENROUTER_URL, json=payload, headers=headers) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        raise LLMError(f"OpenRouter {resp.status}: {data}")
                    return data["choices"][0]["message"]["content"].strip()
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
