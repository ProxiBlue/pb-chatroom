"""ResponderDispatcher — trigger evaluation, argv construction, subprocess dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatch
from typing import Any, Protocol

from pb_chatroom_relay.budget import BudgetEngine
from pb_chatroom_relay.config import ResponderConfig


# ---------------------------------------------------------------------------
# Protocol + fake for SubprocessRunner
# ---------------------------------------------------------------------------


class SubprocessRunner(Protocol):
    async def run(
        self,
        argv: list[str],
        cwd: str | None,
        stdin_data: bytes,
        timeout_seconds: float,
    ) -> tuple[bytes, bytes, int]:
        """Returns (stdout, stderr, returncode). Raises TimeoutError on timeout."""
        ...


class FakeSubprocessRunner:
    """Test double for SubprocessRunner."""

    def __init__(
        self,
        stdout: bytes = b'',
        stderr: bytes = b'',
        returncode: int = 0,
        fail_first_n: int = 0,
        raise_timeout: bool = False,
    ) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self._returncode = returncode
        self._fail_first_n = fail_first_n
        self._raise_timeout = raise_timeout
        self.call_count = 0
        self.last_argv: list[str] = []
        self.last_cwd: str | None = None
        self.last_stdin_data: bytes = b''

    async def run(
        self,
        argv: list[str],
        cwd: str | None,
        stdin_data: bytes,
        timeout_seconds: float,
    ) -> tuple[bytes, bytes, int]:
        self.call_count += 1
        self.last_argv = argv
        self.last_cwd = cwd
        self.last_stdin_data = stdin_data

        if self._raise_timeout:
            raise TimeoutError

        if self.call_count <= self._fail_first_n:
            return b'', b'transient error', 1

        return self._stdout, self._stderr, self._returncode


# ---------------------------------------------------------------------------
# DispatchResult
# ---------------------------------------------------------------------------


class DispatchStatus(Enum):
    SUCCESS = 'success'
    REFUSED_BUDGET = 'refused_budget'
    TIMED_OUT = 'timed_out'
    FAILED = 'failed'
    SKIPPED = 'skipped'


@dataclass
class DispatchResult:
    status: DispatchStatus
    stdout: bytes = b''
    stderr: bytes = b''
    returncode: int = 0
    error_message: str = ''


# ---------------------------------------------------------------------------
# Trigger matching helpers
# ---------------------------------------------------------------------------


def _thread_matches_trigger(thread: dict[str, Any], config: ResponderConfig) -> bool:
    """Return True iff the thread satisfies the responder's trigger conditions."""
    trigger = config.trigger
    has_from = bool(trigger.from_pattern)
    has_keywords = bool(trigger.subject_keywords)

    if has_from and not fnmatch(thread.get('from_participant', ''), trigger.from_pattern):
        return False

    if has_keywords:
        subject_lower = thread.get('subject', '').lower()
        if not any(kw.lower() in subject_lower for kw in trigger.subject_keywords):
            return False

    # If neither condition is configured, match everything
    return True


# ---------------------------------------------------------------------------
# Stdin body formatter
# ---------------------------------------------------------------------------


def _format_stdin(thread: dict[str, Any], system_prompt_addendum: str) -> bytes:
    parts = [
        f"Subject: {thread.get('subject', '')}",
        f"From: {thread.get('from_participant', '')}",
        '',
        thread.get('body', ''),
    ]
    if system_prompt_addendum:
        parts += ['', '---', system_prompt_addendum]
    return '\n'.join(parts).encode()


# ---------------------------------------------------------------------------
# ResponderDispatcher
# ---------------------------------------------------------------------------


class ResponderDispatcher:
    def __init__(
        self,
        runner: SubprocessRunner,
        budget_engine: BudgetEngine,
        default_timeout: float = 300.0,
    ) -> None:
        self._runner = runner
        self._budget_engine = budget_engine
        self._default_timeout = default_timeout

    async def dispatch(
        self,
        responder_name: str,
        thread: dict[str, Any],
        config: ResponderConfig,
    ) -> DispatchResult:
        # Skip broadcaster-originated threads to avoid self-feedback loops
        if thread.get('metadata', {}).get('broadcaster'):
            return DispatchResult(status=DispatchStatus.SKIPPED)

        # Evaluate trigger filters
        if not _thread_matches_trigger(thread, config):
            return DispatchResult(status=DispatchStatus.SKIPPED)

        # Check budget
        if not self._budget_engine.can_dispatch(responder_name):
            return DispatchResult(status=DispatchStatus.REFUSED_BUDGET)

        inv = config.claude_invocation
        argv = ['claude', '--print', '--model', inv.model] + list(inv.extra_args)
        cwd = inv.cwd or None
        stdin_data = _format_stdin(thread, inv.system_prompt_addendum)
        timeout = self._default_timeout

        # Attempt dispatch with one retry on transient failure
        result = await self._run_with_retry(argv, cwd, stdin_data, timeout)

        if result.status == DispatchStatus.SUCCESS:
            self._budget_engine.record_dispatch(responder_name)

        return result

    async def _run_with_retry(
        self,
        argv: list[str],
        cwd: str | None,
        stdin_data: bytes,
        timeout: float,
    ) -> DispatchResult:
        for attempt in range(2):
            try:
                stdout, stderr, returncode = await self._runner.run(
                    argv=argv,
                    cwd=cwd,
                    stdin_data=stdin_data,
                    timeout_seconds=timeout,
                )
            except TimeoutError:
                return DispatchResult(
                    status=DispatchStatus.TIMED_OUT,
                    error_message='subprocess timed out',
                )

            if returncode == 0:
                return DispatchResult(
                    status=DispatchStatus.SUCCESS,
                    stdout=stdout,
                    stderr=stderr,
                    returncode=returncode,
                )

            # Transient failure — retry once, then give up
            if attempt == 1:
                return DispatchResult(
                    status=DispatchStatus.FAILED,
                    stdout=stdout,
                    stderr=stderr,
                    returncode=returncode,
                    error_message=f'subprocess exited with code {returncode}',
                )

        # Unreachable, but satisfies type checker
        return DispatchResult(status=DispatchStatus.FAILED)
