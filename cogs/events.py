"""
Eventos globais do bot: on_ready, tratamento de erros (slash commands e
comandos de texto legados), auto-desconexão de canal vazio e reconexão
automática de voz.
"""

from __future__ import annotations

import asyncio

import discord
from discord.ext import commands, tasks

from services.player import player_manager
from utils.errors import tratar_erro_app_command
from utils.logger import get_logger

log = get_logger(__name__)


class Eventos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.tree.on_error = tratar_erro_app_command
        self.watchdog_reconexao.start()

    def cog_unload(self):
        self.watchdog_reconexao.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Conectado como %s (ID: %s)", self.bot.user, self.bot.user.id)
        try:
            sincronizados = await self.bot.tree.sync()
            log.info("%d comando(s) slash sincronizado(s).", len(sincronizados))
        except discord.HTTPException as e:
            log.error("Erro ao sincronizar comandos slash: %s", e)

        await self.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name="/tocar")
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild

        # O próprio bot foi desconectado/movido inesperadamente (queda de conexão, kick, etc.)
        if member.id == self.bot.user.id and before.channel and not after.channel:
            player = player_manager.get(guild.id)
            if not player.parado_manualmente and (player.atual or player.queue):
                log.warning("Bot caiu do canal de voz em '%s'. Tentando reconectar em 5s...", guild.name)
                await asyncio.sleep(5)
                await player_manager.tentar_reconectar(guild)
            return

        # Alguém saiu/entrou de um canal onde o bot está — verifica se ficou vazio
        player = player_manager.get(guild.id)
        if player.voice_client and player.voice_client.channel and before.channel == player.voice_client.channel:
            await player_manager.verificar_canal_vazio(guild)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # Mantido apenas por compatibilidade com eventuais comandos de prefixo legados.
        if isinstance(error, commands.CommandNotFound):
            return
        log.error("Erro em comando de texto '%s': %s", ctx.command, error, exc_info=error)
        try:
            await ctx.send(f"⚠️ Ocorreu um erro: {error}")
        except discord.HTTPException:
            pass

    @tasks.loop(seconds=45)
    async def watchdog_reconexao(self):
        """Verifica periodicamente players que deveriam estar conectados mas não estão."""
        for guild_id in player_manager.guild_ids_ativos():
            player = player_manager.get(guild_id)
            if player.parado_manualmente:
                continue
            if not (player.atual or player.queue):
                continue
            if player.voice_client and player.voice_client.is_connected():
                continue
            guild = self.bot.get_guild(guild_id)
            if guild:
                await player_manager.tentar_reconectar(guild)

    @watchdog_reconexao.before_loop
    async def antes_watchdog(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Eventos(bot))
