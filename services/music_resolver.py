from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import yt_dlp


@dataclass(slots=True, frozen=True)
class Track:
    title: str
    url: str
    webpage_url: str | None
    duration: float | None
    thumbnail: str | None
    uploader: str | None
    source: str | None
    requester_id: int


class MusicResolver:
    """Resolve buscas/URLs usando yt-dlp sem bloquear o event loop."""

    def __init__(self) -> None:
        self.options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "extract_flat": False,
            "default_search": "ytsearch",
        }

    def _extract(self, query: str) -> dict[str, Any]:
        with yt_dlp.YoutubeDL(self.options) as ydl:
            return ydl.extract_info(query, download=False)

    async def resolve(self, query: str, requester_id: int, *, search: bool = False) -> Track:
        target = f"ytsearch1:{query}" if search else query
        info = await asyncio.to_thread(self._extract, target)
        if "entries" in info:
            entries = [e for e in info["entries"] if e]
            if not entries:
                raise ValueError("Nenhum resultado encontrado")
            info = entries[0]
        return Track(
            title=str(info.get("title") or "Sem título"),
            url=str(info.get("url") or ""),
            webpage_url=info.get("webpage_url"),
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
            uploader=info.get("uploader") or info.get("channel"),
            source=info.get("extractor_key") or info.get("extractor"),
            requester_id=requester_id,
        )

    async def search(self, query: str, requester_id: int, limit: int = 10) -> list[Track]:
        def extract() -> dict[str, Any]:
            with yt_dlp.YoutubeDL({**self.options, "noplaylist": False}) as ydl:
                return ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        info = await asyncio.to_thread(extract)
        tracks: list[Track] = []
        for entry in info.get("entries") or []:
            if not entry:
                continue
            tracks.append(Track(str(entry.get("title") or "Sem título"), str(entry.get("url") or ""), entry.get("webpage_url"), entry.get("duration"), entry.get("thumbnail"), entry.get("uploader") or entry.get("channel"), entry.get("extractor_key"), requester_id))
        return tracks
