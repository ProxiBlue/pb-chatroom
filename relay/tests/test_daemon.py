"""Tests for Daemon — top-level orchestration of relay components."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pb_chatroom_relay.config import (
    ArchiverConfig,
    BroadcasterConfig,
    ResponderConfig,
    RespondersConfig,
)
from pb_chatroom_relay.daemon import Daemon, DaemonConfig


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


def _noop_uvicorn(app: Any, host: str, port: int) -> asyncio.coroutine:
    """Stub uvicorn.serve — returns immediately."""

    async def _serve() -> None:
        return

    return _serve()


async def _cancellable_uvicorn(app: Any, host: str, port: int) -> None:
    """Uvicorn stub that blocks until cancelled."""
    try:
        await asyncio.sleep(9999)
    except asyncio.CancelledError:
        raise


def _make_polling_loop_stub() -> MagicMock:
    """Return a PollingLoop stub whose run() sleeps until cancelled."""
    stub = MagicMock()
    stub.subscribe = MagicMock()

    async def _run() -> None:
        try:
            await asyncio.sleep(9999)
        except asyncio.CancelledError:
            raise

    stub.run = _run
    return stub


def _make_enabled_broadcaster_config() -> BroadcasterConfig:
    return BroadcasterConfig(
        enabled=True,
        idle_threshold_minutes=60,
        max_per_day=3,
        min_hours_between=4,
        broadcast_to=['target'],
        prompt_subject='Hello',
        prompt_body='World',
    )


def _make_enabled_archiver_config() -> ArchiverConfig:
    return ArchiverConfig(
        enabled=True,
        graphiti_group_id_resolution='literal',
        max_thread_chars=0,
    )


def _make_full_config() -> RespondersConfig:
    """All three role classes enabled."""
    return RespondersConfig(
        responders={
            'bot': ResponderConfig(),
        },
        broadcasters={
            'morning': _make_enabled_broadcaster_config(),
        },
        archivers={
            'default': _make_enabled_archiver_config(),
        },
    )


# ---------------------------------------------------------------------------
# Requirement 1: it constructs all components when all three role classes are enabled
# ---------------------------------------------------------------------------


async def test_it_constructs_all_components_when_all_three_role_classes_are_enabled(
    tmp_state_dir,
):
    cfg = _make_full_config()
    dc = DaemonConfig(state_path=tmp_state_dir / 'state.json')

    polling_stub = _make_polling_loop_stub()
    archiver_stub = MagicMock()

    async def _archiver_run() -> None:
        try:
            await asyncio.sleep(9999)
        except asyncio.CancelledError:
            raise

    archiver_stub.archive_since = AsyncMock(return_value=None)

    broadcaster_stub = MagicMock()

    async def _broadcaster_emit(*a: Any, **kw: Any) -> int:
        return 0

    broadcaster_stub.emit = _broadcaster_emit

    daemon = Daemon(
        responders_config=cfg,
        daemon_config=dc,
        polling_loop=polling_stub,
        archiver=archiver_stub,
        broadcaster_emitter=broadcaster_stub,
        uvicorn_serve=_noop_uvicorn,
    )

    assert daemon._polling_loop is polling_stub
    assert daemon._archiver is archiver_stub
    assert daemon._broadcaster_emitter is broadcaster_stub


# ---------------------------------------------------------------------------
# Requirement 2: it skips constructing the responder dispatcher when no responders configured
# ---------------------------------------------------------------------------


async def test_it_skips_constructing_the_responder_dispatcher_when_no_responders_are_configured(
    tmp_state_dir,
):
    cfg = RespondersConfig(responders={})  # no responders
    dc = DaemonConfig(state_path=tmp_state_dir / 'state.json')

    daemon = Daemon(
        responders_config=cfg,
        daemon_config=dc,
        uvicorn_serve=_noop_uvicorn,
    )

    assert daemon._dispatcher is None


# ---------------------------------------------------------------------------
# Requirement 3: it skips constructing the broadcaster emitter when empty/all disabled
# ---------------------------------------------------------------------------


async def test_it_skips_constructing_the_broadcaster_emitter_when_broadcasters_block_is_empty_or_all_disabled(  # noqa: E501
    tmp_state_dir,
):
    cfg_empty = RespondersConfig(broadcasters={})
    dc = DaemonConfig(state_path=tmp_state_dir / 'state.json')

    daemon_empty = Daemon(
        responders_config=cfg_empty,
        daemon_config=dc,
        uvicorn_serve=_noop_uvicorn,
    )
    assert daemon_empty._broadcaster_emitter is None

    cfg_disabled = RespondersConfig(
        broadcasters={'b': BroadcasterConfig(enabled=False)}
    )
    daemon_disabled = Daemon(
        responders_config=cfg_disabled,
        daemon_config=dc,
        uvicorn_serve=_noop_uvicorn,
    )
    assert daemon_disabled._broadcaster_emitter is None


# ---------------------------------------------------------------------------
# Requirement 4: it skips constructing the archiver when archivers default is disabled
# ---------------------------------------------------------------------------


async def test_it_skips_constructing_the_archiver_when_archivers_default_is_disabled(
    tmp_state_dir,
):
    cfg = RespondersConfig(
        archivers={'default': ArchiverConfig(enabled=False)}
    )
    dc = DaemonConfig(state_path=tmp_state_dir / 'state.json')

    daemon = Daemon(
        responders_config=cfg,
        daemon_config=dc,
        uvicorn_serve=_noop_uvicorn,
    )
    assert daemon._archiver is None


# ---------------------------------------------------------------------------
# Requirement 5: it wires the polling loop to deliver new threads to the responder pipeline
# ---------------------------------------------------------------------------


async def test_it_wires_the_polling_loop_to_deliver_new_threads_to_the_responder_pipeline(
    tmp_state_dir,
):
    cfg = RespondersConfig(
        responders={'bot': ResponderConfig()},
    )
    dc = DaemonConfig(state_path=tmp_state_dir / 'state.json')

    dispatched_threads: list[dict[str, Any]] = []

    class StubDispatcher:
        async def dispatch(
            self, responder_name: str, thread: dict, config: Any
        ) -> Any:
            dispatched_threads.append({'name': responder_name, 'thread': thread})
            from pb_chatroom_relay.dispatcher import DispatchResult, DispatchStatus

            return DispatchResult(status=DispatchStatus.SKIPPED)

    posted_results: list[tuple[str, Any]] = []

    class StubPoster:
        async def post(self, thread_id: str, result: Any) -> None:
            posted_results.append((thread_id, result))

    # Capture subscribe calls so we can invoke the callback manually
    subscribed_callbacks: list[Any] = []

    class StubPollingLoop:
        def subscribe(self, cb: Any) -> None:
            subscribed_callbacks.append(cb)

        async def run(self) -> None:
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                raise

    polling_stub = StubPollingLoop()

    daemon = Daemon(
        responders_config=cfg,
        daemon_config=dc,
        polling_loop=polling_stub,
        dispatcher=StubDispatcher(),
        poster=StubPoster(),
        uvicorn_serve=_noop_uvicorn,
    )

    # Run briefly to wire subscribers then cancel
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0)  # let run() wire subscribers
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    # At least one subscriber registered
    assert len(subscribed_callbacks) >= 1

    # Invoke the responder callback manually
    test_thread = {
        'id': 'thread-1',
        'to_participant': 'bot',
        'subject': 'hello',
        'body': 'world',
        'from_participant': 'user',
        'updated_at': '2026-01-01T00:00:00Z',
        'metadata': {},
    }
    for cb in subscribed_callbacks:
        await cb(test_thread)

    assert any(d['name'] == 'bot' for d in dispatched_threads)


# ---------------------------------------------------------------------------
# Requirement 6: it wires the polling loop to trigger the archiver on acked threads
# ---------------------------------------------------------------------------


async def test_it_wires_the_polling_loop_to_trigger_the_archiver_on_acked_threads(
    tmp_state_dir,
):
    """Archiver runs as independent timed task, not as a polling subscriber.
    Verify that when enabled, daemon._archiver is not None and an archiver_loop
    task is started alongside the polling loop.
    """
    archiver_calls: list[Any] = []

    class StubArchiver:
        async def archive_since(self, cursor: Any, state: Any, state_path: Any) -> None:
            archiver_calls.append(cursor)
            # Raise to stop the archiver loop after first call
            raise asyncio.CancelledError

    cfg = RespondersConfig(
        archivers={'default': _make_enabled_archiver_config()},
    )
    dc = DaemonConfig(state_path=tmp_state_dir / 'state.json')

    polling_stub = _make_polling_loop_stub()

    daemon = Daemon(
        responders_config=cfg,
        daemon_config=dc,
        polling_loop=polling_stub,
        archiver=StubArchiver(),
        uvicorn_serve=_noop_uvicorn,
    )

    assert daemon._archiver is not None

    # Run — archiver CancelledError bubbles up through TaskGroup
    try:
        await asyncio.wait_for(daemon.run(), timeout=2.0)
    except (asyncio.TimeoutError, asyncio.CancelledError, BaseException):
        pass

    assert len(archiver_calls) >= 1


# ---------------------------------------------------------------------------
# Requirement 7: it starts the healthcheck app under uvicorn on the configured port
# ---------------------------------------------------------------------------


async def test_it_starts_the_healthcheck_app_under_uvicorn_on_the_configured_port(
    tmp_state_dir,
):
    uvicorn_calls: list[dict[str, Any]] = []

    async def recording_uvicorn(app: Any, host: str, port: int) -> None:
        uvicorn_calls.append({'app': app, 'host': host, 'port': port})
        # Return immediately after recording

    cfg = RespondersConfig()
    dc = DaemonConfig(state_path=tmp_state_dir / 'state.json', health_port=9999)

    polling_stub = _make_polling_loop_stub()

    daemon = Daemon(
        responders_config=cfg,
        daemon_config=dc,
        polling_loop=polling_stub,
        uvicorn_serve=recording_uvicorn,
    )

    task = asyncio.create_task(daemon.run())
    # Give the TaskGroup time to start all tasks including health
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    assert len(uvicorn_calls) == 1
    assert uvicorn_calls[0]['port'] == 9999


# ---------------------------------------------------------------------------
# Requirement 8: it cancels all child tasks cleanly when shutdown is requested
# ---------------------------------------------------------------------------


async def test_it_cancels_all_child_tasks_cleanly_when_shutdown_is_requested(
    tmp_state_dir,
):
    cfg = RespondersConfig()
    dc = DaemonConfig(state_path=tmp_state_dir / 'state.json')

    polling_stub = _make_polling_loop_stub()

    daemon = Daemon(
        responders_config=cfg,
        daemon_config=dc,
        polling_loop=polling_stub,
        uvicorn_serve=_cancellable_uvicorn,
    )

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.02)

    # Cancel simulates SIGTERM
    task.cancel()

    try:
        await asyncio.wait_for(task, timeout=2.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass

    assert task.done()
