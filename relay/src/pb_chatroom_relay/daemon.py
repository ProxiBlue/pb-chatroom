"""Daemon — top-level orchestration of relay components."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pb_chatroom_relay.archiver import Archiver
from pb_chatroom_relay.broadcaster import BroadcasterEmitter
from pb_chatroom_relay.budget import BudgetEngine, UtcClock
from pb_chatroom_relay.client import ChatroomClient
from pb_chatroom_relay.config import RespondersConfig
from pb_chatroom_relay.dispatcher import DispatchStatus, ResponderDispatcher
from pb_chatroom_relay.health import build_health_app
from pb_chatroom_relay.idle import IdleSupervisor
from pb_chatroom_relay.identity_validation import validate_identities
from pb_chatroom_relay.polling import PollingLoop
from pb_chatroom_relay.responder import ResponderReplyPoster
from pb_chatroom_relay.state import State

logger = logging.getLogger(__name__)

# Sentinel — distinguishes "caller passed None explicitly" from "use auto-build"
_AUTO = object()


# ---------------------------------------------------------------------------
# DaemonConfig
# ---------------------------------------------------------------------------


@dataclass
class DaemonConfig:
    server_url: str = 'http://server:7476'
    participant_id: str = 'relay'
    state_path: Path = field(default_factory=lambda: Path('relay/state/state.json'))
    health_port: int = 8000
    poll_interval_seconds: int = 10
    archiver_interval_seconds: int = 60
    broadcaster_interval_seconds: int = 60


# ---------------------------------------------------------------------------
# Default uvicorn serve
# ---------------------------------------------------------------------------


async def _default_uvicorn_serve(app: Any, host: str, port: int) -> None:
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level='warning')
    server = uvicorn.Server(config)
    await server.serve()


# ---------------------------------------------------------------------------
# Real subprocess runner
# ---------------------------------------------------------------------------


class _RealSubprocessRunner:
    async def run(
        self,
        argv: list[str],
        cwd: str | None,
        stdin_data: bytes,
        timeout_seconds: float,
    ) -> tuple[bytes, bytes, int]:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(stdin_data),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise
        return stdout, stderr, proc.returncode or 0


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------


class Daemon:
    """Top-level relay daemon orchestrator.

    All component dependencies can be injected for testing; when *_AUTO* (the
    default sentinel), they are constructed from *responders_config* and
    *daemon_config*. Pass ``None`` explicitly to skip construction even when
    config would normally enable the component.
    """

    def __init__(
        self,
        responders_config: RespondersConfig,
        daemon_config: DaemonConfig | None = None,
        *,
        client: Any = None,
        state: Any = None,
        budget_engine: Any = None,
        polling_loop: Any = None,
        dispatcher: Any = _AUTO,
        poster: Any = None,
        idle_supervisor: Any = None,
        broadcaster_emitter: Any = _AUTO,
        archiver: Any = _AUTO,
        uvicorn_serve: Callable | None = None,
    ) -> None:
        self._config = responders_config
        self._dc = daemon_config or DaemonConfig()
        self._uvicorn_serve = uvicorn_serve or _default_uvicorn_serve

        # --- state ---
        self._state: State = state if state is not None else State.load(self._dc.state_path)

        # --- client ---
        self._client: ChatroomClient = (
            client
            if client is not None
            else ChatroomClient(
                base_url=self._dc.server_url,
                participant_id=self._dc.participant_id,
            )
        )

        # --- polling loop ---
        self._polling_loop: Any = (
            polling_loop
            if polling_loop is not None
            else PollingLoop(
                client=self._client,
                state=self._state,
                state_path=self._dc.state_path,
                interval_seconds=self._dc.poll_interval_seconds,
            )
        )

        # --- budget engine ---
        if budget_engine is not None:
            self._budget_engine: BudgetEngine = budget_engine
        else:
            self._budget_engine = BudgetEngine(
                state=self._state,
                clock=UtcClock(),
                state_path=self._dc.state_path,
            )
            for name, rc in self._config.responders.items():
                self._budget_engine.add_responder(name, rc.budget)

        # --- dispatcher ---
        if dispatcher is not _AUTO:
            self._dispatcher: ResponderDispatcher | None = dispatcher
        else:
            if self._config.responders:
                self._dispatcher = ResponderDispatcher(
                    runner=_RealSubprocessRunner(),
                    budget_engine=self._budget_engine,
                )
            else:
                self._dispatcher = None

        # --- poster ---
        self._poster: ResponderReplyPoster | None = (
            poster if poster is not None else (
                ResponderReplyPoster(client=self._client) if self._dispatcher else None
            )
        )

        # --- idle supervisor ---
        self._idle_supervisor: IdleSupervisor | None = idle_supervisor

        # --- broadcaster emitter ---
        if broadcaster_emitter is not _AUTO:
            self._broadcaster_emitter: BroadcasterEmitter | None = broadcaster_emitter
        else:
            active_broadcasters = {
                k: v for k, v in self._config.broadcasters.items() if v.enabled
            }
            if active_broadcasters:
                if self._idle_supervisor is None:
                    self._idle_supervisor = IdleSupervisor(
                        state=self._state,
                        state_path=self._dc.state_path,
                        last_activity_getter=lambda: None,
                    )
                self._broadcaster_emitter = BroadcasterEmitter(
                    client=self._client,
                    idle_supervisor=self._idle_supervisor,
                )
            else:
                self._broadcaster_emitter = None

        # --- archiver ---
        if archiver is not _AUTO:
            self._archiver: Archiver | None = archiver
        else:
            active_archivers = {
                k: v for k, v in self._config.archivers.items() if v.enabled
            }
            if active_archivers:
                archiver_cfg = next(iter(active_archivers.values()))

                class _NoopGraphitiClient:
                    async def add_memory(
                        self, group_id: str, content: str, source_type: str
                    ) -> None:
                        pass

                self._archiver = Archiver(
                    config=archiver_cfg,
                    chatroom=self._client,
                    graphiti=_NoopGraphitiClient(),
                )
            else:
                self._archiver = None

    # ------------------------------------------------------------------
    # Subscriber wiring
    # ------------------------------------------------------------------

    def _wire_subscribers(self) -> None:
        """Subscribe responder callback to the polling loop."""
        if self._dispatcher is None:
            return

        async def _responder_callback(thread: dict[str, Any]) -> None:
            dispatcher = self._dispatcher
            poster = self._poster
            if dispatcher is None or poster is None:
                return

            for name, rc in self._config.responders.items():
                result = await dispatcher.dispatch(name, thread, rc)
                if result.status != DispatchStatus.SKIPPED:
                    await poster.post(thread['id'], result)

        self._polling_loop.subscribe(_responder_callback)

    # ------------------------------------------------------------------
    # Status for healthcheck
    # ------------------------------------------------------------------

    def _get_status(self) -> dict[str, Any]:
        return {
            'last_poll_at': self._state.poll_cursor,
            'budget': self._budget_engine.snapshot(),
        }

    # ------------------------------------------------------------------
    # Task loops
    # ------------------------------------------------------------------

    async def _health_loop(self) -> None:
        app = build_health_app(self._get_status)
        await self._uvicorn_serve(app, host='0.0.0.0', port=self._dc.health_port)

    async def _archiver_loop(self) -> None:
        assert self._archiver is not None
        while True:
            await self._archiver.archive_since(
                cursor=self._state.archive_cursor,
                state=self._state,
                state_path=self._dc.state_path,
            )
            await asyncio.sleep(self._dc.archiver_interval_seconds)

    async def _broadcaster_loop(self) -> None:
        assert self._broadcaster_emitter is not None
        from datetime import UTC, datetime

        while True:
            now = datetime.now(UTC)
            for name, bc in self._config.broadcasters.items():
                if not bc.enabled:
                    continue
                if self._idle_supervisor and self._idle_supervisor.should_emit(name, bc, now):
                    await self._broadcaster_emitter.emit(name, bc, now)
            await asyncio.sleep(self._dc.broadcaster_interval_seconds)

    # ------------------------------------------------------------------
    # run()
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start all component tasks and run until cancelled."""
        validate_identities(self._config)
        self._wire_subscribers()

        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._polling_loop.run())
            tg.create_task(self._health_loop())

            if self._archiver is not None:
                tg.create_task(self._archiver_loop())

            if self._broadcaster_emitter is not None:
                tg.create_task(self._broadcaster_loop())
