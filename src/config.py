from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MODEL_NARRATOR = os.getenv("MODEL_NARRATOR", "deepseek/deepseek-chat")
MODEL_UTILITY = os.getenv("MODEL_UTILITY", "qwen/qwen-2.5-72b-instruct")

DB_PATH = os.getenv("DB_PATH", "./data/ddr.db")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Quantos eventos acumulam antes de o Cronista compactar o histórico
CHRONICLE_THRESHOLD = 12
# Quantos eventos recentes entram no contexto do Narrador
RECENT_EVENTS = 10
