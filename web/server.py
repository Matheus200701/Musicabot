"""
Painel web do FlaviMusic, em FastAPI.

Roda no MESMO processo e no MESMO event loop asyncio do bot (veja bot.py) —
diferente do webpanel.py original, que usava Flask (síncrono) numa thread
separada com run_coroutine_threadsafe. Rodar tudo no mesmo loop assíncrono é
mais leve (importante pra Termux) e elimina a ponte thread↔loop inteira.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict

import discord
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from utils.logger import get_logger

log = get_logger(__name__)

DIRETORIO_WEB = os.path.dirname(os.path.abspath(__file__))
SESSION_SECRET = os.getenv("WEB_SESSION_SECRET", "")

_bot_ref: discord.Client | None = None


def ligar_bot(bot: discord.Client) -> None:
    global _bot_ref
    _bot_ref = bot


def obter_bot() -> discord.Client | None:
    return _bot_ref


templates = Jinja2Templates(directory=os.path.join(DIRETORIO_WEB, "templates"))


class LimitadorTaxa:
    """Rate limiter simples em memória (por IP), para proteger a API do painel de abuso/spam."""

    def __init__(self, max_requisicoes: int = 60, janela_segundos: int = 60):
        self.max_requisicoes = max_requisicoes
        self.janela_segundos = janela_segundos
        self._acessos: dict[str, list[float]] = defaultdict(list)

    def permitido(self, chave: str) -> bool:
        agora = time.monotonic()
        janela_inicio = agora - self.janela_segundos
        acessos = [t for t in self._acessos[chave] if t > janela_inicio]
        acessos.append(agora)
        self._acessos[chave] = acessos
        return len(acessos) <= self.max_requisicoes


limitador = LimitadorTaxa(max_requisicoes=120, janela_segundos=60)


def criar_app() -> FastAPI:
    # Import tardio: os routers importam `obter_bot`/`templates` deste mesmo módulo,
    # então só podemos importá-los depois que essas definições já existirem acima.
    from web.routers import auth_router, guilds_router, player_router, ws_router

    if not SESSION_SECRET:
        log.warning(
            "WEB_SESSION_SECRET não configurado no .env — usando uma chave temporária "
            "(sessões serão invalidadas a cada restart do bot). Defina essa variável em produção."
        )

    app = FastAPI(title="FlaviMusic Dashboard", docs_url=None, redoc_url=None)

    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET or os.urandom(32).hex(),
        session_cookie="flavimusic_session",
        max_age=60 * 60 * 24 * 7,  # 7 dias
        https_only=os.getenv("WEB_COOKIE_HTTPS_ONLY", "false").lower() == "true",
    )

    @app.middleware("http")
    async def middleware_rate_limit(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "desconhecido"
            if not limitador.permitido(ip):
                return JSONResponse(status_code=429, content={"erro": "Muitas requisições. Aguarde um pouco."})
        return await call_next(request)

    app.mount("/static", StaticFiles(directory=os.path.join(DIRETORIO_WEB, "static")), name="static")

    app.include_router(auth_router.router)
    app.include_router(guilds_router.router)
    app.include_router(player_router.router)
    app.include_router(ws_router.router)

    @app.get("/health")
    async def health():
        bot = obter_bot()
        return {
            "status": "ok",
            "bot_conectado": bool(bot and bot.is_ready()),
            "servidores": len(bot.guilds) if bot and bot.is_ready() else 0,
        }

    return app


app = criar_app()


async def iniciar_servidor_web(bot: discord.Client, host: str, port: int) -> None:
    """Deve ser chamado como uma task asyncio, junto com bot.start(), no mesmo event loop."""
    ligar_bot(bot)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False)
    servidor = uvicorn.Server(config)
    log.info("Painel web disponível em http://%s:%d", host, port)
    await servidor.serve()
