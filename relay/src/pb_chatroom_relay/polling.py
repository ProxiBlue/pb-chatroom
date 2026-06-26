"""PollingLoop — tick-based thread poller with cursor persistence."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from pb_chatroom_relay.state import State

logger = logging.getLogger(__name__)

SubscriberCallback = Callable[[dict[str, Any]], Awaitable[None]]


class PollingLoop:
    """Polls list_threads on an interval, advances a cursor, notifies subscribers.

    Args:
        client: ChatroomClient instance (or any object with list_threads).
        state: Loaded State instance (mutable, updated in-place).
        state_path: Path to persist state after each tick.
        interval_seconds: Seconds between ticks in run() loop.
    """

    def __init__(
        self,
        client: Any,
        state: State,
        state_path: Path,
        interval_seconds: int = 10,
    ) -> None:
        self._client = client
        self._state = state
        self._state_path = state_path
        self.interval_seconds = interval_seconds
        self._subscribers: list[SubscriberCallback] = []

    def subscribe(self, callback: SubscriberCallback) -> None:
        """Register a callback to be called with each new thread dict."""
        self._subscribers.append(callback)

    async def tick(self) -> None:
        """Execute ONE poll cycle: fetch threads, advance cursor, notify subscribers."""
        try:
            threads = await self._client.list_threads(since=self._state.poll_cursor)
        except httpx.HTTPStatusError as exc:
            logger.warning('Transient HTTP error during poll: %s — will retry next tick', exc)
            return
        except Exception as exc:
            logger.warning('Unexpected error during poll: %s — will retry next tick', exc)
            return

        if not threads:
            return

        # Advance cursor to max updated_at across returned threads
        max_updated_at = max(t['updated_at'] for t in threads)
        self._state.poll_cursor = max_updated_at
        self._state.save(self._state_path)

        # Notify all subscribers
        for thread in threads:
            for subscriber in self._subscribers:
                await subscriber(thread)

    async def run(self) -> None:
        """Loop forever: tick, sleep, repeat."""
        while True:
            await self.tick()
            await asyncio.sleep(self.interval_seconds)
