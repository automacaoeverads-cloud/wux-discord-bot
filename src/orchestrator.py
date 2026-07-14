from __future__ import annotations

"""Orquestrador determinístico: código coordena os agentes, nunca o contrário.

Pipeline de uma ação:
  1. Árbitro decide se há rolagem (JSON validado)
  2. CÓDIGO rola o d20 e fixa o resultado
  3. Narrador escreve a prosa a partir do fato
  4. Escriba extrai deltas → código valida e aplica no SQLite
  5. Cronista compacta o histórico quando ele cresce demais
"""

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from typing import Optional

from . import config, dice
from .agents import arbiter, chronicler, narrator, scribe
from .db import Database
from .rules import ATTR_LABELS, DIFFICULTIES


@dataclass
class ActionOutcome:
    narration: str
    roll_text: Optional[str]      # linha da rolagem, ou None se não houve
    delta_text: Optional[str]     # resumo das mudanças de ficha, ou None
    character_updated: Optional[sqlite3.Row]


def character_brief(row: sqlite3.Row) -> str:
    inv = ", ".join(json.loads(row["inventory"])) or "nada"
    conds = ", ".join(json.loads(row["conditions"])) or "nenhuma"
    return (
        f"{row['name']} (HP {row['hp']}/{row['hp_max']}, "
        f"For {row['forca']:+d}, Agi {row['agilidade']:+d}, "
        f"Men {row['mente']:+d}, Pre {row['presenca']:+d}; "
        f"itens: {inv}; condições: {conds})"
    )


def party_brief(rows: list[sqlite3.Row]) -> str:
    return "; ".join(character_brief(r) for r in rows) or "(sem personagens)"


def describe_delta(delta: dict) -> Optional[str]:
    parts: list[str] = []
    hp = delta.get("hp_change", 0)
    if hp:
        parts.append(f"HP {hp:+d}")
    if delta.get("items_added"):
        parts.append("ganhou: " + ", ".join(delta["items_added"]))
    if delta.get("items_removed"):
        parts.append("perdeu: " + ", ".join(delta["items_removed"]))
    if delta.get("conditions_added"):
        parts.append("condições: +" + ", +".join(delta["conditions_added"]))
    if delta.get("conditions_removed"):
        parts.append("condições: -" + ", -".join(delta["conditions_removed"]))
    return "; ".join(parts) if parts else None


class Orchestrator:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    async def handle_action(self, guild_id: int, user_id: int, action: str) -> ActionOutcome:
        async with self._lock(guild_id):
            campaign = self.db.get_campaign(guild_id)
            char = self.db.get_character(guild_id, user_id)
            if campaign is None or char is None:
                raise ValueError("Campanha ou personagem não encontrados.")

            brief = character_brief(char)
            scene = campaign["scene"]

            # 1. Árbitro (IA decide SE rola, código valida)
            verdict = await arbiter.judge(action, brief, scene)

            # 2. Código rola o dado — resultado vira fato imutável
            roll_text: Optional[str] = None
            if verdict["needs_roll"]:
                attr = verdict["attribute"]
                dc = DIFFICULTIES[verdict["difficulty"]]
                result = dice.roll_check(char[attr], dc)
                roll_text = result.describe(ATTR_LABELS[attr])
                mechanical = (
                    f"Teste de {ATTR_LABELS[attr]} (CD {dc}): "
                    f"{'SUCESSO CRÍTICO' if result.critical else 'DESASTRE' if result.fumble else 'SUCESSO' if result.success else 'FALHA'}"
                    f" (motivo do teste: {verdict['reason']})"
                )
            else:
                mechanical = "Nenhum teste necessário — a ação simplesmente acontece."

            # 3. Narrador escreve a prosa a partir do fato
            recent = "\n".join(
                f"- [{e['kind']}] {e['content']}"
                for e in self.db.recent_events(guild_id, config.RECENT_EVENTS)
            )
            party = party_brief(self.db.get_characters(guild_id))
            narration = await narrator.narrate(
                action, char["name"], mechanical, scene,
                campaign["summary"], recent, party,
            )

            # 4. Escriba extrai deltas → código aplica com validação
            delta = await scribe.extract_delta(narration, char["name"], brief)
            delta_text = describe_delta(delta)
            if delta_text:
                self.db.apply_delta(char["id"], delta)

            # Registra o evento no histórico
            self.db.add_event(
                guild_id, "acao",
                f"{char['name']}: {action} → {mechanical}. {narration[:300]}",
            )

            # 5. Cronista compacta se o histórico cresceu
            await self._maybe_chronicle(guild_id)

            updated = self.db.get_character(guild_id, user_id)
            return ActionOutcome(narration, roll_text, delta_text, updated)

    async def open_scene(self, guild_id: int, description: str) -> str:
        async with self._lock(guild_id):
            campaign = self.db.get_campaign(guild_id)
            if campaign is None:
                raise ValueError("Campanha não configurada.")
            party = party_brief(self.db.get_characters(guild_id))
            narration = await narrator.open_scene(description, campaign["summary"], party)
            self.db.set_scene(guild_id, description)
            self.db.add_event(guild_id, "cena", f"Nova cena: {description}")
            return narration

    async def _maybe_chronicle(self, guild_id: int) -> None:
        if self.db.event_count(guild_id) < config.CHRONICLE_THRESHOLD:
            return
        old = self.db.pop_oldest_events(guild_id, keep_recent=config.RECENT_EVENTS // 2)
        if not old:
            return
        campaign = self.db.get_campaign(guild_id)
        old_text = "\n".join(f"- {e['content']}" for e in old)
        try:
            new_summary = await chronicler.update_summary(campaign["summary"], old_text)
            self.db.set_summary(guild_id, new_summary)
        except Exception:  # noqa: BLE001
            # Se o Cronista falhar, devolve os eventos ao histórico bruto
            for e in old:
                self.db.add_event(guild_id, e["kind"], e["content"])
