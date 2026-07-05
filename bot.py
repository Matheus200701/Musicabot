"""
Ponto de entrada do FlaviMusic.

Diferente do original (que rodava o painel Flask numa thread separada),
aqui o bot (discord.py) e o painel web (FastAPI/uvicorn) rodam como duas
tasks no MESMO event loop asyncio — mais leve (bom para Termux/VPS pequena)
e sem necessidade de pontes thread↔loop para compartilhar estado do player.

Variáveis de ambiente (ver .env.example):
    DISCORD_TOKEN         - obrigatório
    PREFIX                - prefixo de comandos de texto legados (padrão "!")
    WEB_PANEL_ATIVO        - "true"/"false" (padrão "true")
    WEB_PANEL_HOST         - padrão "0.0.0.0"
    WEB_PANEL_PORT         - padrão 8000
"""

from __future__ import annotations

import asyncio
import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.logger import configurar_logging, get_logger

load_dotenv()

log = get_logger(__name__)

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX", "!")
WEB_PANEL_ATIVO = os.getenv("WEB_PANEL_ATIVO", "true").lower() == "true"
WEB_PANEL_HOST = os.getenv("WEB_PANEL_HOST", "0.0.0.0")
WEB_PANEL_PORT = int(os.getenv("WEB_PANEL_PORT", "8000"))

EXTENSOES = (
    "cogs.music",
    "cogs.events",
    "cogs.leveling",
    "cogs.economy",
    "cogs.help",
)


def _criar_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True  # necessário p/ sistema de XP e comandos de texto legados
    intents.voice_states = True     # necessário p/ player de música e checagem de canal vazio
    intents.members = True          # necessário p/ contar humanos no canal de voz (vote-skip)
    return intents


bot = commands.Bot(command_prefix=PREFIX, intents=_criar_intents(), help_command=None)


async def _carregar_extensoes() -> None:
    for extensao in EXTENSOES:
        try:
            await bot.load_extension(extensao)
            log.info("Extensão carregada: %s", extensao)
        except Exception:
            log.exception("Falha ao carregar a extensão '%s'", extensao)


async def main() -> None:
    configurar_logging()

    if not TOKEN:
        log.error(
            "DISCORD_TOKEN não encontrado. Copie .env.example para .env e configure seu token "
            "(https://discord.com/developers/applications)."
        )
        sys.exit(1)

    async with bot:
        await _carregar_extensoes()

        tarefas = [bot.start(TOKEN)]

        if WEB_PANEL_ATIVO:
            from web.server import iniciar_servidor_web

            tarefas.append(iniciar_servidor_web(bot, WEB_PANEL_HOST, WEB_PANEL_PORT))
        else:
            log.info("Painel web desativado (WEB_PANEL_ATIVO=false).")

        await asyncio.gather(*tarefas)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Encerrado pelo usuário.")
