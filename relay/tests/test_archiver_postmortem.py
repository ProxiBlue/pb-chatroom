"""Tests for Archiver postmortem mode (task 016)."""

from __future__ import annotations

from typing import Any

import pytest

from pb_chatroom_relay.archiver import Archiver, render_thread
from pb_chatroom_relay.config import ArchiverConfig
from pb_chatroom_relay.state import State


# ---------------------------------------------------------------------------
# Shared fakes (reuse pattern from test_archiver.py)
# ---------------------------------------------------------------------------


class FakeChatroomClient:
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
    def __init__(self, raise_on_call: int | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._raise_on_call = raise_on_call

    async def add_memory(self, group_id: str, content: str, source_type: str) -> None:
        call_index = len(self.calls) + 1
        self.calls.append({'group_id': group_id, 'content': content, 'source_type': source_type})
        if self._raise_on_call is not None and call_index == self._raise_on_call:
            raise RuntimeError('graphiti dispatch failed')


def _make_thread(
    thread_id: str,
    subject: str,
    status: str = 'acked',
    discussion_type: str = 'free-form',
) -> dict[str, Any]:
    return {
        'id': thread_id,
        'subject': subject,
        'status': status,
        'updated_at': '2024-01-02T00:00:00Z',
        'from_participant': 'host',
        'discussion_type': discussion_type,
    }


def _make_message(msg_id: str, from_p: str, body: str, created_at: str) -> dict[str, Any]:
    return {
        'id': msg_id,
        'from_participant': from_p,
        'body': body,
        'created_at': created_at,
    }


# ---------------------------------------------------------------------------
# Requirement 1: double max_thread_chars for postmortem
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_uses_double_max_thread_chars_when_discussion_type_is_postmortem(tmp_state_dir):
    config = ArchiverConfig(
        enabled=True,
        group_id_map={'host': 'mygroup'},
        max_thread_chars=100,
        exclude_test_subjects=[],
    )
    thread = _make_thread('t1', 'Incident Review', discussion_type='postmortem')
    # Body is 300 chars — exceeds 100 but within 200 (double)
    long_body = 'x' * 300
    thread_detail = {
        **thread,
        'messages': [_make_message('m1', 'host', long_body, '2024-01-02T10:00:00Z')],
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
    # Must be truncated at double limit (200), not single limit (100)
    content = graphiti.calls[0]['content']
    assert len(content) <= 200
    assert len(content) > 100


# ---------------------------------------------------------------------------
# Requirement 2: Summary section from first 500 chars of first message
# ---------------------------------------------------------------------------


def test_it_prepends_a_Summary_section_taken_from_the_first_500_chars_of_the_first_message():
    thread = _make_thread('t1', 'Outage 2024-01', discussion_type='postmortem')
    first_body = 'A' * 600  # longer than 500
    messages = [
        _make_message('m1', 'alice', first_body, '2024-01-01T10:00:00Z'),
        _make_message('m2', 'bob', 'follow-up', '2024-01-02T10:00:00Z'),
    ]
    result = render_thread(thread, messages, mode='postmortem')

    assert '## Summary' in result
    # Summary must be exactly the first 500 chars (stripped)
    expected_summary = first_body[:500].strip()
    assert expected_summary in result
    # Full 600-char body must NOT appear verbatim in the summary section
    assert first_body not in result.split('## Full Thread')[0]


# ---------------------------------------------------------------------------
# Requirement 3: chronological message ordering in the body section
# ---------------------------------------------------------------------------


def test_it_preserves_the_chronological_message_ordering_in_the_body_section():
    thread = _make_thread('t1', 'Post-Incident', discussion_type='postmortem')
    messages = [
        _make_message('m3', 'charlie', 'third', '2024-01-03T10:00:00Z'),
        _make_message('m1', 'alice', 'first', '2024-01-01T10:00:00Z'),
        _make_message('m2', 'bob', 'second', '2024-01-02T10:00:00Z'),
    ]
    result = render_thread(thread, messages, mode='postmortem')

    full_thread_part = result.split('## Full Thread')[1]
    alice_idx = full_thread_part.index('alice')
    bob_idx = full_thread_part.index('bob')
    charlie_idx = full_thread_part.index('charlie')
    assert alice_idx < bob_idx < charlie_idx


# ---------------------------------------------------------------------------
# Requirement 4: default render_thread unchanged for free-form threads
# ---------------------------------------------------------------------------


def test_it_leaves_render_thread_default_behavior_unchanged_for_free_form_threads():
    thread = _make_thread('t1', 'Hello World', discussion_type='free-form')
    messages = [
        _make_message('m2', 'bob', 'second', '2024-01-02T10:00:00Z'),
        _make_message('m1', 'alice', 'first', '2024-01-01T10:00:00Z'),
    ]
    result = render_thread(thread, messages)

    lines = result.split('\n')
    assert lines[0] == '# Hello World'
    assert '## Summary' not in result
    assert '## Full Thread' not in result
    alice_idx = next(i for i, line in enumerate(lines) if 'alice' in line)
    bob_idx = next(i for i, line in enumerate(lines) if 'bob' in line)
    assert alice_idx < bob_idx


# ---------------------------------------------------------------------------
# Requirement 5: cursor advances after successful postmortem dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_advances_the_archive_cursor_after_a_successful_postmortem_dispatch_same_as_v030(
    tmp_state_dir,
):
    config = ArchiverConfig(
        enabled=True,
        group_id_map={'host': 'mygroup'},
        max_thread_chars=10000,
        exclude_test_subjects=[],
    )
    thread = _make_thread('t1', 'Big Outage', discussion_type='postmortem')
    thread_detail = {
        **thread,
        'messages': [_make_message('m1', 'host', 'details here', '2024-01-02T10:00:00Z')],
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

    reloaded = State.load(state_path)
    assert reloaded.archive_cursor is not None
    assert reloaded.archive_cursor == thread['updated_at']
