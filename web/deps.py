"""
Dependências do FastAPI: sessão do usuário logado e checagem de acesso a um
servidor específico (o usuário precisa estar logado, o bot precisa estar
naquele servidor, e o usuário precisa ter permissão de Gerenciar Servidor lá).
"""

from __future__ import annotations

from typing import Optional

import discord
from fastapi import HTTPException, Request

from web.discord_oauth import usuario_pode_gerenciar


def usuario_atual(request: Request) -> Optional[dict]:
    return request.session.get("usuario")


def exigir_usuario(request: Request) -> dict:
    usuario = usuario_atual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Não autenticado. Faça login em /login.")
    return usuario


def exigir_acesso_guild(request: Request, guild_id: int) -> discord.Guild:
    """Garante que o usuário logado pode gerenciar esse servidor E que o bot está nele."""
    from web.server import obter_bot  # import tardio evita ciclo

    usuario = exigir_usuario(request)
    guilds_usuario = {int(g["id"]): g for g in usuario.get("guilds", [])}

    guild_resumo = guilds_usuario.get(guild_id)
    if not guild_resumo or not usuario_pode_gerenciar(guild_resumo):
        raise HTTPException(status_code=403, detail="Você não tem permissão para gerenciar esse servidor.")

    bot = obter_bot()
    guild = bot.get_guild(guild_id) if bot else None
    if not guild:
        raise HTTPException(status_code=404, detail="O bot não está nesse servidor (ou ainda está iniciando).")

    return guild
