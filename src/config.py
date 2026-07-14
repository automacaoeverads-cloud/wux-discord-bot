from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MODEL_NARRATOR = os.getenv("MODEL_NARRATOR", "tencent/hy3:free")
MODEL_UTILITY = os.getenv("MODEL_UTILITY", "tencent/hy3:free")

DB_PATH = os.getenv("DB_PATH", "./data/ddr.db")

# Modelos de raciocínio (ex.: tencent/hy3) gastam tokens "pensando" ANTES de
# escrever a resposta. Esse colchão é somado ao max_tokens pedido, senão o
# orçamento acaba no raciocínio e o content volta vazio (finish_reason=length).
REASONING_HEADROOM = int(os.getenv("REASONING_HEADROOM", "3000"))

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Quantos eventos acumulam antes de o Cronista compactar o histórico
CHRONICLE_THRESHOLD = 12
# Quantos eventos recentes entram no contexto do Narrador
RECENT_EVENTS = 10
