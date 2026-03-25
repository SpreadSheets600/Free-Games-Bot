from __future__ import annotations

import os
import asyncio
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import aiosqlite


@dataclass
class GuildSettings:
    guild_id: int
    channel_id: Optional[int]
    ping_mode: str
    ping_target_id: Optional[int]
    platform_filter: Optional[str]
    type_filter: Optional[str]


@dataclass
class ArchiveEntry:
    giveaway_id: int
    title: str
    worth: str
    platforms: str
    type: str
    published_date: str
    end_date: str
    open_giveaway_url: str
    status: str
    description: str


@dataclass
class PlayedGameEntry:
    guild_id: int
    user_id: int
    game_key: str
    game_title: str
    platform: str
    status: str
    notes: str
    last_played_at: str


class SettingsRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._create_schema()
        await self._migrate_schema()

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
                channel_id INTEGER,
                ping_mode TEXT NOT NULL DEFAULT 'off',
                ping_target_id INTEGER,
                platform_filter TEXT,
                type_filter TEXT
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

            CREATE TABLE IF NOT EXISTS rss_seen_entries (
                entry_key TEXT PRIMARY KEY,
                seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS giveaway_archive (
                giveaway_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                worth TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                instructions TEXT NOT NULL DEFAULT '',
                open_giveaway_url TEXT NOT NULL DEFAULT '',
                image TEXT NOT NULL DEFAULT '',
                thumbnail TEXT NOT NULL DEFAULT '',
                platforms TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL DEFAULT '',
                published_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                users INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT '',
                source_feed TEXT,
                source_url TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS played_games (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                game_key TEXT NOT NULL,
                game_title TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'played',
                notes TEXT NOT NULL DEFAULT '',
                last_played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id, game_key)
            );
            """
        )
        await self._conn.commit()

    async def _migrate_schema(self) -> None:
        assert self._conn
        columns = await self._table_columns("guild_settings")
        migrations = {
            "ping_mode": "ALTER TABLE guild_settings ADD COLUMN ping_mode TEXT NOT NULL DEFAULT 'off'",
            "ping_target_id": "ALTER TABLE guild_settings ADD COLUMN ping_target_id INTEGER",
            "platform_filter": "ALTER TABLE guild_settings ADD COLUMN platform_filter TEXT",
            "type_filter": "ALTER TABLE guild_settings ADD COLUMN type_filter TEXT",
        }

        for column, statement in migrations.items():
            if column not in columns:
                await self._conn.execute(statement)

        await self._conn.commit()

    async def _table_columns(self, table_name: str) -> set[str]:
        assert self._conn
        cursor = await self._conn.execute(f"PRAGMA table_info({table_name})")
        rows = await cursor.fetchall()
        await cursor.close()
        return {str(row["name"]) for row in rows}

    async def upsert_guild(self, guild_id: int) -> None:
        assert self._conn
        async with self._lock:
            await self._conn.execute(
                "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
                (guild_id,),
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

    async def set_ping_settings(
        self, guild_id: int, ping_mode: str, ping_target_id: Optional[int] = None
    ) -> None:
        assert self._conn
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO guild_settings (guild_id, ping_mode, ping_target_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    ping_mode=excluded.ping_mode,
                    ping_target_id=excluded.ping_target_id
                """,
                (guild_id, ping_mode, ping_target_id),
            )
            await self._conn.commit()

    async def set_filters(
        self,
        guild_id: int,
        platform_filter: Optional[str],
        type_filter: Optional[str],
    ) -> None:
        assert self._conn
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO guild_settings (guild_id, platform_filter, type_filter)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    platform_filter=excluded.platform_filter,
                    type_filter=excluded.type_filter
                """,
                (guild_id, platform_filter, type_filter),
            )
            await self._conn.commit()

    async def clear_guild(self, guild_id: int) -> None:
        assert self._conn
        async with self._lock:
            await self._conn.execute(
                "DELETE FROM played_games WHERE guild_id=?",
                (guild_id,),
            )
            await self._conn.execute(
                "DELETE FROM guild_settings WHERE guild_id=?",
                (guild_id,),
            )
            await self._conn.commit()

    async def get_guild_settings(self, guild_id: int) -> Optional[GuildSettings]:
        assert self._conn
        cursor = await self._conn.execute(
            """
            SELECT guild_id, channel_id, ping_mode, ping_target_id, platform_filter, type_filter
            FROM guild_settings
            WHERE guild_id=?
            """,
            (guild_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return self._guild_from_row(row) if row else None

    async def get_guild_channel(self, guild_id: int) -> Optional[int]:
        guild = await self.get_guild_settings(guild_id)
        return guild.channel_id if guild else None

    async def get_all_guilds(self) -> List[GuildSettings]:
        assert self._conn
        cursor = await self._conn.execute(
            """
            SELECT guild_id, channel_id, ping_mode, ping_target_id, platform_filter, type_filter
            FROM guild_settings
            WHERE channel_id IS NOT NULL
            """
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._guild_from_row(row) for row in rows]

    async def mark_notified(self, guild_id: int, giveaway_id: str) -> None:
        assert self._conn
        async with self._lock:
            await self._conn.execute(
                """
                INSERT OR IGNORE INTO notified_giveaways (guild_id, giveaway_id)
                VALUES (?, ?)
                """,
                (guild_id, giveaway_id),
            )
            await self._conn.commit()

    async def already_notified(self, guild_id: int, giveaway_id: str) -> bool:
        assert self._conn
        cursor = await self._conn.execute(
            """
            SELECT 1
            FROM notified_giveaways
            WHERE guild_id=? AND giveaway_id=?
            """,
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
                f"""
                DELETE FROM notified_giveaways
                WHERE guild_id=? AND giveaway_id NOT IN ({placeholders})
                """,
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
            "SELECT value FROM bot_state WHERE key=?",
            (key,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return str(row["value"]) if row else default

    async def remember_rss_entries(self, entry_keys: Sequence[str]) -> List[str]:
        assert self._conn
        if not entry_keys:
            return []

        new_entries: List[str] = []
        async with self._lock:
            for entry_key in entry_keys:
                cursor = await self._conn.execute(
                    "SELECT 1 FROM rss_seen_entries WHERE entry_key=?",
                    (entry_key,),
                )
                exists = await cursor.fetchone()
                await cursor.close()
                if exists:
                    continue

                await self._conn.execute(
                    "INSERT INTO rss_seen_entries (entry_key) VALUES (?)",
                    (entry_key,),
                )
                new_entries.append(entry_key)

            await self._conn.commit()

        return new_entries

    async def archive_giveaways(self, giveaways: Iterable[object], source_feed: str = "") -> None:
        assert self._conn
        async with self._lock:
            for giveaway in giveaways:
                await self._conn.execute(
                    """
                    INSERT INTO giveaway_archive (
                        giveaway_id, title, worth, description, instructions,
                        open_giveaway_url, image, thumbnail, platforms, type,
                        published_date, end_date, users, status, source_feed, source_url,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(giveaway_id) DO UPDATE SET
                        title=excluded.title,
                        worth=excluded.worth,
                        description=excluded.description,
                        instructions=excluded.instructions,
                        open_giveaway_url=excluded.open_giveaway_url,
                        image=excluded.image,
                        thumbnail=excluded.thumbnail,
                        platforms=excluded.platforms,
                        type=excluded.type,
                        published_date=excluded.published_date,
                        end_date=excluded.end_date,
                        users=excluded.users,
                        status=excluded.status,
                        source_feed=excluded.source_feed,
                        source_url=excluded.source_url,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        int(getattr(giveaway, "id")),
                        getattr(giveaway, "title", ""),
                        getattr(giveaway, "worth", ""),
                        getattr(giveaway, "description", ""),
                        getattr(giveaway, "instructions", ""),
                        getattr(giveaway, "open_giveaway_url", ""),
                        getattr(giveaway, "image", ""),
                        getattr(giveaway, "thumbnail", ""),
                        getattr(giveaway, "platforms", ""),
                        getattr(giveaway, "type", ""),
                        getattr(giveaway, "published_date", ""),
                        getattr(giveaway, "end_date", ""),
                        int(getattr(giveaway, "users", 0) or 0),
                        getattr(giveaway, "status", ""),
                        source_feed,
                        getattr(giveaway, "open_giveaway_url", ""),
                    ),
                )
            await self._conn.commit()

    async def search_archive(self, query: str, limit: int = 10) -> List[ArchiveEntry]:
        assert self._conn
        like = f"%{query.strip()}%"
        cursor = await self._conn.execute(
            """
            SELECT giveaway_id, title, worth, platforms, type, published_date, end_date,
                   open_giveaway_url, status, description
            FROM giveaway_archive
            WHERE title LIKE ? OR description LIKE ? OR platforms LIKE ? OR type LIKE ?
            ORDER BY updated_at DESC, published_date DESC
            LIMIT ?
            """,
            (like, like, like, like, limit),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._archive_from_row(row) for row in rows]

    async def recent_archive(
        self,
        limit: int = 10,
        platform: Optional[str] = None,
        type_: Optional[str] = None,
    ) -> List[ArchiveEntry]:
        assert self._conn
        conditions = []
        params: List[object] = []

        if platform:
            conditions.append("LOWER(platforms) LIKE ?")
            params.append(f"%{platform.lower()}%")
        if type_:
            conditions.append("LOWER(type) = ?")
            params.append(type_.lower())

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cursor = await self._conn.execute(
            f"""
            SELECT giveaway_id, title, worth, platforms, type, published_date, end_date,
                   open_giveaway_url, status, description
            FROM giveaway_archive
            {where}
            ORDER BY updated_at DESC, published_date DESC
            LIMIT ?
            """,
            (*params, limit),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._archive_from_row(row) for row in rows]

    async def upsert_played_game(
        self,
        guild_id: int,
        user_id: int,
        game_key: str,
        game_title: str,
        platform: str,
        status: str,
        notes: str,
    ) -> None:
        assert self._conn
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO played_games (
                    guild_id, user_id, game_key, game_title, platform, status, notes, last_played_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id, user_id, game_key) DO UPDATE SET
                    game_title=excluded.game_title,
                    platform=excluded.platform,
                    status=excluded.status,
                    notes=excluded.notes,
                    last_played_at=CURRENT_TIMESTAMP
                """,
                (guild_id, user_id, game_key, game_title, platform, status, notes),
            )
            await self._conn.commit()

    async def remove_played_game(
        self, guild_id: int, user_id: int, game_key: str
    ) -> bool:
        assert self._conn
        async with self._lock:
            cursor = await self._conn.execute(
                """
                DELETE FROM played_games
                WHERE guild_id=? AND user_id=? AND game_key=?
                """,
                (guild_id, user_id, game_key),
            )
            await self._conn.commit()
            return cursor.rowcount > 0

    async def list_played_games(
        self, guild_id: int, user_id: int, limit: int = 25
    ) -> List[PlayedGameEntry]:
        assert self._conn
        cursor = await self._conn.execute(
            """
            SELECT guild_id, user_id, game_key, game_title, platform, status, notes, last_played_at
            FROM played_games
            WHERE guild_id=? AND user_id=?
            ORDER BY last_played_at DESC, game_title ASC
            LIMIT ?
            """,
            (guild_id, user_id, limit),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._played_from_row(row) for row in rows]

    async def dump_state(self) -> Tuple[int, int, int, int]:
        assert self._conn
        guilds = await self._count("guild_settings")
        notified = await self._count("notified_giveaways")
        archived = await self._count("giveaway_archive")
        played = await self._count("played_games")
        return guilds, notified, archived, played

    async def _count(self, table_name: str) -> int:
        assert self._conn
        cursor = await self._conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}")
        row = await cursor.fetchone()
        await cursor.close()
        return int(row["count"])

    def _guild_from_row(self, row: aiosqlite.Row) -> GuildSettings:
        return GuildSettings(
            guild_id=int(row["guild_id"]),
            channel_id=int(row["channel_id"]) if row["channel_id"] is not None else None,
            ping_mode=str(row["ping_mode"] or "off"),
            ping_target_id=int(row["ping_target_id"]) if row["ping_target_id"] is not None else None,
            platform_filter=str(row["platform_filter"]) if row["platform_filter"] else None,
            type_filter=str(row["type_filter"]) if row["type_filter"] else None,
        )

    def _archive_from_row(self, row: aiosqlite.Row) -> ArchiveEntry:
        return ArchiveEntry(
            giveaway_id=int(row["giveaway_id"]),
            title=str(row["title"]),
            worth=str(row["worth"]),
            platforms=str(row["platforms"]),
            type=str(row["type"]),
            published_date=str(row["published_date"]),
            end_date=str(row["end_date"]),
            open_giveaway_url=str(row["open_giveaway_url"]),
            status=str(row["status"]),
            description=str(row["description"]),
        )

    def _played_from_row(self, row: aiosqlite.Row) -> PlayedGameEntry:
        return PlayedGameEntry(
            guild_id=int(row["guild_id"]),
            user_id=int(row["user_id"]),
            game_key=str(row["game_key"]),
            game_title=str(row["game_title"]),
            platform=str(row["platform"]),
            status=str(row["status"]),
            notes=str(row["notes"]),
            last_played_at=str(row["last_played_at"]),
        )
