"""Tests for Archiver — renders threads to markdown and dispatches to graphiti."""

from __future__ import annotations

from typing import Any

import pytest

from pb_chatroom_relay.archiver import Archiver, render_thread
from pb_chatroom_relay.config import ArchiverConfig
from pb_chatroom_relay.state import State


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


class FakeChatroomClient:
    """In-memory fake for ChatroomClient."""

    def __init__(
        self,
        threads: list[dict[str, Any]] | None = None,
        thread_detail: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._threads = threads or []
        self._thread_detail = thread_detail or {}

    async def list_threads(
        self, since: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        result = list(self._threads)
        if since is not None:
            result = [t for t in result if t.get('updated_at', '') > since]
        if status is not None:
            result = [t for t in result if t.get('status') == status]
        return result

    async def get_thread(self, thread_id: str) -> dict[str, Any]:
        return self._thread_detail[thread_id]


class FakeGraphitiClient:
    """Records add_memory calls; optionally raises on the nth call."""

    def __init__(self, raise_on_call: int | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._raise_on_call = raise_on_call

    async def add_memory(self, group_id: str, content: str, source_type: str) -> None:
        call_index = len(self.calls) + 1
        self.calls.append({'group_id': group_id, 'content': content, 'source_type': source_type})
        if self._raise_on_call is not None and call_index == self._raise_on_call:
            raise RuntimeError('graphiti dispatch failed')


def _make_thread(thread_id: str, subject: str, status: str = 'acked') -> dict[str, Any]:
    return {
        'id': thread_id,
        'subject': subject,
        'status': status,
        'updated_at': '2024-01-02T00:00:00Z',
        'from_participant': 'host',
    }


def _make_message(msg_id: str, from_p: str, body: str, created_at: str) -> dict[str, Any]:
    return {
        'id': msg_id,
        'from_participant': from_p,
        'body': body,
        'created_at': created_at,
    }


# ---------------------------------------------------------------------------
# Requirement 1: render_thread produces markdown with subject + chronological messages
# ---------------------------------------------------------------------------


def test_it_renders_thread_subject_and_messages_to_markdown_in_chronological_order():
    thread = _make_thread('t1', 'Hello World')
    messages = [
        _make_message('m2', 'bob', 'second', '2024-01-02T10:00:00Z'),
        _make_message('m1', 'alice', 'first', '2024-01-01T10:00:00Z'),
    ]
    result = render_thread(thread, messages)

    lines = result.split('\n')
    assert lines[0] == '# Hello World'
    # alice (earlier) must appear before bob (later)
    alice_idx = next(i for i, line in enumerate(lines) if 'alice' in line)
    bob_idx = next(i for i, line in enumerate(lines) if 'bob' in line)
    assert alice_idx < bob_idx
    assert 'first' in result
    assert 'second' in result


# ---------------------------------------------------------------------------
# Requirement 2: resolve_group_id literal key match beats wildcard
# ---------------------------------------------------------------------------


def test_it_resolves_group_id_with_a_literal_key_match_before_falling_back_to_wildcards():
    from pb_chatroom_relay.archiver import resolve_group_id

    group_id_map = {
        'host': 'literal-host',
        'host-*': 'wildcard-host',
    }
    result = resolve_group_id('host', group_id_map)
    assert result == 'literal-host'


# ---------------------------------------------------------------------------
# Requirement 3: strip container- prefix when wildcard matches container-*
# ---------------------------------------------------------------------------


def test_it_strips_the_container_prefix_when_group_id_map_matches_container_wildcard():
    from pb_chatroom_relay.archiver import resolve_group_id

    group_id_map = {
        'container-*': '<strip-container-prefix>',
    }
    result = resolve_group_id('container-pvcpipesupplies', group_id_map)
    assert result == 'pvcpipesupplies'


# ---------------------------------------------------------------------------
# Requirement 4: skip threads in exclude_test_subjects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_skips_threads_whose_subject_is_in_exclude_test_subjects(tmp_state_dir):
    config = ArchiverConfig(
        enabled=True,
        group_id_map={'host': 'mygroup'},
        max_thread_chars=10000,
        exclude_test_subjects=['[TEST]'],
    )
    excluded_thread = _make_thread('t1', '[TEST]')
    normal_thread = _make_thread('t2', 'Normal')
    normal_detail = {
        'id': 't2',
        'subject': 'Normal',
        'status': 'acked',
        'updated_at': '2024-01-02T00:00:00Z',
        'from_participant': 'host',
        'messages': [_make_message('m1', 'host', 'hi', '2024-01-02T10:00:00Z')],
    }

    chatroom = FakeChatroomClient(
        threads=[excluded_thread, normal_thread],
        thread_detail={'t2': normal_detail},
    )
    graphiti = FakeGraphitiClient()
    state = State()
    state_path = tmp_state_dir / 'state.json'

    archiver = Archiver(config=config, chatroom=chatroom, graphiti=graphiti)
    await archiver.archive_since(cursor=None, state=state, state_path=state_path)

    # Only Normal dispatched; [TEST] skipped
    assert len(graphiti.calls) == 1
    assert 'Normal' in graphiti.calls[0]['content']


# ---------------------------------------------------------------------------
# Requirement 5: truncate rendered body at max_thread_chars
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_truncates_rendered_body_at_max_thread_chars(tmp_state_dir):
    config = ArchiverConfig(
        enabled=True,
        group_id_map={'host': 'mygroup'},
        max_thread_chars=20,
        exclude_test_subjects=[],
    )
    thread = _make_thread('t1', 'Short')
    thread_detail = {
        'id': 't1',
        'subject': 'Short',
        'status': 'acked',
        'updated_at': '2024-01-02T00:00:00Z',
        'from_participant': 'host',
        'messages': [_make_message('m1', 'host', 'x' * 500, '2024-01-02T10:00:00Z')],
    }

    chatroom = FakeChatroomClient(
        threads=[thread],
        thread_detail={'t1': thread_detail},
    )
    graphiti = FakeGraphitiClient()
    state = State()
    state_path = tmp_state_dir / 'state.json'

    archiver = Archiver(config=config, chatroom=chatroom, graphiti=graphiti)
    await archiver.archive_since(cursor=None, state=state, state_path=state_path)

    assert len(graphiti.calls) == 1
    assert len(graphiti.calls[0]['content']) <= 20


# ---------------------------------------------------------------------------
# Requirement 6: advance cursor only after successful dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_advances_the_archive_cursor_only_after_a_successful_graphiti_dispatch(
    tmp_state_dir,
):
    config = ArchiverConfig(
        enabled=True,
        group_id_map={'host': 'mygroup'},
        max_thread_chars=10000,
        exclude_test_subjects=[],
    )
    thread = _make_thread('t1', 'Good thread')
    thread_detail = {
        'id': 't1',
        'subject': 'Good thread',
        'status': 'acked',
        'updated_at': '2024-01-02T00:00:00Z',
        'from_participant': 'host',
        'messages': [_make_message('m1', 'host', 'hello', '2024-01-02T10:00:00Z')],
    }

    chatroom = FakeChatroomClient(
        threads=[thread],
        thread_detail={'t1': thread_detail},
    )
    graphiti = FakeGraphitiClient()
    state = State()
    state_path = tmp_state_dir / 'state.json'

    archiver = Archiver(config=config, chatroom=chatroom, graphiti=graphiti)
    await archiver.archive_since(cursor=None, state=state, state_path=state_path)

    # Cursor must be advanced after success
    reloaded = State.load(state_path)
    assert reloaded.archive_cursor is not None
    assert reloaded.archive_cursor == thread['updated_at']


# ---------------------------------------------------------------------------
# Requirement 7: do not advance cursor when graphiti dispatch raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_does_not_advance_the_cursor_when_the_graphiti_dispatch_raises(tmp_state_dir):
    config = ArchiverConfig(
        enabled=True,
        group_id_map={'host': 'mygroup'},
        max_thread_chars=10000,
        exclude_test_subjects=[],
    )
    thread = _make_thread('t1', 'Bad thread')
    thread_detail = {
        'id': 't1',
        'subject': 'Bad thread',
        'status': 'acked',
        'updated_at': '2024-01-02T00:00:00Z',
        'from_participant': 'host',
        'messages': [_make_message('m1', 'host', 'hello', '2024-01-02T10:00:00Z')],
    }

    chatroom = FakeChatroomClient(
        threads=[thread],
        thread_detail={'t1': thread_detail},
    )
    graphiti = FakeGraphitiClient(raise_on_call=1)
    state = State()
    state_path = tmp_state_dir / 'state.json'

    archiver = Archiver(config=config, chatroom=chatroom, graphiti=graphiti)
    await archiver.archive_since(cursor=None, state=state, state_path=state_path)

    # Cursor must NOT be advanced on failed dispatch
    reloaded = State.load(state_path)
    assert reloaded.archive_cursor is None
