"""
Checagens de permissão reutilizadas pelos comandos de música e pelo painel web.

Filosofia (igual Hydra/outros bots de música populares):
- Qualquer pessoa em um canal de voz pode usar comandos "simples" (tocar, fila, pausar).
- Ações "fortes" (forçar skip, parar, limpar fila, mover) exigem:
    * ter o cargo de DJ configurado no servidor (utils/config_store), OU
    * ter permissão de Gerenciar Canais/Servidor, OU
    * ser o único humano no canal de voz.
  Caso contrário, a ação passa a exigir votação (ver services/player.py).
"""

from __future__ import annotations

import discord

from utils.config_store import config_store


def eh_dj_ou_staff(membro: discord.Member) -> bool:
    if membro.guild_permissions.manage_guild or membro.guild_permissions.manage_channels:
        return True
    cfg = config_store.get(membro.guild.id)
    dj_role_id = cfg.get("dj_role_id")
    if dj_role_id and any(r.id == dj_role_id for r in membro.roles):
        return True
    return False


def humanos_no_canal(canal: discord.VoiceChannel | discord.StageChannel) -> list[discord.Member]:
    return [m for m in canal.members if not m.bot]


def pode_agir_sem_votacao(membro: discord.Member, canal_voz: discord.VoiceChannel | None) -> bool:
    """Retorna True se o membro pode executar uma ação forte sem precisar de votação."""
    if eh_dj_ou_staff(membro):
        return True
    if canal_voz and len(humanos_no_canal(canal_voz)) <= 1:
        return True
    return False


def canal_permitido(guild_id: int, canal_id: int) -> bool:
    """Verifica se comandos de música podem ser usados no canal informado."""
    cfg = config_store.get(guild_id)
    restrito = cfg.get("canal_musica_id")
    return restrito is None or int(restrito) == int(canal_id)
