"""
API REST para controlar a música pelo painel web: tocar, pausar, pular,
parar, loop, shuffle, volume e remover da fila. Usa exatamente o mesmo
PlayerManager que os comandos slash e os botões do Discord usam.
"""

from __future__ import annotations

import discord
from fastapi import APIRouter, Body, Request

from services.player import player_manager
from utils.errors import FlaviMusicError
from utils.logger import get_logger
from web.deps import exigir_acesso_guild, exigir_usuario

log = get_logger(__name__)

router = APIRouter(prefix="/api/player", tags=["player"])


def _membro_solicitante(guild: discord.Guild, usuario: dict) -> discord.Member | None:
    try:
        return guild.get_member(int(usuario["id"]))
    except (KeyError, ValueError, TypeError):
        return None


@router.get("/{guild_id}/status")
async def status(request: Request, guild_id: int):
    guild = exigir_acesso_guild(request, guild_id)
    return player_manager.status(guild)


@router.post("/{guild_id}/tocar")
async def tocar(request: Request, guild_id: int, payload: dict = Body(...)):
    guild = exigir_acesso_guild(request, guild_id)
    usuario = exigir_usuario(request)
    membro = _membro_solicitante(guild, usuario)

    if not membro or not membro.voice or not membro.voice.channel:
        return {"ok": False, "mensagem": "Você precisa estar em um canal de voz no servidor para tocar algo pelo painel."}

    busca = (payload.get("busca") or "").strip()
    if not busca:
        return {"ok": False, "mensagem": "Informe uma música, link do YouTube ou link do Spotify."}

    try:
        resultado = await player_manager.adicionar_e_tocar(
            guild, membro.voice.channel, membro.voice.channel, busca, membro
        )
    except FlaviMusicError as e:
        return {"ok": False, "mensagem": str(e)}

    return {"ok": True, "mensagem": f"Adicionado: {resultado['faixa']['title']}"}


@router.post("/{guild_id}/pausar_continuar")
async def pausar_continuar(request: Request, guild_id: int):
    guild = exigir_acesso_guild(request, guild_id)
    try:
        return await player_manager.pausar_continuar(guild)
    except FlaviMusicError as e:
        return {"ok": False, "mensagem": str(e)}


@router.post("/{guild_id}/pular")
async def pular(request: Request, guild_id: int):
    guild = exigir_acesso_guild(request, guild_id)
    try:
        # Ações vindas do painel (que já exige permissão de Gerenciar Servidor) pulam sem votação.
        return await player_manager.pular(guild, forcar=True)
    except FlaviMusicError as e:
        return {"ok": False, "mensagem": str(e)}


@router.post("/{guild_id}/parar")
async def parar(request: Request, guild_id: int):
    guild = exigir_acesso_guild(request, guild_id)
    return await player_manager.parar(guild)


@router.post("/{guild_id}/loop")
async def loop(request: Request, guild_id: int, payload: dict = Body(default={})):
    guild = exigir_acesso_guild(request, guild_id)
    return await player_manager.alternar_loop(guild, modo=payload.get("modo"))


@router.post("/{guild_id}/shuffle")
async def shuffle(request: Request, guild_id: int):
    guild = exigir_acesso_guild(request, guild_id)
    return await player_manager.embaralhar(guild)


@router.post("/{guild_id}/volume")
async def volume(request: Request, guild_id: int, payload: dict = Body(...)):
    guild = exigir_acesso_guild(request, guild_id)
    return await player_manager.definir_volume(guild, int(payload.get("percentual", 50)))


@router.post("/{guild_id}/remover")
async def remover(request: Request, guild_id: int, payload: dict = Body(...)):
    guild = exigir_acesso_guild(request, guild_id)
    return await player_manager.remover_da_fila(guild, int(payload.get("posicao", 0)))
