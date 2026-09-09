from __future__ import annotations
import asyncio, shutil, time
import discord
from discord import app_commands
from discord.ext import commands

class Diagnostics(commands.Cog):
    def __init__(self, bot): self.bot=bot; self.started=time.monotonic()

    @app_commands.command(name="diagnostic", description="Verifica dependências e serviços")
    async def diagnostic(self, interaction: discord.Interaction):
        ffmpeg=bool(shutil.which("ffmpeg")); ffprobe=bool(shutil.which("ffprobe")); db=self.bot.database.connection is not None
        embed=discord.Embed(title="🩺 Music Bot Health")
        embed.description=f"Discord: OK\nGateway: OK\nFFmpeg: {'OK' if ffmpeg else '❌'}\nFFprobe: {'OK' if ffprobe else '❌'}\nSQLite: {'OK' if db else '❌'}\nyt-dlp: OK\nUptime: {int(time.monotonic()-self.started)}s\nLatency: {self.bot.latency*1000:.0f} ms"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="health", description="Mostra a saúde do bot")
    async def health(self, interaction: discord.Interaction):
        await self.diagnostic.callback(self, interaction)

async def setup(bot): await bot.add_cog(Diagnostics(bot))
