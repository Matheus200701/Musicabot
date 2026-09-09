from __future__ import annotations

import asyncio
import random
from collections import deque
from dataclasses import dataclass
from enum import StrEnum

import discord

from services.music_resolver import MusicResolver, Track


class LoopMode(StrEnum):
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"


@dataclass(slots=True)
class GuildPlayer:
    guild_id: int
    queue: deque[Track]
    current: Track | None = None
    voice: discord.VoiceClient | None = None
    volume: float = 0.5
    loop: LoopMode = LoopMode.OFF
    stopped: bool = False


class PlayerManager:
    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self.resolver = MusicResolver()
        self.players: dict[int, GuildPlayer] = {}
        self.locks: dict[int, asyncio.Lock] = {}

    def get(self, guild_id: int) -> GuildPlayer:
        return self.players.setdefault(guild_id, GuildPlayer(guild_id, deque()))

    async def connect(self, guild_id: int, channel: discord.VoiceChannel) -> GuildPlayer:
        player = self.get(guild_id)
        if player.voice and player.voice.is_connected():
            if player.voice.channel != channel:
                await player.voice.move_to(channel)
        else:
            player.voice = await channel.connect(reconnect=True, timeout=15)
        return player

    async def enqueue(self, guild: discord.Guild, channel: discord.VoiceChannel, query: str, requester_id: int, *, search: bool = False) -> Track:
        player = await self.connect(guild.id, channel)
        track = await self.resolver.resolve(query, requester_id, search=search)
        player.queue.append(track)
        if not player.voice.is_playing() and not player.voice.is_paused():
            await self._start_next(guild)
        return track

    async def _start_next(self, guild: discord.Guild) -> None:
        player = self.get(guild.id)
        async with self.locks.setdefault(guild.id, asyncio.Lock()):
            if player.loop is LoopMode.TRACK and player.current:
                track = player.current
            else:
                track = player.queue.popleft() if player.queue else None
            if track is None or not player.voice or not player.voice.is_connected():
                return
            player.current = track
            player.stopped = False
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(
                    track.url,
                    before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                    options="-vn",
                ),
                volume=player.volume,
            )

            def after(error: Exception | None) -> None:
                self.bot.loop.call_soon_threadsafe(lambda: asyncio.create_task(self._after(guild, error)))

            player.voice.play(source, after=after)

    async def _after(self, guild: discord.Guild, error: Exception | None) -> None:
        player = self.get(guild.id)
        if error:
            player.stopped = True
        if player.loop is LoopMode.QUEUE and player.current:
            player.queue.append(player.current)
        if not player.stopped:
            await self._start_next(guild)

    def pause(self, guild_id: int) -> None:
        player = self.get(guild_id)
        if player.voice and player.voice.is_playing():
            player.voice.pause()

    def resume(self, guild_id: int) -> None:
        player = self.get(guild_id)
        if player.voice and player.voice.is_paused():
            player.voice.resume()

    def skip(self, guild: discord.Guild) -> None:
        player = self.get(guild.id)
        if player.voice and (player.voice.is_playing() or player.voice.is_paused()):
            player.voice.stop()

    async def stop(self, guild_id: int) -> None:
        player = self.get(guild_id)
        player.stopped = True
        player.queue.clear()
        player.current = None
        if player.voice:
            await player.voice.disconnect(force=True)
            player.voice = None

    def shuffle(self, guild_id: int) -> None:
        player = self.get(guild_id)
        items = list(player.queue)
        random.shuffle(items)
        player.queue = deque(items)

    async def shutdown(self) -> None:
        for player in list(self.players.values()):
            if player.voice:
                await player.voice.disconnect(force=True)
        self.players.clear()
