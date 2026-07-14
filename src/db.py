from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Optional

from . import config
from .rules import level_from_xp, max_hp, max_mp

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    guild_id INTEGER PRIMARY KEY,
    mesa_channel_id INTEGER NOT NULL,
    fichas_channel_id INTEGER NOT NULL,
    regras_channel_id INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    scene TEXT NOT NULL DEFAULT '',
    last_narrated_id INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    race TEXT NOT NULL DEFAULT 'humano',
    klass TEXT NOT NULL DEFAULT 'guerreiro',
    forca INTEGER NOT NULL,
    agilidade INTEGER NOT NULL,
    mente INTEGER NOT NULL,
    presenca INTEGER NOT NULL,
    hp INTEGER NOT NULL,
    hp_max INTEGER NOT NULL,
    mp INTEGER NOT NULL DEFAULT 0,
    mp_max INTEGER NOT NULL DEFAULT 0,
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    inventory TEXT NOT NULL DEFAULT '[]',
    conditions TEXT NOT NULL DEFAULT '[]',
    sheet_message_id INTEGER,
    alive INTEGER NOT NULL DEFAULT 1,
    UNIQUE (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# Colunas adicionadas depois da v1 — migradas em bancos antigos
MIGRATIONS = {
    "campaigns": {
        "regras_channel_id": "INTEGER NOT NULL DEFAULT 0",
        "last_narrated_id": "INTEGER NOT NULL DEFAULT 0",
    },
    "characters": {
        "race": "TEXT NOT NULL DEFAULT 'humano'",
        "klass": "TEXT NOT NULL DEFAULT 'guerreiro'",
        "mp": "INTEGER NOT NULL DEFAULT 0",
        "mp_max": "INTEGER NOT NULL DEFAULT 0",
        "xp": "INTEGER NOT NULL DEFAULT 0",
        "level": "INTEGER NOT NULL DEFAULT 1",
    },
}


class Database:
    """Fonte única da verdade do estado do jogo."""

    def __init__(self, path: str = config.DB_PATH) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        for table, columns in MIGRATIONS.items():
            existing = {r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})")}
            for column, ddl in columns.items():
                if column not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        self.conn.commit()

    # --- campanha ---

    def setup_campaign(self, guild_id: int, mesa_id: int, fichas_id: int, regras_id: int = 0) -> None:
        self.conn.execute(
            "INSERT INTO campaigns (guild_id, mesa_channel_id, fichas_channel_id, regras_channel_id) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET mesa_channel_id=?, fichas_channel_id=?, regras_channel_id=?",
            (guild_id, mesa_id, fichas_id, regras_id, mesa_id, fichas_id, regras_id),
        )
        self.conn.commit()

    def get_campaign(self, guild_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM campaigns WHERE guild_id=?", (guild_id,)
        ).fetchone()

    def set_summary(self, guild_id: int, summary: str) -> None:
        self.conn.execute("UPDATE campaigns SET summary=? WHERE guild_id=?", (summary, guild_id))
        self.conn.commit()

    def set_scene(self, guild_id: int, scene: str) -> None:
        self.conn.execute("UPDATE campaigns SET scene=? WHERE guild_id=?", (scene, guild_id))
        self.conn.commit()

    def set_last_narrated(self, guild_id: int, message_id: int) -> None:
        self.conn.execute(
            "UPDATE campaigns SET last_narrated_id=? WHERE guild_id=?", (message_id, guild_id)
        )
        self.conn.commit()

    # --- personagens ---

    def create_character(
        self, guild_id: int, user_id: int, name: str, race: str, klass: str,
        forca: int, agilidade: int, mente: int, presenca: int,
        hp_max: int, mp_max: int,
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO characters "
            "(guild_id, user_id, name, race, klass, forca, agilidade, mente, presenca, "
            " hp, hp_max, mp, mp_max) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (guild_id, user_id, name, race, klass, forca, agilidade, mente, presenca,
             hp_max, hp_max, mp_max, mp_max),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_character(self, guild_id: int, user_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM characters WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        ).fetchone()

    def get_characters(self, guild_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM characters WHERE guild_id=? AND alive=1", (guild_id,)
        ).fetchall()

    def delete_character(self, guild_id: int, user_id: int) -> None:
        self.conn.execute(
            "DELETE FROM characters WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        )
        self.conn.commit()

    def set_sheet_message(self, char_id: int, message_id: int) -> None:
        self.conn.execute(
            "UPDATE characters SET sheet_message_id=? WHERE id=?", (message_id, char_id)
        )
        self.conn.commit()

    def grant_xp(self, char_id: int, amount: int) -> tuple[int, int]:
        """Soma XP e sobe de nível se preciso. Retorna (nível_antes, nível_depois)."""
        row = self.conn.execute("SELECT * FROM characters WHERE id=?", (char_id,)).fetchone()
        if row is None:
            return (1, 1)
        before = row["level"]
        xp = max(0, row["xp"] + amount)
        after = level_from_xp(xp)

        hp_max = max_hp(row["forca"], row["race"], row["klass"], after)
        mp_max = max_mp(row["mente"], row["race"], row["klass"], after)
        # Subir de nível cura a diferença (o ganho vem "cheio")
        hp = min(hp_max, row["hp"] + max(0, hp_max - row["hp_max"]))
        mp = min(mp_max, row["mp"] + max(0, mp_max - row["mp_max"]))

        self.conn.execute(
            "UPDATE characters SET xp=?, level=?, hp=?, hp_max=?, mp=?, mp_max=? WHERE id=?",
            (xp, after, hp, hp_max, mp, mp_max, char_id),
        )
        self.conn.commit()
        return (before, after)

    def apply_delta(self, char_id: int, delta: dict[str, Any]) -> None:
        """Aplica um delta validado do Escriba. Só campos permitidos, com clamps."""
        row = self.conn.execute("SELECT * FROM characters WHERE id=?", (char_id,)).fetchone()
        if row is None:
            return

        hp = row["hp"]
        hp_change = delta.get("hp_change", 0)
        if isinstance(hp_change, int):
            hp = max(0, min(row["hp_max"], hp + hp_change))

        mp = row["mp"]
        mp_change = delta.get("mp_change", 0)
        if isinstance(mp_change, int):
            mp = max(0, min(row["mp_max"], mp + mp_change))

        inventory = json.loads(row["inventory"])
        for item in delta.get("items_added", []) or []:
            if isinstance(item, str) and item.strip():
                inventory.append(item.strip())
        for item in delta.get("items_removed", []) or []:
            if item in inventory:
                inventory.remove(item)

        conditions = json.loads(row["conditions"])
        for cond in delta.get("conditions_added", []) or []:
            if isinstance(cond, str) and cond.strip() and cond not in conditions:
                conditions.append(cond.strip())
        for cond in delta.get("conditions_removed", []) or []:
            if cond in conditions:
                conditions.remove(cond)

        alive = 0 if hp <= 0 else row["alive"]
        self.conn.execute(
            "UPDATE characters SET hp=?, mp=?, inventory=?, conditions=?, alive=? WHERE id=?",
            (hp, mp, json.dumps(inventory, ensure_ascii=False),
             json.dumps(conditions, ensure_ascii=False), alive, char_id),
        )
        self.conn.commit()

    # --- eventos / histórico ---

    def add_event(self, guild_id: int, kind: str, content: str) -> None:
        self.conn.execute(
            "INSERT INTO events (guild_id, kind, content) VALUES (?, ?, ?)",
            (guild_id, kind, content),
        )
        self.conn.commit()

    def recent_events(self, guild_id: int, limit: int) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE guild_id=? ORDER BY id DESC LIMIT ?",
            (guild_id, limit),
        ).fetchall()
        return list(reversed(rows))

    def event_count(self, guild_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE guild_id=?", (guild_id,)
        ).fetchone()
        return int(row["n"])

    def pop_oldest_events(self, guild_id: int, keep_recent: int) -> list[sqlite3.Row]:
        """Remove e retorna os eventos antigos, mantendo os `keep_recent` mais novos."""
        rows = self.conn.execute(
            "SELECT * FROM events WHERE guild_id=? ORDER BY id DESC LIMIT -1 OFFSET ?",
            (guild_id, keep_recent),
        ).fetchall()
        if rows:
            ids = [r["id"] for r in rows]
            self.conn.execute(
                f"DELETE FROM events WHERE id IN ({','.join('?' * len(ids))})", ids
            )
            self.conn.commit()
        return list(reversed(rows))
