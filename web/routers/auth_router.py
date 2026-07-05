"""
Rotas de autenticação: /login (redireciona pro Discord), /auth/callback
(recebe o code, troca por token, guarda usuário na sessão) e /logout.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from utils.logger import get_logger
from web import discord_oauth

log = get_logger(__name__)

router = APIRouter(tags=["auth"])


@router.get("/login")
async def login(request: Request):
    if not discord_oauth.CLIENT_ID or not discord_oauth.CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="OAuth2 do Discord não configurado (defina DISCORD_CLIENT_ID/DISCORD_CLIENT_SECRET no .env).",
        )
    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    return RedirectResponse(discord_oauth.url_autorizacao(state))


@router.get("/auth/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(f"/login-erro?motivo={error}")

    state_esperado = request.session.pop("oauth_state", None)
    if not code or not state or state != state_esperado:
        raise HTTPException(status_code=400, detail="Falha na validação do login (state inválido ou expirado).")

    try:
        token_info = await discord_oauth.trocar_code_por_token(code)
        access_token = token_info["access_token"]
        usuario = await discord_oauth.obter_usuario(access_token)
        guilds = await discord_oauth.obter_guilds_usuario(access_token)
    except Exception:
        log.exception("Erro no fluxo OAuth2 do Discord")
        raise HTTPException(status_code=502, detail="Não foi possível concluir o login com o Discord.")

    request.session["usuario"] = {
        "id": usuario["id"],
        "username": usuario.get("username"),
        "avatar": usuario.get("avatar"),
        "guilds": guilds,
    }
    return RedirectResponse("/servidores")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
