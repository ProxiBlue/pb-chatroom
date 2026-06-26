"""Tests for peer_response graphiti-first helper and dispatcher integration."""

from __future__ import annotations

from datetime import UTC, datetime
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
# Fake GraphitiSearchClient
# ---------------------------------------------------------------------------

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


class FakeGraphitiSearchClient:
    def __init__(self, facts: list[dict]) -> None:
        self._facts = facts
        self.last_query: str = ''
        self.last_group_id: str = ''

    async def search_facts(self, query: str, group_id: str) -> list[dict]:
        self.last_query = query
        self.last_group_id = group_id
        return self._facts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_thread(
    subject: str = 'How should we design the caching layer?',
    from_participant: str = 'container-myapp',
    body: str = 'Body text',
    discussion_type: str | None = 'design_question',
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    t: dict[str, Any] = {
        'id': 'thread-1',
        'subject': subject,
        'from_participant': from_participant,
        'created_by': from_participant,
        'body': body,
        'metadata': metadata or {},
    }
    if discussion_type is not None:
        t['discussion_type'] = discussion_type
    return t


def _make_config(
    from_pattern: str = '*',
    model: str = 'claude-opus-4-5',
    cwd: str = '/tmp',
) -> ResponderConfig:
    return ResponderConfig(
        trigger=TriggerConfig(from_pattern=from_pattern, subject_keywords=[]),
        claude_invocation=ClaudeInvocationConfig(
            cwd=cwd,
            model=model,
            extra_args=[],
            system_prompt_addendum='',
        ),
        budget=BudgetConfig(max_invocations_per_hour=0, max_invocations_per_day=0),
    )


def _make_engine(tmp_path: Path) -> BudgetEngine:
    state_path = tmp_path / 'state.json'
    state = State.load(state_path)
    clock = FakeClock(_T0)
    return BudgetEngine(state=state, clock=clock, state_path=state_path)


# ---------------------------------------------------------------------------
# Requirement 1: it short-circuits a design_question thread when graphiti returns relevant facts
# ---------------------------------------------------------------------------


async def test_it_short_circuits_a_design_question_thread_when_graphiti_returns_relevant_facts(
    tmp_path,
):
    relevant_fact = {'fact': 'Use Redis for session caching', 'score': 0.85}
    graphiti = FakeGraphitiSearchClient(facts=[relevant_fact])

    runner = FakeSubprocessRunner(stdout=b'claude reply', returncode=0)
    engine = _make_engine(tmp_path)
    config = _make_config()
    engine.add_responder('r', config.budget)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine, graphiti=graphiti)

    thread = _make_thread(discussion_type='design_question')
    result = await dispatcher.dispatch('r', thread, config)

    assert result.status == DispatchStatus.SUCCESS


# ---------------------------------------------------------------------------
# Requirement 2: it posts the graphiti excerpt verbatim with a confirmation line
# ---------------------------------------------------------------------------


async def test_it_posts_the_graphiti_excerpt_verbatim_with_a_confirmation_line(
    tmp_path,
):
    relevant_fact = {'fact': 'Use Redis for session caching', 'score': 0.85}
    graphiti = FakeGraphitiSearchClient(facts=[relevant_fact])

    runner = FakeSubprocessRunner(stdout=b'claude reply', returncode=0)
    engine = _make_engine(tmp_path)
    config = _make_config()
    engine.add_responder('r', config.budget)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine, graphiti=graphiti)

    thread = _make_thread(discussion_type='design_question')
    result = await dispatcher.dispatch('r', thread, config)

    stdout_text = result.stdout.decode()
    assert 'Use Redis for session caching' in stdout_text
    assert 'Graphiti found relevant experience:' in stdout_text


# ---------------------------------------------------------------------------
# Requirement 3: it does NOT spawn the subprocess when graphiti suffices
# ---------------------------------------------------------------------------


async def test_it_does_NOT_spawn_the_subprocess_when_graphiti_suffices(
    tmp_path,
):
    relevant_fact = {'fact': 'Use Redis for session caching', 'score': 0.85}
    graphiti = FakeGraphitiSearchClient(facts=[relevant_fact])

    runner = FakeSubprocessRunner(stdout=b'claude reply', returncode=0)
    engine = _make_engine(tmp_path)
    config = _make_config()
    engine.add_responder('r', config.budget)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine, graphiti=graphiti)

    thread = _make_thread(discussion_type='design_question')
    await dispatcher.dispatch('r', thread, config)

    assert runner.call_count == 0


# ---------------------------------------------------------------------------
# Requirement 4: it spawns the subprocess with graphiti excerpt prepended when results are thin
# ---------------------------------------------------------------------------


async def test_it_spawns_the_subprocess_with_graphiti_excerpt_prepended_when_results_are_thin(
    tmp_path,
):
    thin_fact = {'fact': 'Somewhat related info', 'score': 0.3}
    graphiti = FakeGraphitiSearchClient(facts=[thin_fact])

    runner = FakeSubprocessRunner(stdout=b'claude reply', returncode=0)
    engine = _make_engine(tmp_path)
    config = _make_config()
    engine.add_responder('r', config.budget)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine, graphiti=graphiti)

    thread = _make_thread(discussion_type='design_question')
    result = await dispatcher.dispatch('r', thread, config)

    assert runner.call_count >= 1
    assert result.status == DispatchStatus.SUCCESS


# ---------------------------------------------------------------------------
# Requirement 5: it falls through to v0.3.0 dispatch when discussion_type is null
# ---------------------------------------------------------------------------


async def test_it_falls_through_to_v0_3_0_dispatch_when_discussion_type_is_null(
    tmp_path,
):
    graphiti = FakeGraphitiSearchClient(facts=[{'fact': 'irrelevant', 'score': 0.9}])

    runner = FakeSubprocessRunner(stdout=b'claude reply', returncode=0)
    engine = _make_engine(tmp_path)
    config = _make_config()
    engine.add_responder('r', config.budget)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine, graphiti=graphiti)

    thread = _make_thread(discussion_type=None)
    result = await dispatcher.dispatch('r', thread, config)

    # subprocess must be called (normal dispatch)
    assert runner.call_count == 1
    assert result.status == DispatchStatus.SUCCESS


# ---------------------------------------------------------------------------
# Requirement 6: it falls through to v0.3.0 dispatch when discussion_type is claim_request
# ---------------------------------------------------------------------------


async def test_it_falls_through_to_v0_3_0_dispatch_when_discussion_type_is_claim_request(
    tmp_path,
):
    graphiti = FakeGraphitiSearchClient(facts=[{'fact': 'irrelevant', 'score': 0.9}])

    runner = FakeSubprocessRunner(stdout=b'claude reply', returncode=0)
    engine = _make_engine(tmp_path)
    config = _make_config()
    engine.add_responder('r', config.budget)
    dispatcher = ResponderDispatcher(runner=runner, budget_engine=engine, graphiti=graphiti)

    thread = _make_thread(discussion_type='claim_request')
    result = await dispatcher.dispatch('r', thread, config)

    # subprocess must be called (normal dispatch)
    assert runner.call_count == 1
    assert result.status == DispatchStatus.SUCCESS
