from __future__ import annotations

import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from services.database import Database
from services.player import PlayerManager
from utils.logger import configure_logging, get_logger

load_dotenv()
configure_logging()
log = get_logger(__name__)

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
PREFIX = os.getenv("BOT_PREFIX", "!")

EXTENSIONS = (
    "cogs.music",
    "cogs.settings",
    "cogs.diagnostics",
    "cogs.admin",
)


class MusicBot(commands.Bot):
    """Bot principal. A árvore de comandos é sincronizada uma única vez em setup_hook."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.voice_states = True
        self.database = Database(Path(os.getenv("DATABASE_PATH", "data/bot.db")))
        self.players = PlayerManager(self)
        self._commands_synced = False
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)

    async def setup_hook(self) -> None:
        await self.database.connect()
        await self.database.migrate()
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        if not self._commands_synced:
            await self.tree.sync()
            self._commands_synced = True
            log.info("Slash Commands globais sincronizados uma única vez: %d", len(self.tree.get_commands()))

    async def close(self) -> None:
        await self.players.shutdown()
        await self.database.close()
        await super().close()


bot = MusicBot()


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN não definido no .env")
    await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
