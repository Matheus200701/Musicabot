"""
Wrapper sobre o yt-dlp: extrai metadados de uma busca/URL, com cache e
tratamento de erros mais informativo que o original.

Mantém a mesma ideia do flavimusic original (extract_info sem download,
streaming direto pro FFmpeg), mas:
- adiciona thumbnail, uploader e id ao resultado (usados nos embeds novos)
- cacheia buscas por texto (services/cache.py) por 30 min
- suporta limite de playlist (evita travar o bot com uma playlist de 500 músicas)
- roda tudo em threadpool (extract_info é bloqueante)
"""

from __future__ import annotations

import asyncio
import re

import yt_dlp

from services.cache import cache_busca
from utils.errors import BuscaFalhouError
from utils.logger import get_logger

log = get_logger(__name__)

LIMITE_PLAYLIST = 50

YDL_OPTS_BASE = {
    "format": "bestaudio*/bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": "in_playlist",
    "skip_download": True,
    "ignoreerrors": "only_download",
    "extractor_args": {
        "youtube": {"player_client": ["android", "web"]},
    },
}

FFMPEG_OPTS = {
    "before_options": (
        "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
        "-nostdin -loglevel panic"
    ),
    "options": "-vn",
}

_REGEX_URL = re.compile(r"^https?://", re.IGNORECASE)


class YtdlpService:
    def __init__(self):
        self._ydl = yt_dlp.YoutubeDL(YDL_OPTS_BASE)

    def _extrair_sync(self, query: str) -> dict:
        return self._ydl.extract_info(query, download=False)

    @staticmethod
    def _normalizar(entry: dict) -> dict:
        return {
            "id": entry.get("id"),
            "title": entry.get("title") or "Desconhecido",
            "webpage_url": entry.get("webpage_url") or entry.get("url", ""),
            "duration": entry.get("duration") or 0,
            "thumbnail": entry.get("thumbnail"),
            "uploader": entry.get("uploader"),
            "stream_url": None,  # resolvido só na hora de tocar (evita URLs de stream expiradas)
        }

    async def buscar(self, query: str) -> list[dict]:
        """
        Busca uma música/URL/playlist e retorna uma lista de faixas (metadados leves,
        sem a stream_url ainda — essa é resolvida sob demanda em `resolver_stream`,
        pois links de stream do YouTube expiram em pouco tempo).
        """
        query = query.strip()
        chave_cache = f"busca::{query}"
        cacheado = cache_busca.get(chave_cache)
        if cacheado is not None:
            return [dict(f) for f in cacheado]

        loop = asyncio.get_event_loop()
        try:
            dados = await loop.run_in_executor(None, self._extrair_sync, query)
        except yt_dlp.utils.DownloadError as e:
            raise BuscaFalhouError(_mensagem_amigavel(str(e))) from e
        except Exception as e:  # noqa: BLE001 - queremos capturar qualquer erro do extractor
            raise BuscaFalhouError(str(e)) from e

        if not dados:
            raise BuscaFalhouError("nenhum resultado encontrado.")

        entradas = dados.get("entries")
        if entradas is not None:
            entradas = [e for e in entradas if e][:LIMITE_PLAYLIST]
            if not entradas:
                raise BuscaFalhouError("playlist vazia ou indisponível.")
            faixas = [self._normalizar(e) for e in entradas]
        else:
            faixas = [self._normalizar(dados)]

        cache_busca.set(chave_cache, faixas)
        return [dict(f) for f in faixas]

    async def resolver_stream(self, faixa: dict) -> str:
        """Resolve a URL de stream real de uma faixa no momento de tocá-la (URLs expiram)."""
        chave_cache = f"stream::{faixa.get('id') or faixa.get('webpage_url')}"
        url_cacheada = cache_busca.get(chave_cache)
        if url_cacheada:
            return url_cacheada

        alvo = faixa.get("webpage_url") or faixa.get("id")
        if not alvo:
            raise BuscaFalhouError("faixa sem identificador válido.")

        loop = asyncio.get_event_loop()
        try:
            dados = await loop.run_in_executor(None, lambda: self._ydl.extract_info(alvo, download=False))
        except yt_dlp.utils.DownloadError as e:
            raise BuscaFalhouError(_mensagem_amigavel(str(e))) from e

        stream_url = dados.get("url")
        if not stream_url:
            raise BuscaFalhouError("não consegui obter o áudio dessa faixa.")

        # URLs de stream do YouTube costumam durar ~6h; cacheamos por bem menos tempo por segurança.
        cache_busca.set(chave_cache, stream_url)
        return stream_url

    @staticmethod
    def eh_url(texto: str) -> bool:
        return bool(_REGEX_URL.match(texto.strip()))


def _mensagem_amigavel(erro_original: str) -> str:
    erro_lower = erro_original.lower()
    if "sign in" in erro_lower or "confirm your age" in erro_lower:
        return "o YouTube pediu confirmação/login pra esse vídeo (restrição de idade ou região)."
    if "private video" in erro_lower:
        return "esse vídeo é privado."
    if "unavailable" in erro_lower:
        return "esse conteúdo não está mais disponível."
    if "video unavailable" in erro_lower:
        return "vídeo indisponível."
    return "erro ao processar esse link/busca."


ytdlp_service = YtdlpService()
