from collections import deque

import pytest

from services.music_resolver import Track
from services.pro_player import GuildPlayer, LoopMode


def test_track_and_queue_model():
    track = Track("Test", "https://example.invalid/audio", None, 90, None, "artist", "test", 1)
    player = GuildPlayer(1, deque([track]))
    assert player.queue.popleft().title == "Test"
    assert player.loop is LoopMode.OFF


def test_loop_modes_are_explicit():
    assert {m.value for m in LoopMode} == {"off", "track", "queue"}

@pytest.mark.asyncio
async def test_async_test_runtime():
    await __import__("asyncio").sleep(0)
