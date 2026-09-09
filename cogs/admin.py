from __future__ import annotations
import os
import discord
from discord import app_commands
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot): self.bot=bot
    def owner(self, interaction): return interaction.user.id == int(os.getenv('OWNER_ID','0') or 0)

    @app_commands.command(name="sync", description="Sincroniza comandos globais (proprietário)")
    async def sync(self, interaction):
        if not self.owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        cmds=await self.bot.tree.sync(); await interaction.response.send_message(f"✅ {len(cmds)} comandos sincronizados.", ephemeral=True)

    @app_commands.command(name="clear_commands", description="Remove comandos globais (proprietário)")
    async def clear_commands(self, interaction):
        if not self.owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        self.bot.tree.clear_commands(guild=None); await self.bot.tree.sync(); await interaction.response.send_message("🧹 Comandos globais removidos.", ephemeral=True)

async def setup(bot): await bot.add_cog(Admin(bot))
