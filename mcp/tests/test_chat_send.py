"""Tests for MCP tool: chat_send."""

from __future__ import annotations

import httpx
import pytest


@pytest.fixture
def message_response() -> dict:
    return {
        'id': 'msg-1',
        'thread_id': 'thread-abc',
        'body': 'Hello',
        'participant_id': 'host',
        'created_at': '2026-06-26T00:00:00Z',
    }


@pytest.fixture
def success_transport(message_response) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=message_response)

    return httpx.MockTransport(handler)


class TrackingTransport(httpx.MockTransport):
    def __init__(self, handler):
        super().__init__(handler)
        self.call_count = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.call_count += 1
        return super().handle_request(request)


@pytest.fixture
def tracking_transport(message_response) -> TrackingTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=message_response)

    return TrackingTransport(handler)


async def test_it_posts_a_message_to_the_thread_and_returns_the_message_response(
    message_response,
    success_transport,
):
    from pb_chatroom_mcp.tools.chat_send import chat_send

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=success_transport,
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        result = await chat_send('thread-abc', 'Hello', client)
    assert result == message_response


async def test_it_rejects_an_empty_or_missing_thread_id_without_making_any_http_request(
    tracking_transport,
):
    from pb_chatroom_mcp.tools.chat_send import chat_send

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=tracking_transport,
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        result = await chat_send('', 'Hello', client)
    assert result == (
        'chat_send requires a thread_id'
        ' — root-thread creation is parent-only via /chat threads-open'
    )
    assert tracking_transport.call_count == 0


async def test_it_rejects_an_empty_or_missing_body(
    tracking_transport,
):
    from pb_chatroom_mcp.tools.chat_send import chat_send

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=tracking_transport,
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        result = await chat_send('thread-abc', '', client)
    assert result == 'body is required'
    assert tracking_transport.call_count == 0


async def test_it_returns_a_structured_error_for_404_responses_with_the_thread_id_surfaced():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={'detail': 'not found'})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=transport,
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        from pb_chatroom_mcp.tools.chat_send import chat_send

        result = await chat_send('thread-missing', 'Hello', client)
    assert result == 'thread thread-missing not found'


async def test_it_returns_a_structured_error_for_403_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={'detail': 'forbidden'})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=transport,
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        from pb_chatroom_mcp.tools.chat_send import chat_send

        result = await chat_send('thread-abc', 'Hello', client)
    assert result == 'not a participant of thread thread-abc'


def test_it_does_not_accept_any_participant_id_argument_identity_is_auto_stamped():
    import inspect

    from pb_chatroom_mcp.tools.chat_send import chat_send

    sig = inspect.signature(chat_send)
    param_names = list(sig.parameters.keys())
    assert 'participant_id' not in param_names
