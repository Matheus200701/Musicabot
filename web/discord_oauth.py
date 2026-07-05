"""
Cliente mínimo para o fluxo OAuth2 do Discord (Authorization Code Grant).

Não usa nenhuma lib de OAuth genérica de propósito — o fluxo do Discord é
simples o bastante (poucas chamadas HTTP) que uma dependência extra não
compensaria a complexidade adicional, mantendo o projeto leve.

Scopes usados: "identify guilds" (dados básicos do usuário + lista de
servidores em comum, para decidir quais servidores aparecem no painel).
"""

from __future__ import annotations

import os
import urllib.parse

import aiohttp

DISCORD_API = "https://discord.com/api/v10"
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
SCOPES = "identify guilds"


def url_autorizacao(state: str) -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "prompt": "none",
    }
    return f"https://discord.com/oauth2/authorize?{urllib.parse.urlencode(params)}"


async def trocar_code_por_token(code: str) -> dict:
    dados = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    async with aiohttp.ClientSession() as sessao:
        async with sessao.post(f"{DISCORD_API}/oauth2/token", data=dados) as resp:
            resp.raise_for_status()
            return await resp.json()


async def obter_usuario(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as sessao:
        async with sessao.get(f"{DISCORD_API}/users/@me", headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()


async def obter_guilds_usuario(access_token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as sessao:
        async with sessao.get(f"{DISCORD_API}/users/@me/guilds", headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()


def usuario_pode_gerenciar(guild_resumo: dict) -> bool:
    """Verifica, a partir do resumo retornado por /users/@me/guilds, se o usuário
    é dono do servidor ou tem permissão de Gerenciar Servidor (bit 0x20)."""
    if guild_resumo.get("owner"):
        return True
    permissoes = int(guild_resumo.get("permissions", 0))
    MANAGE_GUILD = 0x20
    ADMINISTRATOR = 0x8
    return bool(permissoes & MANAGE_GUILD or permissoes & ADMINISTRATOR)
