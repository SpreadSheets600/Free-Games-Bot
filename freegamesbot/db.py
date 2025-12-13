from __future__ import annotations

import os
import asyncio
import aiosqlite
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class GuildSettings:
    guild_id: int
    channel_id: int


class SettingsRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)

        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._create_schema()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _create_schema(self) -> None:
        assert self._conn
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notified_giveaways (
                guild_id INTEGER NOT NULL,
                giveaway_id TEXT NOT NULL,
                PRIMARY KEY (guild_id, giveaway_id),
                FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        await self._conn.commit()

    async def set_guild_channel(self, guild_id: int, channel_id: int) -> None:
        assert self._conn
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO guild_settings (guild_id, channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id
                """,
                (guild_id, channel_id),
            )

            await self._conn.commit()

    async def clear_guild(self, guild_id: int) -> None:
        assert self._conn
        async with self._lock:
            await self._conn.execute(
                "DELETE FROM guild_settings WHERE guild_id=?", (guild_id,)
            )

            await self._conn.commit()

    async def get_guild_channel(self, guild_id: int) -> Optional[int]:
        assert self._conn
        cursor = await self._conn.execute(
            "SELECT channel_id FROM guild_settings WHERE guild_id=?", (guild_id,)
        )

        row = await cursor.fetchone()

        await cursor.close()
        return row[0] if row else None

    async def get_all_guilds(self) -> List[GuildSettings]:
        assert self._conn
        cursor = await self._conn.execute(
            "SELECT guild_id, channel_id FROM guild_settings"
        )
        rows = await cursor.fetchall()

        await cursor.close()
        return [GuildSettings(guild_id=row[0], channel_id=row[1]) for row in rows]

    async def mark_notified(self, guild_id: int, giveaway_id: str) -> None:
        assert self._conn
        async with self._lock:
            await self._conn.execute(
                "INSERT OR IGNORE INTO notified_giveaways (guild_id, giveaway_id) VALUES (?, ?)",
                (guild_id, giveaway_id),
            )

            await self._conn.commit()

    async def already_notified(self, guild_id: int, giveaway_id: str) -> bool:
        assert self._conn
        cursor = await self._conn.execute(
            "SELECT 1 FROM notified_giveaways WHERE guild_id=? AND giveaway_id=?",
            (guild_id, giveaway_id),
        )
        row = await cursor.fetchone()

        await cursor.close()
        return bool(row)

    async def prune_notified(self, guild_id: int, keep_ids: List[str]) -> None:
        assert self._conn

        if not keep_ids:
            return

        placeholders = ",".join("?" for _ in keep_ids)

        async with self._lock:
            await self._conn.execute(
                f"DELETE FROM notified_giveaways WHERE guild_id=? AND giveaway_id NOT IN ({placeholders})",
                (guild_id, *keep_ids),
            )

            await self._conn.commit()

    async def set_bot_state(self, key: str, value: str) -> None:
        assert self._conn
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO bot_state (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )
            await self._conn.commit()

    async def get_bot_state(
        self, key: str, default: Optional[str] = None
    ) -> Optional[str]:
        assert self._conn
        cursor = await self._conn.execute(
            "SELECT value FROM bot_state WHERE key=?", (key,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        return row[0] if row else default

    async def dump_state(self) -> Tuple[int, int]:
        assert self._conn

        cursor = await self._conn.execute("SELECT COUNT(*) FROM guild_settings")
        guilds = (await cursor.fetchone())[0]

        await cursor.close()

        cursor = await self._conn.execute("SELECT COUNT(*) FROM notified_giveaways")
        notified = (await cursor.fetchone())[0]

        await cursor.close()

        return guilds, notified
