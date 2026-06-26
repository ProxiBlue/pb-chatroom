"""Tests for PollingLoop — tick-based cursor-advancing thread poller."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx

from pb_chatroom_relay.polling import PollingLoop
from pb_chatroom_relay.state import State


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_thread(thread_id: str, updated_at: str) -> dict[str, Any]:
    return {'id': thread_id, 'updated_at': updated_at, 'subject': 'test'}


def make_state(tmp_state_dir: Path, poll_cursor: str | None = None) -> tuple[State, Path]:
    path = tmp_state_dir / 'state.json'
    state = State(poll_cursor=poll_cursor)
    state.save(path)
    return state, path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_it_calls_list_threads_with_the_persisted_since_cursor_on_first_tick(
    tmp_state_dir,
):
    state, path = make_state(tmp_state_dir, poll_cursor='2026-06-01T00:00:00Z')
    client = AsyncMock()
    client.list_threads.return_value = []

    loop = PollingLoop(client=client, state=state, state_path=path)
    await loop.tick()

    client.list_threads.assert_called_once_with(since='2026-06-01T00:00:00Z')


async def test_it_advances_the_cursor_to_the_max_updated_at_across_returned_threads(
    tmp_state_dir,
):
    state, path = make_state(tmp_state_dir, poll_cursor=None)
    client = AsyncMock()
    client.list_threads.return_value = [
        make_thread('t1', '2026-06-01T10:00:00Z'),
        make_thread('t2', '2026-06-01T12:00:00Z'),
        make_thread('t3', '2026-06-01T11:00:00Z'),
    ]

    loop = PollingLoop(client=client, state=state, state_path=path)
    await loop.tick()

    assert state.poll_cursor == '2026-06-01T12:00:00Z'


async def test_it_does_not_advance_the_cursor_when_list_threads_returns_an_empty_result(
    tmp_state_dir,
):
    state, path = make_state(tmp_state_dir, poll_cursor='2026-06-01T09:00:00Z')
    client = AsyncMock()
    client.list_threads.return_value = []

    loop = PollingLoop(client=client, state=state, state_path=path)
    await loop.tick()

    assert state.poll_cursor == '2026-06-01T09:00:00Z'


async def test_it_delivers_each_new_thread_to_every_registered_subscriber_callback(
    tmp_state_dir,
):
    state, path = make_state(tmp_state_dir)
    threads = [
        make_thread('t1', '2026-06-01T10:00:00Z'),
        make_thread('t2', '2026-06-01T11:00:00Z'),
    ]
    client = AsyncMock()
    client.list_threads.return_value = threads

    received_a: list[dict] = []
    received_b: list[dict] = []

    async def subscriber_a(thread: dict) -> None:
        received_a.append(thread)

    async def subscriber_b(thread: dict) -> None:
        received_b.append(thread)

    loop = PollingLoop(client=client, state=state, state_path=path)
    loop.subscribe(subscriber_a)
    loop.subscribe(subscriber_b)
    await loop.tick()

    assert received_a == threads
    assert received_b == threads


async def test_it_does_not_deliver_a_thread_twice_when_same_updated_at_appears_across_polls(
    tmp_state_dir,
):
    """After cursor advances to T1, second tick with empty result won't re-notify."""
    state, path = make_state(tmp_state_dir)
    thread = make_thread('t1', '2026-06-01T10:00:00Z')

    client = AsyncMock()
    # First tick: returns thread; second tick: server filtered by since, returns empty
    client.list_threads.side_effect = [
        [thread],  # first tick
        [],        # second tick — since=T1, strictly >T1 excludes t1
    ]

    received: list[dict] = []

    async def subscriber(t: dict) -> None:
        received.append(t)

    loop = PollingLoop(client=client, state=state, state_path=path)
    loop.subscribe(subscriber)

    await loop.tick()
    assert received == [thread]
    assert state.poll_cursor == '2026-06-01T10:00:00Z'

    await loop.tick()
    # second tick called with since=T1
    assert client.list_threads.call_args_list[1].kwargs['since'] == '2026-06-01T10:00:00Z'
    # no new notifications — empty result
    assert received == [thread]


async def test_it_logs_and_retries_on_a_transient_http_error_without_advancing_the_cursor(
    tmp_state_dir, caplog
):
    state, path = make_state(tmp_state_dir, poll_cursor='2026-06-01T08:00:00Z')
    client = AsyncMock()
    client.list_threads.side_effect = httpx.HTTPStatusError(
        'server error',
        request=MagicMock(),
        response=MagicMock(status_code=503),
    )

    received: list[dict] = []

    async def subscriber(t: dict) -> None:
        received.append(t)

    loop = PollingLoop(client=client, state=state, state_path=path)
    loop.subscribe(subscriber)

    with caplog.at_level(logging.WARNING):
        await loop.tick()

    # cursor must NOT have advanced
    assert state.poll_cursor == '2026-06-01T08:00:00Z'
    # no subscribers notified
    assert received == []
    # must have logged something
    assert len(caplog.records) > 0


async def test_it_persists_the_advanced_cursor_via_the_state_layer_after_each_tick(
    tmp_state_dir,
):
    state, path = make_state(tmp_state_dir, poll_cursor=None)
    client = AsyncMock()
    client.list_threads.return_value = [
        make_thread('t1', '2026-06-01T15:00:00Z'),
    ]

    loop = PollingLoop(client=client, state=state, state_path=path)
    await loop.tick()

    # Reload from disk and check cursor was persisted
    reloaded = State.load(path)
    assert reloaded.poll_cursor == '2026-06-01T15:00:00Z'
