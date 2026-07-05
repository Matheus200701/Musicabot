"""
Sistema central de logs do FlaviMusic.

Cria um logger único ("FlaviMusic") usado em todo o projeto (bot, services,
cogs e painel web), com saída simultânea para:
- console (colorido, nível INFO por padrão)
- arquivo rotativo em logs/flavimusic.log (nível DEBUG, guarda histórico)

Uso em qualquer módulo:
    from utils.logger import get_logger
    log = get_logger(__name__)
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "flavimusic.log")

_CORES = {
    "DEBUG": "\033[36m",     # ciano
    "INFO": "\033[32m",      # verde
    "WARNING": "\033[33m",   # amarelo
    "ERROR": "\033[31m",     # vermelho
    "CRITICAL": "\033[41m",  # fundo vermelho
}
_RESET = "\033[0m"


class _FormatterColorido(logging.Formatter):
    """Formatter que colore o nível do log apenas no console (não no arquivo)."""

    def format(self, record: logging.LogRecord) -> str:
        cor = _CORES.get(record.levelname, "")
        original = record.levelname
        record.levelname = f"{cor}{record.levelname:<8}{_RESET}" if cor else record.levelname
        texto = super().format(record)
        record.levelname = original
        return texto


_configurado = False


def configurar_logging(nivel_console: int = logging.INFO, nivel_arquivo: int = logging.DEBUG) -> logging.Logger:
    """Configura o logger raiz do projeto. Deve ser chamado uma única vez, no bot.py."""
    global _configurado

    root = logging.getLogger("FlaviMusic")
    if _configurado:
        return root

    root.setLevel(logging.DEBUG)
    root.propagate = False

    os.makedirs(LOG_DIR, exist_ok=True)

    formato = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    data_formato = "%Y-%m-%d %H:%M:%S"

    console = logging.StreamHandler()
    console.setLevel(nivel_console)
    console.setFormatter(_FormatterColorido(formato, datefmt=data_formato))
    root.addHandler(console)

    arquivo = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    arquivo.setLevel(nivel_arquivo)
    arquivo.setFormatter(logging.Formatter(formato, datefmt=data_formato))
    root.addHandler(arquivo)

    # Silencia bibliotecas muito verbosas, mantendo só avisos/erros delas
    for nome_ruidoso in ("discord", "discord.gateway", "discord.client", "discord.http",
                         "yt_dlp", "uvicorn.access"):
        logging.getLogger(nome_ruidoso).setLevel(logging.WARNING)

    _configurado = True
    root.info("Sistema de logs iniciado (console + arquivo em %s)", LOG_FILE)
    return root


def get_logger(nome: str | None = None) -> logging.Logger:
    """Retorna um logger filho de 'FlaviMusic', ex: get_logger(__name__)."""
    base = logging.getLogger("FlaviMusic")
    if nome:
        return base.getChild(nome.rsplit(".", 1)[-1])
    return base
