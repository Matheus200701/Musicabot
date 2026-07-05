"""
Páginas HTML (login, seleção de servidor, dashboard) e API de configuração
por servidor (canal de música, prefixo, cargo de DJ).
"""

from __future__ import annotations

import discord
from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.config_store import config_store
from web.deps import exigir_acesso_guild, usuario_atual
from web.discord_oauth import usuario_pode_gerenciar
from web.server import obter_bot, templates

router = APIRouter(tags=["guilds"])


@router.get("/", response_class=HTMLResponse)
async def raiz(request: Request):
    if usuario_atual(request):
        return RedirectResponse("/servidores")
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/login-erro", response_class=HTMLResponse)
async def login_erro(request: Request, motivo: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "erro": motivo or "acesso negado"})


@router.get("/servidores", response_class=HTMLResponse)
async def servidores(request: Request):
    usuario = usuario_atual(request)
    if not usuario:
        return RedirectResponse("/")

    bot = obter_bot()
    ids_bot = {g.id for g in bot.guilds} if bot and bot.is_ready() else set()

    gerenciaveis = []
    for g in usuario.get("guilds", []):
        if not usuario_pode_gerenciar(g):
            continue
        gid = int(g["id"])
        gerenciaveis.append({
            "id": gid,
            "nome": g["name"],
            "icone": (
                f"https://cdn.discordapp.com/icons/{gid}/{g['icon']}.png" if g.get("icon") else None
            ),
            "bot_presente": gid in ids_bot,
        })

    return templates.TemplateResponse(
        "servidores.html", {"request": request, "usuario": usuario, "servidores": gerenciaveis}
    )


@router.get("/dashboard/{guild_id}", response_class=HTMLResponse)
async def dashboard(request: Request, guild_id: int):
    guild: discord.Guild = exigir_acesso_guild(request, guild_id)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "guild_id": guild_id, "guild_nome": guild.name},
    )


@router.get("/api/config/{guild_id}")
async def obter_config(request: Request, guild_id: int):
    guild = exigir_acesso_guild(request, guild_id)
    cfg = config_store.get(guild_id)
    canais = [{"id": str(c.id), "nome": c.name} for c in guild.text_channels]
    cargos = [{"id": str(r.id), "nome": r.name} for r in guild.roles if not r.is_default()]
    return {"config": cfg, "canais_texto": canais, "cargos": cargos}


@router.post("/api/config/{guild_id}")
async def salvar_config(request: Request, guild_id: int, payload: dict = Body(...)):
    exigir_acesso_guild(request, guild_id)
    campos_aceitos = {"prefixo", "canal_musica_id", "dj_role_id"}
    dados = {k: v for k, v in payload.items() if k in campos_aceitos}
    novo = await config_store.set(guild_id, **dados)
    return {"ok": True, "config": novo}
