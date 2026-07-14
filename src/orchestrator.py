from __future__ import annotations

"""Orquestrador determinístico: código coordena os agentes, nunca o contrário.

Pipeline de um beat (/narrar):
  1. Código coleta as mensagens da mesa desde a última narração (feito no bot)
  2. Árbitro decide quais personagens precisam rolar (JSON validado)
  3. CÓDIGO rola os d20 e fixa os resultados
  4. Narrador escreve a prosa a partir dos fatos
  5. Escriba extrai deltas por personagem → código valida e aplica no SQLite
  6. Cronista compacta o histórico quando ele cresce demais
"""

import asyncio
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from . import config, dice
from .agents import arbiter, chronicler, narrator, scribe
from .db import Database
from .rules import ATTR_LABELS, DIFFICULTIES


@dataclass
class BeatOutcome:
    narration: str
    roll_lines: list[str] = field(default_factory=list)   # uma linha por rolagem
    delta_lines: list[str] = field(default_factory=list)  # uma linha por ficha alterada
    updated_rows: list[sqlite3.Row] = field(default_factory=list)


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

    async def narrate_beat(self, guild_id: int, actions: list[tuple[str, str]]) -> BeatOutcome:
        """Processa um beat: `actions` = [(nome_do_personagem, texto), ...] na ordem do chat."""
        async with self._lock(guild_id):
            campaign = self.db.get_campaign(guild_id)
            if campaign is None:
                raise ValueError("Campanha não configurada.")
            rows = self.db.get_characters(guild_id)
            by_name = {r["name"].lower(): r for r in rows}
            scene = campaign["scene"]
            party = party_brief(rows)

            script = "\n".join(f"{name}: {text}" for name, text in actions)

            # 1. Árbitro decide quem rola (código valida os nomes)
            verdicts = await arbiter.judge_beat(script, party, scene)

            # 2. Código rola os dados — resultados viram fatos imutáveis
            roll_lines: list[str] = []
            fact_lines: list[str] = []
            for v in verdicts:
                char = by_name.get(v["character"].lower())
                if char is None:
                    continue
                attr, dc = v["attribute"], DIFFICULTIES[v["difficulty"]]
                result = dice.roll_check(char[attr], dc)
                roll_lines.append(f"{char['name']}: {result.describe(ATTR_LABELS[attr])}")
                outcome = (
                    "SUCESSO CRÍTICO" if result.critical else
                    "DESASTRE" if result.fumble else
                    "SUCESSO" if result.success else "FALHA"
                )
                fact_lines.append(
                    f"- {char['name']} — teste de {ATTR_LABELS[attr]} (CD {dc}): {outcome} "
                    f"(motivo: {v['reason']})"
                )
            facts = "\n".join(fact_lines) or "Nenhum teste foi necessário — as ações simplesmente acontecem."

            # 3. Narrador escreve a prosa a partir dos fatos
            recent = "\n".join(
                f"- [{e['kind']}] {e['content']}"
                for e in self.db.recent_events(guild_id, config.RECENT_EVENTS)
            )
            narration = await narrator.narrate_beat(
                script, facts, scene, campaign["summary"], recent, party,
            )

            # 4. Escriba extrai deltas por personagem → código aplica com validação
            delta_lines: list[str] = []
            updated_rows: list[sqlite3.Row] = []
            deltas = await scribe.extract_deltas(narration, party)
            for name, delta in deltas.items():
                char = by_name.get(name.lower())
                if char is None:
                    continue
                text = describe_delta(delta)
                if not text:
                    continue
                self.db.apply_delta(char["id"], delta)
                delta_lines.append(f"{char['name']}: {text}")
                updated_rows.append(
                    self.db.get_character(guild_id, char["user_id"])
                )

            # Registra o beat no histórico
            resumo_facts = "; ".join(fact_lines) or "sem testes"
            self.db.add_event(
                guild_id, "beat",
                f"Ações: {script[:400]} → {resumo_facts[:300]}. Narração: {narration[:300]}",
            )

            # 5. Cronista compacta se o histórico cresceu
            await self._maybe_chronicle(guild_id)

            return BeatOutcome(narration, roll_lines, delta_lines, updated_rows)

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
