"""
Exceções customizadas do FlaviMusic e handler global de erros para slash
commands (registrado em cogs/events.py via bot.tree.on_error).
"""

from __future__ import annotations

import discord
from discord import app_commands

from utils.helpers import embed_erro
from utils.logger import get_logger

log = get_logger(__name__)


class FlaviMusicError(Exception):
    """Erro base do projeto. Mensagens dessas exceções são mostradas ao usuário."""


class NaoConectadoError(FlaviMusicError):
    def __init__(self):
        super().__init__("Você precisa estar em um canal de voz para usar esse comando.")


class NadaTocandoError(FlaviMusicError):
    def __init__(self):
        super().__init__("Não há nenhuma música tocando agora.")


class CanalErradoError(FlaviMusicError):
    def __init__(self, canal_permitido: str):
        super().__init__(f"Use comandos de música apenas em {canal_permitido}.")


class PermissaoNegadaError(FlaviMusicError):
    def __init__(self, motivo: str = "Você não tem permissão para fazer isso."):
        super().__init__(motivo)


class BuscaFalhouError(FlaviMusicError):
    def __init__(self, motivo: str):
        super().__init__(f"Não consegui encontrar/reproduzir isso: {motivo}")


async def tratar_erro_app_command(interaction: discord.Interaction, erro: Exception) -> None:
    """Handler global: bot.tree.on_error = tratar_erro_app_command (ligado em cogs/events.py)."""

    erro_original = getattr(erro, "original", erro)

    if isinstance(erro_original, FlaviMusicError):
        embed = embed_erro("Ops!", str(erro_original))
    elif isinstance(erro, app_commands.CommandOnCooldown):
        embed = embed_erro("Calma aí!", f"Esse comando está em cooldown. Tente novamente em {erro.retry_after:.1f}s.")
    elif isinstance(erro, app_commands.MissingPermissions):
        embed = embed_erro("Permissão insuficiente", "Você não tem permissão para usar esse comando.")
    elif isinstance(erro, app_commands.BotMissingPermissions):
        embed = embed_erro("Faltam permissões", "Eu não tenho as permissões necessárias no servidor para fazer isso.")
    elif isinstance(erro, app_commands.CheckFailure):
        embed = embed_erro("Não permitido", "Você não pode usar esse comando aqui.")
    else:
        log.error("Erro não tratado no comando %s: %r", getattr(interaction.command, "name", "?"), erro_original, exc_info=erro_original)
        embed = embed_erro("Erro interno", "Algo deu errado do meu lado. Isso já foi registrado no log.")

    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.HTTPException:
        log.warning("Não foi possível notificar o usuário sobre o erro (interação expirada).")
