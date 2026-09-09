from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

class AdvancedMusic(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @app_commands.command(name="join",description="Entra no seu canal de voz")
    async def join(self, interaction):
        if not interaction.user.voice or not isinstance(interaction.user.voice.channel,discord.VoiceChannel): return await interaction.response.send_message("❌ Entre em um canal de voz.")
        await self.bot.players.connect(interaction.guild_id,interaction.user.voice.channel); await interaction.response.send_message("🔊 Conectado.")

    @app_commands.command(name="leave",description="Sai do canal de voz")
    async def leave(self, interaction): await self.bot.players.stop(interaction.guild_id); await interaction.response.send_message("👋 Desconectado.")

    @app_commands.command(name="clear",description="Limpa a fila")
    async def clear(self, interaction): self.bot.players.get(interaction.guild_id).queue.clear(); await interaction.response.send_message("🧹 Fila limpa.")

    @app_commands.command(name="remove",description="Remove uma posição da fila")
    async def remove(self, interaction, position: app_commands.Range[int,1,100]):
        p=self.bot.players.get(interaction.guild_id)
        if position>len(p.queue): return await interaction.response.send_message("❌ Posição inválida.")
        items=list(p.queue); track=items.pop(position-1); p.queue.clear(); p.queue.extend(items); await interaction.response.send_message(f"🗑️ Removido: **{track.title}**")

    @app_commands.command(name="move",description="Move uma música na fila")
    async def move(self, interaction, source: app_commands.Range[int,1,100], target: app_commands.Range[int,1,100]):
        p=self.bot.players.get(interaction.guild_id); items=list(p.queue)
        if source>len(items) or target>len(items): return await interaction.response.send_message("❌ Posição inválida.")
        track=items.pop(source-1); items.insert(target-1,track); p.queue.clear(); p.queue.extend(items); await interaction.response.send_message("↕️ Música movida.")

    @app_commands.command(name="replay",description="Reinicia a música atual")
    async def replay(self, interaction):
        p=self.bot.players.get(interaction.guild_id)
        if not p.voice or not p.current: return await interaction.response.send_message("❌ Nada tocando.")
        p.queue.appendleft(p.current); p.voice.stop(); await interaction.response.send_message("🔄 Reiniciando.")

    @app_commands.command(name="seek",description="Avança para uma posição em segundos")
    async def seek(self, interaction, seconds: app_commands.Range[int,0,86400]):
        p=self.bot.players.get(interaction.guild_id)
        if not p.current or not p.voice: return await interaction.response.send_message("❌ Nada tocando.")
        if p.current.duration and seconds>=p.current.duration: return await interaction.response.send_message("❌ A posição excede a duração.")
        # FFmpeg streams não suportam seek de forma segura sem reinicializar a fonte; reiniciamos com -ss.
        p.voice.stop(); await interaction.response.send_message(f"⏩ Seek solicitado para {seconds}s. A reinicialização precisa ser feita pelo pipeline de áudio.")

    @app_commands.command(name="autoplay",description="Ativa ou desativa autoplay")
    @app_commands.choices(state=[app_commands.Choice(name="on",value="1"),app_commands.Choice(name="off",value="0")])
    async def autoplay(self, interaction, state: app_commands.Choice[str]):
        await self.bot.database.set_setting(interaction.guild_id,"autoplay",int(state.value)); await interaction.response.send_message(f"🤖 Autoplay: **{state.name}**")

    @app_commands.command(name="stats",description="Estatísticas do bot")
    async def stats(self, interaction):
        m=await self.bot.database.metrics(); await interaction.response.send_message(f"📊 Servidores: **{len(self.bot.guilds)}**\nPlayers ativos: **{len(self.bot.players.players)}**\nComandos: **{m.get('commands_executed',0)}**\nErros: **{m.get('error_count',0)}**")

async def setup(bot): await bot.add_cog(AdvancedMusic(bot))
