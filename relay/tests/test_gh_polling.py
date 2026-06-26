"""Tests for pb_chatroom_relay.gh_polling — GH issue polling sub-role."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pb_chatroom_relay.config import GhPollingConfig
from pb_chatroom_relay.dispatcher import FakeSubprocessRunner
from pb_chatroom_relay.gh_polling import GhPoller
from pb_chatroom_relay.state import State


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    number: int,
    title: str = 'Fix the thing',
    labels: list[str] | None = None,
    created_at: str = '2026-06-26T00:00:00Z',
    url: str | None = None,
) -> dict:
    return {
        'number': number,
        'title': title,
        'labels': [{'name': lbl} for lbl in (labels or [])],
        'createdAt': created_at,
        'url': url or f'https://github.com/org/repo/issues/{number}',
    }


def _fake_runner_for(issues: list[dict], returncode: int = 0) -> FakeSubprocessRunner:
    stdout = json.dumps(issues).encode()
    stderr = b'' if returncode == 0 else b'gh: error: not found'
    return FakeSubprocessRunner(stdout=stdout, stderr=stderr, returncode=returncode)


def _make_poller(
    repos: list[str],
    eligible_label_filter: list[str] | None = None,
    min_age_minutes: int = 0,
    poll_interval_minutes: int = 5,
    runner: FakeSubprocessRunner | None = None,
    state: State | None = None,
    state_path: Path | None = None,
) -> GhPoller:
    cfg = GhPollingConfig(
        repos=repos,
        eligible_label_filter=eligible_label_filter or [],
        min_age_minutes=min_age_minutes,
        poll_interval_minutes=poll_interval_minutes,
    )
    s = state or State()
    return GhPoller(config=cfg, state=s, state_path=state_path, runner=runner)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_it_parses_gh_polling_config_block_with_repos_poll_interval_minutes_eligible_label_filter_and_min_age_minutes():  # noqa: E501
    cfg = GhPollingConfig(
        repos=['org/repo-a', 'org/repo-b'],
        poll_interval_minutes=10,
        eligible_label_filter=['good-first', 'help-wanted'],
        min_age_minutes=15,
    )
    assert cfg.repos == ['org/repo-a', 'org/repo-b']
    assert cfg.poll_interval_minutes == 10
    assert cfg.eligible_label_filter == ['good-first', 'help-wanted']
    assert cfg.min_age_minutes == 15


@pytest.mark.asyncio
async def test_it_polls_each_configured_repo_via_gh_issue_list_with_JSON_output():
    issues = [_make_issue(1, labels=['bug'])]
    runner = _fake_runner_for(issues)
    poller = _make_poller(repos=['org/repo-a', 'org/repo-b'], runner=runner)

    await poller.poll_once()

    # Two repos → two calls
    assert runner.call_count == 2
    # Last call argv must include gh issue list --repo ... --json
    assert 'gh' in runner.last_argv
    assert 'issue' in runner.last_argv
    assert 'list' in runner.last_argv
    assert '--json' in runner.last_argv


@pytest.mark.asyncio
async def test_it_yields_a_ticket_only_when_it_carries_at_least_one_eligible_label():
    issues = [
        _make_issue(1, labels=['bug']),            # not eligible
        _make_issue(2, labels=['good-first-issue']),  # eligible
        _make_issue(3, labels=['bug', 'help-wanted']),  # eligible
    ]
    runner = _fake_runner_for(issues)
    poller = _make_poller(
        repos=['org/repo'],
        eligible_label_filter=['good-first-issue', 'help-wanted'],
        runner=runner,
    )

    results = await poller.poll_once()

    numbers = [r['number'] for r in results]
    assert 1 not in numbers
    assert 2 in numbers
    assert 3 in numbers


@pytest.mark.asyncio
async def test_it_skips_tickets_younger_than_min_age_minutes():
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)
    old_ts = (now - timedelta(minutes=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    new_ts = (now - timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ')

    issues = [
        _make_issue(1, labels=['bug'], created_at=old_ts),   # old enough
        _make_issue(2, labels=['bug'], created_at=new_ts),   # too new
    ]
    runner = _fake_runner_for(issues)
    poller = _make_poller(
        repos=['org/repo'],
        min_age_minutes=10,
        runner=runner,
    )
    poller._now = lambda: now  # inject clock

    results = await poller.poll_once()

    numbers = [r['number'] for r in results]
    assert 1 in numbers
    assert 2 not in numbers


@pytest.mark.asyncio
async def test_it_does_not_yield_the_same_ticket_twice_across_consecutive_polls(
    tmp_path,
):
    issues = [_make_issue(1, labels=['bug']), _make_issue(2, labels=['bug'])]
    runner = _fake_runner_for(issues)
    state_path = tmp_path / 'state.json'
    state = State()
    poller = _make_poller(
        repos=['org/repo'],
        runner=runner,
        state=state,
        state_path=state_path,
    )

    first = await poller.poll_once()
    assert len(first) == 2

    second = await poller.poll_once()
    assert second == []


@pytest.mark.asyncio
async def test_it_advances_the_per_repo_cursor_in_state_file_after_each_poll(
    tmp_path,
):
    issues = [_make_issue(5, labels=['bug']), _make_issue(3, labels=['bug'])]
    runner = _fake_runner_for(issues)
    state_path = tmp_path / 'state.json'
    state = State()
    poller = _make_poller(
        repos=['org/repo'],
        runner=runner,
        state=state,
        state_path=state_path,
    )

    await poller.poll_once()

    saved = State.load(state_path)
    # Cursor must advance to max(number) = 5
    assert saved.gh_cursor.get('org/repo') == '5'


@pytest.mark.asyncio
async def test_it_tolerates_a_gh_subprocess_error_and_retries_on_the_next_tick():
    issues = [_make_issue(1, labels=['bug'])]
    runner = FakeSubprocessRunner(
        stdout=json.dumps(issues).encode(),
        stderr=b'',
        returncode=0,
        fail_first_n=1,  # first call fails, second succeeds
    )
    poller = _make_poller(repos=['org/repo'], runner=runner)

    # First poll — subprocess fails, should return empty (not raise)
    first = await poller.poll_once()
    assert first == []

    # Second poll — subprocess succeeds, should return tickets
    second = await poller.poll_once()
    assert len(second) == 1
