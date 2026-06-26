"""Tests for ResponderDispatcher — trigger evaluation, argv construction, subprocess dispatch."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pb_chatroom_relay.budget import BudgetEngine, FakeClock
from pb_chatroom_relay.config import (
    BudgetConfig,
    ClaudeInvocationConfig,
    ResponderConfig,
    TriggerConfig,
)
from pb_chatroom_relay.dispatcher import (
    DispatchStatus,
    FakeSubprocessRunner,
    ResponderDispatcher,
)
from pb_chatroom_relay.state import State

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)


def _make_thread(
    subject: str = 'Hello world',
    from_participant: str = 'alice@example.com',
    body: str = 'Body text',
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        'id': 'thread-1',
        'subject': subject,
        'from_participant': from_participant,
        'body': body,
        'metadata': metadata or {},
    }


def _make_config(
    from_pattern: str = '',
    subject_keywords: list[str] | None = None,
    model: str = 'claude-opus-4-5',
    extra_args: list[str] | None = None,
    cwd: str = '/tmp',
    system_prompt_addendum: str = '',
    max_invocations_per_hour: int = 0,
    max_invocations_per_day: int = 0,
) -> ResponderConfig:
    return ResponderConfig(
        trigger=TriggerConfig(
            from_pattern=from_pattern,
            subject_keywords=subject_keywords or [],
        ),
        claude_invocation=ClaudeInvocationConfig(
            cwd=cwd,
            model=model,
            extra_args=extra_args or [],
            system_prompt_addendum=system_prompt_addendum,
        ),
        budget=BudgetConfig(
            max_invocations_per_hour=max_invocations_per_hour,
            max_invocations_per_day=max_invocations_per_day,
        ),
    )


def _make_engine(tmp_path: Path) -> BudgetEngine:
    state_path = tmp_path / 'state.json'
    state = State.load(state_path)
    clock = FakeClock(_T0)
    return BudgetEngine(state=state, clock=clock, state_path=state_path)


# ---------------------------------------------------------------------------
# Requirement 1: from_pattern wildcard matching
# ---------------------------------------------------------------------------


async def test_it_matches_a_thread_when_from_pattern_wildcard_matches_the_from_participant(
    tmp_path,
):
    runner = FakeSubprocessRunner(stdout=b'reply', stderr=b'', returncode=0)
    engine = _make_engine(tmp_path)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine)

    config = _make_config(from_pattern='*@example.com')
    thread = _make_thread(from_participant='alice@example.com')
    engine.add_responder('r', config.budget)

    result = await dispatcher.dispatch('r', thread, config)
    assert result.status == DispatchStatus.SUCCESS


# ---------------------------------------------------------------------------
# Requirement 2: subject_keywords matching (case-insensitive)
# ---------------------------------------------------------------------------


async def test_it_matches_a_thread_when_a_subject_keywords_entry_is_found_in_the_subject_case_insensitively(  # noqa: E501
    tmp_path,
):
    runner = FakeSubprocessRunner(stdout=b'ok', stderr=b'', returncode=0)
    engine = _make_engine(tmp_path)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine)

    config = _make_config(subject_keywords=['URGENT'])
    thread = _make_thread(subject='urgent: fix this now')
    engine.add_responder('r', config.budget)

    result = await dispatcher.dispatch('r', thread, config)
    assert result.status == DispatchStatus.SUCCESS


# ---------------------------------------------------------------------------
# Requirement 3: broadcaster skip
# ---------------------------------------------------------------------------


async def test_it_skips_a_thread_tagged_with_broadcaster_metadata_to_avoid_self_feedback_loops(
    tmp_path,
):
    runner = FakeSubprocessRunner(stdout=b'', stderr=b'', returncode=0)
    engine = _make_engine(tmp_path)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine)

    config = _make_config(from_pattern='*')
    thread = _make_thread(metadata={'broadcaster': True})
    engine.add_responder('r', config.budget)

    result = await dispatcher.dispatch('r', thread, config)
    assert result.status == DispatchStatus.SKIPPED


# ---------------------------------------------------------------------------
# Requirement 4: argv construction
# ---------------------------------------------------------------------------


async def test_it_builds_the_claude_invocation_argv_from_claude_invocation_cwd_model_extra_args(
    tmp_path,
):
    runner = FakeSubprocessRunner(stdout=b'', stderr=b'', returncode=0)
    engine = _make_engine(tmp_path)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine)

    config = _make_config(
        from_pattern='*',
        model='claude-opus-4-5',
        extra_args=['--max-tokens', '1000'],
        cwd='/projects/mybot',
    )
    thread = _make_thread()
    engine.add_responder('r', config.budget)

    await dispatcher.dispatch('r', thread, config)

    assert runner.last_argv == [
        'claude',
        '--print',
        '--model',
        'claude-opus-4-5',
        '--max-tokens',
        '1000',
    ]
    assert runner.last_cwd == '/projects/mybot'


# ---------------------------------------------------------------------------
# Requirement 5: stdin contains thread body
# ---------------------------------------------------------------------------


async def test_it_passes_the_thread_body_to_the_subprocess_on_stdin(tmp_path):
    runner = FakeSubprocessRunner(stdout=b'', stderr=b'', returncode=0)
    engine = _make_engine(tmp_path)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine)

    config = _make_config(from_pattern='*')
    thread = _make_thread(
        subject='My Subject',
        from_participant='bob@test.com',
        body='The actual body content',
    )
    engine.add_responder('r', config.budget)

    await dispatcher.dispatch('r', thread, config)

    stdin_text = runner.last_stdin_data.decode()
    assert 'Subject: My Subject' in stdin_text
    assert 'From: bob@test.com' in stdin_text
    assert 'The actual body content' in stdin_text


# ---------------------------------------------------------------------------
# Requirement 6: budget refused
# ---------------------------------------------------------------------------


async def test_it_refuses_dispatch_when_the_budget_engine_reports_the_responder_is_exhausted(
    tmp_path,
):
    runner = FakeSubprocessRunner(stdout=b'', stderr=b'', returncode=0)
    engine = _make_engine(tmp_path)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine)

    config = _make_config(from_pattern='*', max_invocations_per_hour=1)
    thread = _make_thread()
    engine.add_responder('r', config.budget)

    # exhaust the budget
    engine.record_dispatch('r')

    result = await dispatcher.dispatch('r', thread, config)
    assert result.status == DispatchStatus.REFUSED_BUDGET


# ---------------------------------------------------------------------------
# Requirement 7: record dispatch on success
# ---------------------------------------------------------------------------


async def test_it_records_the_dispatch_with_the_budget_engine_on_successful_spawn(tmp_path):
    runner = FakeSubprocessRunner(stdout=b'response', stderr=b'', returncode=0)
    engine = _make_engine(tmp_path)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine)

    config = _make_config(from_pattern='*', max_invocations_per_hour=5, max_invocations_per_day=10)
    thread = _make_thread()
    engine.add_responder('r', config.budget)

    snap_before = engine.snapshot()
    assert snap_before['r']['hour_count'] == 0

    await dispatcher.dispatch('r', thread, config)

    snap_after = engine.snapshot()
    assert snap_after['r']['hour_count'] == 1


# ---------------------------------------------------------------------------
# Requirement 8: retry once on transient failure
# ---------------------------------------------------------------------------


async def test_it_retries_once_on_a_transient_subprocess_failure_before_surfacing_the_error(
    tmp_path,
):
    # Fail first call, succeed second
    runner = FakeSubprocessRunner(
        stdout=b'ok', stderr=b'', returncode=0, fail_first_n=1
    )
    engine = _make_engine(tmp_path)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine)

    config = _make_config(from_pattern='*')
    thread = _make_thread()
    engine.add_responder('r', config.budget)

    result = await dispatcher.dispatch('r', thread, config)
    assert result.status == DispatchStatus.SUCCESS
    assert runner.call_count == 2


async def test_it_returns_failed_when_both_attempts_fail(tmp_path):
    runner = FakeSubprocessRunner(stdout=b'', stderr=b'error', returncode=1, fail_first_n=2)
    engine = _make_engine(tmp_path)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine)

    config = _make_config(from_pattern='*')
    thread = _make_thread()
    engine.add_responder('r', config.budget)

    result = await dispatcher.dispatch('r', thread, config)
    assert result.status == DispatchStatus.FAILED
    assert runner.call_count == 2


# ---------------------------------------------------------------------------
# Requirement 9: timeout
# ---------------------------------------------------------------------------


async def test_it_returns_a_DispatchResult_marked_timed_out_when_the_subprocess_exceeds_the_configured_timeout(  # noqa: E501
    tmp_path,
):
    runner = FakeSubprocessRunner(stdout=b'', stderr=b'', returncode=0, raise_timeout=True)
    engine = _make_engine(tmp_path)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine, default_timeout=0.1)

    config = _make_config(from_pattern='*')
    thread = _make_thread()
    engine.add_responder('r', config.budget)

    result = await dispatcher.dispatch('r', thread, config)
    assert result.status == DispatchStatus.TIMED_OUT
