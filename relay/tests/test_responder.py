"""Tests for ResponderReplyPoster."""

from __future__ import annotations

import pytest

from pb_chatroom_relay.dispatcher import DispatchResult, DispatchStatus
from pb_chatroom_relay.responder import ResponderReplyPoster


# ---------------------------------------------------------------------------
# Stub ChatroomClient
# ---------------------------------------------------------------------------


class StubChatroomClient:
    def __init__(self) -> None:
        self.post_message_calls: list[tuple[str, str]] = []
        self.ack_thread_calls: list[tuple[str, str | None]] = []

    async def post_message(
        self, thread_id: str, body: str, discussion_type: str | None = None
    ) -> str:
        self.post_message_calls.append((thread_id, body))
        return 'msg-id'

    async def ack_thread(self, thread_id: str, body: str | None = None) -> dict:
        self.ack_thread_calls.append((thread_id, body))
        return {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_posts_a_regular_message_reply_when_the_dispatch_stdout_has_no_DONE_marker():
    client = StubChatroomClient()
    poster = ResponderReplyPoster(client)
    result = DispatchResult(
        status=DispatchStatus.SUCCESS,
        stdout=b'Hello, this is a reply.\nNo done marker here.',
    )
    await poster.post('thread-1', result)
    assert client.post_message_calls == [
        ('thread-1', 'Hello, this is a reply.\nNo done marker here.')
    ]
    assert client.ack_thread_calls == []


@pytest.mark.asyncio
async def test_it_acks_the_thread_when_the_dispatch_stdout_ends_with_a_DONE_marker_line():
    client = StubChatroomClient()
    poster = ResponderReplyPoster(client)
    result = DispatchResult(
        status=DispatchStatus.SUCCESS,
        stdout=b'Work complete.\nDONE',
    )
    await poster.post('thread-2', result)
    assert client.ack_thread_calls == [('thread-2', 'Work complete.')]
    assert client.post_message_calls == []


@pytest.mark.asyncio
async def test_it_strips_the_DONE_marker_from_the_body_before_sending():
    client = StubChatroomClient()
    poster = ResponderReplyPoster(client)
    result = DispatchResult(
        status=DispatchStatus.SUCCESS,
        stdout=b'Line one.\nLine two.\nDONE\n',
    )
    await poster.post('thread-3', result)
    assert client.ack_thread_calls == [('thread-3', 'Line one.\nLine two.')]
    assert client.post_message_calls == []


@pytest.mark.asyncio
async def test_it_posts_an_error_reply_when_the_dispatch_result_is_timed_out():
    client = StubChatroomClient()
    poster = ResponderReplyPoster(client)
    result = DispatchResult(status=DispatchStatus.TIMED_OUT)
    await poster.post('thread-4', result)
    assert len(client.post_message_calls) == 1
    thread_id, body = client.post_message_calls[0]
    assert thread_id == 'thread-4'
    assert '[relay]' in body
    assert 'timeout' in body.lower() or 'timed out' in body.lower()
    assert client.ack_thread_calls == []


@pytest.mark.asyncio
async def test_it_posts_an_error_reply_when_the_dispatch_result_has_a_non_zero_return_code():
    client = StubChatroomClient()
    poster = ResponderReplyPoster(client)
    result = DispatchResult(status=DispatchStatus.FAILED, returncode=2)
    await poster.post('thread-5', result)
    assert len(client.post_message_calls) == 1
    thread_id, body = client.post_message_calls[0]
    assert thread_id == 'thread-5'
    assert '[relay]' in body
    assert '2' in body
    assert client.ack_thread_calls == []


@pytest.mark.asyncio
async def test_it_does_nothing_when_the_dispatch_result_is_refused_by_budget():
    client = StubChatroomClient()
    poster = ResponderReplyPoster(client)
    result = DispatchResult(status=DispatchStatus.REFUSED_BUDGET)
    await poster.post('thread-6', result)
    assert client.post_message_calls == []
    assert client.ack_thread_calls == []
