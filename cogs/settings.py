from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

class Settings(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="music_settings", description="Mostra as configurações de música deste servidor")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def music_settings(self, interaction: discord.Interaction):
        s = await self.bot.database.get_settings(interaction.guild_id)
        await interaction.response.send_message(f"⚙️ Volume: {s['volume']}%\nDJ: {'on' if s['dj_enabled'] else 'off'}\nAutoplay: {'on' if s['autoplay'] else 'off'}\nAuto-disconnect: {s['auto_disconnect_minutes']} min")

async def setup(bot): await bot.add_cog(Settings(bot))
