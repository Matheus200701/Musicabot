"""
WebSocket que envia o status do player (faixa atual, fila, progresso) em
tempo real para o painel web, sempre que o PlayerManager notifica uma
mudança de estado (nova música, pause, skip, etc.) — sem precisar de polling.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.player import player_manager
from utils.logger import get_logger
from web.discord_oauth import usuario_pode_gerenciar
from web.server import obter_bot

log = get_logger(__name__)

router = APIRouter(tags=["websocket"])


def _tem_acesso(websocket: WebSocket, guild_id: int) -> bool:
    usuario = websocket.session.get("usuario") if hasattr(websocket, "session") else None
    if not usuario:
        return False
    guilds_usuario = {int(g["id"]): g for g in usuario.get("guilds", [])}
    resumo = guilds_usuario.get(guild_id)
    return bool(resumo and usuario_pode_gerenciar(resumo))


@router.websocket("/ws/{guild_id}")
async def status_ao_vivo(websocket: WebSocket, guild_id: int):
    if not _tem_acesso(websocket, guild_id):
        await websocket.close(code=4401)
        return

    bot = obter_bot()
    guild = bot.get_guild(guild_id) if bot else None
    if not guild:
        await websocket.close(code=4404)
        return

    await websocket.accept()

    async def enviar_status(_guild_id: int) -> None:
        try:
            await websocket.send_json(player_manager.status(guild))
        except Exception:  # noqa: BLE001 - conexão pode já ter caído
            pass

    player_manager.observar(guild_id, enviar_status)
    try:
        await enviar_status(guild_id)  # snapshot inicial
        while True:
            # Mantém a conexão viva; o cliente não precisa enviar nada, mas
            # respondemos a pings/mensagens vazias para detectar desconexão.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        player_manager.parar_de_observar(guild_id, enviar_status)
