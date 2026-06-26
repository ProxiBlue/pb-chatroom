"""Tests for BroadcasterEmitter."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from pb_chatroom_relay.broadcaster import BroadcasterEmitter
from pb_chatroom_relay.config import BroadcasterConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 26, 10, 0, 0, tzinfo=timezone.utc)


def _cfg(**kwargs) -> BroadcasterConfig:
    defaults = dict(
        enabled=True,
        broadcast_to=['alice', 'bob'],
        prompt_subject='Stand-up time',
        prompt_body='How is progress today?',
    )
    defaults.update(kwargs)
    return BroadcasterConfig(**defaults)


def _stub_client(side_effect=None) -> AsyncMock:
    client = AsyncMock()
    if side_effect is not None:
        client.create_root_thread.side_effect = side_effect
    return client


def _stub_idle() -> Mock:
    return Mock()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_creates_one_root_thread_per_participant_in_broadcast_to():
    client = _stub_client()
    idle = _stub_idle()
    emitter = BroadcasterEmitter(client, idle)
    cfg = _cfg(broadcast_to=['alice', 'bob', 'carol'])

    count = await emitter.emit('check_in', cfg, _NOW)

    assert count == 3
    assert client.create_root_thread.call_count == 3


@pytest.mark.asyncio
async def test_it_stamps_each_created_thread_with_metadata_broadcaster_equal_to_the_broadcaster_name():  # noqa: E501
    client = _stub_client()
    idle = _stub_idle()
    emitter = BroadcasterEmitter(client, idle)
    cfg = _cfg(broadcast_to=['alice', 'bob'])

    await emitter.emit('my_broadcaster', cfg, _NOW)

    for c in client.create_root_thread.call_args_list:
        assert c.kwargs['metadata'] == {'broadcaster': 'my_broadcaster'}


@pytest.mark.asyncio
async def test_it_uses_the_configured_prompt_subject_as_the_thread_subject():
    client = _stub_client()
    idle = _stub_idle()
    emitter = BroadcasterEmitter(client, idle)
    cfg = _cfg(broadcast_to=['alice'], prompt_subject='Daily Stand-up')

    await emitter.emit('check_in', cfg, _NOW)

    client.create_root_thread.assert_called_once()
    assert client.create_root_thread.call_args.kwargs['subject'] == 'Daily Stand-up'


@pytest.mark.asyncio
async def test_it_uses_the_configured_prompt_body_as_the_initial_message_body():
    client = _stub_client()
    idle = _stub_idle()
    emitter = BroadcasterEmitter(client, idle)
    cfg = _cfg(broadcast_to=['alice'], prompt_body='What did you work on?')

    await emitter.emit('check_in', cfg, _NOW)

    client.create_root_thread.assert_called_once()
    assert client.create_root_thread.call_args.kwargs['body'] == 'What did you work on?'


@pytest.mark.asyncio
async def test_it_records_the_emission_against_the_idle_supervisor_after_a_successful_round():
    client = _stub_client()
    idle = _stub_idle()
    emitter = BroadcasterEmitter(client, idle)
    cfg = _cfg(broadcast_to=['alice', 'bob'])

    await emitter.emit('check_in', cfg, _NOW)

    idle.record_emission.assert_called_once_with('check_in', _NOW)


@pytest.mark.asyncio
async def test_it_continues_to_the_next_participant_when_one_create_root_thread_call_raises():
    # First call raises, second succeeds
    client = _stub_client(side_effect=[RuntimeError('network error'), None])
    idle = _stub_idle()
    emitter = BroadcasterEmitter(client, idle)
    cfg = _cfg(broadcast_to=['alice', 'bob'])

    count = await emitter.emit('check_in', cfg, _NOW)

    assert count == 1
    assert client.create_root_thread.call_count == 2


@pytest.mark.asyncio
async def test_it_does_not_record_the_emission_when_zero_threads_were_created_successfully():
    # Both calls raise
    client = _stub_client(side_effect=[RuntimeError('fail'), RuntimeError('fail')])
    idle = _stub_idle()
    emitter = BroadcasterEmitter(client, idle)
    cfg = _cfg(broadcast_to=['alice', 'bob'])

    count = await emitter.emit('check_in', cfg, _NOW)

    assert count == 0
    idle.record_emission.assert_not_called()
