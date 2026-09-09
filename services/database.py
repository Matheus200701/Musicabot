from __future__ import annotations

from pathlib import Path
import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row

    async def migrate(self) -> None:
        assert self.connection is not None
        await self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            volume INTEGER NOT NULL DEFAULT 50,
            loop_mode TEXT NOT NULL DEFAULT 'off',
            dj_role_id INTEGER,
            dj_enabled INTEGER NOT NULL DEFAULT 0,
            music_channel_id INTEGER,
            autoplay INTEGER NOT NULL DEFAULT 0,
            announce INTEGER NOT NULL DEFAULT 1,
            auto_disconnect_minutes INTEGER NOT NULL DEFAULT 5
        );
        CREATE TABLE IF NOT EXISTS metrics (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        );
        """)
        await self.connection.commit()

    async def get_settings(self, guild_id: int) -> dict:
        assert self.connection is not None
        async with self.connection.execute("SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            await self.connection.execute("INSERT INTO guild_settings(guild_id) VALUES (?)", (guild_id,))
            await self.connection.commit()
            return await self.get_settings(guild_id)
        return dict(row)

    async def set_setting(self, guild_id: int, key: str, value: object) -> None:
        allowed = {"volume", "loop_mode", "dj_role_id", "dj_enabled", "music_channel_id", "autoplay", "announce", "auto_disconnect_minutes"}
        if key not in allowed:
            raise ValueError("Configuração inválida")
        assert self.connection is not None
        await self.connection.execute(f"INSERT INTO guild_settings(guild_id,{key}) VALUES (?,?) ON CONFLICT(guild_id) DO UPDATE SET {key}=excluded.{key}", (guild_id, value))
        await self.connection.commit()

    async def increment(self, key: str, amount: int = 1) -> None:
        assert self.connection is not None
        await self.connection.execute("INSERT INTO metrics(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=value+excluded.value", (key, amount))
        await self.connection.commit()

    async def metrics(self) -> dict[str, int]:
        assert self.connection is not None
        async with self.connection.execute("SELECT key,value FROM metrics") as cur:
            return {row[0]: row[1] for row in await cur.fetchall()}

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()
            self.connection = None
