"""
Suporte a Spotify: o Spotify não permite streaming de áudio via API pública,
então a estratégia (igual Hydra, Groovy, etc. faziam) é:

1. Reconhecer um link de música/álbum/playlist do Spotify.
2. Buscar os metadados (nome da faixa + artista(s)) via API oficial do Spotify
   (Client Credentials Flow — não precisa login de usuário, só client id/secret
   de um app criado em https://developer.spotify.com/dashboard).
3. Converter cada faixa em uma busca "artista - título" no YouTube via
   services/ytdlp_service, que é quem realmente fornece o áudio.

Se SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET não estiverem configurados no
.env, esse serviço fica desativado e o bot avisa o usuário meramente ignorando
o link do Spotify como uma busca de texto (não vai funcionar bem, mas não quebra).
"""

from __future__ import annotations

import base64
import os
import re
import time

import aiohttp

from utils.errors import BuscaFalhouError
from utils.logger import get_logger

log = get_logger(__name__)

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

_REGEX_SPOTIFY = re.compile(
    r"open\.spotify\.com/(?:intl-\w+/)?(track|album|playlist)/([a-zA-Z0-9]+)"
)

LIMITE_ITENS = 50


class SpotifyService:
    def __init__(self):
        self.habilitado = bool(CLIENT_ID and CLIENT_SECRET)
        self._token: str | None = None
        self._token_expira_em: float = 0

        if not self.habilitado:
            log.warning(
                "SPOTIFY_CLIENT_ID/SPOTIFY_CLIENT_SECRET não configurados — "
                "links do Spotify serão tratados como busca de texto simples."
            )

    @staticmethod
    def eh_link_spotify(texto: str) -> bool:
        return bool(_REGEX_SPOTIFY.search(texto))

    async def _obter_token(self) -> str:
        if self._token and time.time() < self._token_expira_em - 30:
            return self._token

        auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        async with aiohttp.ClientSession() as sessao:
            async with sessao.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {auth}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise BuscaFalhouError("não consegui autenticar com a API do Spotify.")
                dados = await resp.json()

        self._token = dados["access_token"]
        self._token_expira_em = time.time() + dados.get("expires_in", 3600)
        return self._token

    async def _get(self, sessao: aiohttp.ClientSession, url: str) -> dict:
        token = await self._obter_token()
        async with sessao.get(url, headers={"Authorization": f"Bearer {token}"}) as resp:
            if resp.status == 401:
                # token pode ter expirado entre a checagem e o uso; força renovação
                self._token = None
                token = await self._obter_token()
                async with sessao.get(url, headers={"Authorization": f"Bearer {token}"}) as resp2:
                    resp2.raise_for_status()
                    return await resp2.json()
            resp.raise_for_status()
            return await resp.json()

    async def resolver_queries(self, url_spotify: str) -> list[str]:
        """
        Recebe um link do Spotify (track/album/playlist) e devolve uma lista de
        strings de busca ("Artista - Título") prontas para o yt-dlp procurar no YouTube.
        """
        if not self.habilitado:
            raise BuscaFalhouError(
                "suporte a Spotify não configurado neste bot (defina SPOTIFY_CLIENT_ID "
                "e SPOTIFY_CLIENT_SECRET no .env)."
            )

        match = _REGEX_SPOTIFY.search(url_spotify)
        if not match:
            raise BuscaFalhouError("link do Spotify inválido.")
        tipo, item_id = match.group(1), match.group(2)

        async with aiohttp.ClientSession() as sessao:
            if tipo == "track":
                dados = await self._get(sessao, f"https://api.spotify.com/v1/tracks/{item_id}")
                return [_faixa_para_query(dados)]

            if tipo == "album":
                dados = await self._get(sessao, f"https://api.spotify.com/v1/albums/{item_id}/tracks?limit={LIMITE_ITENS}")
                faixas = dados.get("items", [])
                return [_faixa_para_query(f) for f in faixas[:LIMITE_ITENS]]

            if tipo == "playlist":
                dados = await self._get(sessao, f"https://api.spotify.com/v1/playlists/{item_id}/tracks?limit={LIMITE_ITENS}")
                itens = dados.get("items", [])
                queries = []
                for item in itens[:LIMITE_ITENS]:
                    faixa = item.get("track")
                    if faixa:
                        queries.append(_faixa_para_query(faixa))
                return queries

        raise BuscaFalhouError("tipo de link do Spotify não suportado.")


def _faixa_para_query(faixa: dict) -> str:
    artistas = ", ".join(a["name"] for a in faixa.get("artists", []) if a.get("name"))
    titulo = faixa.get("name", "")
    return f"{artistas} - {titulo}".strip(" -")


spotify_service = SpotifyService()
