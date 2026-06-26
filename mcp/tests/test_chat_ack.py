"""Tests for MCP tool: chat_ack."""

from __future__ import annotations

import httpx
import pytest


@pytest.fixture
def ack_response() -> dict:
    return {
        'id': 'msg-2',
        'thread_id': 'thread-abc',
        'body': None,
        'participant_id': 'host',
        'created_at': '2026-06-26T00:00:00Z',
    }


@pytest.fixture
def success_transport(ack_response) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ack_response)

    return httpx.MockTransport(handler)


@pytest.fixture
def tracking_transport(ack_response):
    """Transport that tracks call count."""

    class TrackingTransport(httpx.MockTransport):
        def __init__(self, handler):
            super().__init__(handler)
            self.call_count = 0

        def handle_request(self, request: httpx.Request) -> httpx.Response:
            self.call_count += 1
            return super().handle_request(request)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ack_response)

    return TrackingTransport(handler)


async def test_it_posts_an_ack_to_the_thread_with_an_empty_body_when_none_is_supplied(
    ack_response,
    success_transport,
):
    from pb_chatroom_mcp.tools.chat_ack import chat_ack

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=success_transport,
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        result = await chat_ack('thread-abc', None, client)
    assert result == ack_response


async def test_it_posts_an_ack_with_the_supplied_body_when_given(
    ack_response,
    success_transport,
):
    from pb_chatroom_mcp.tools.chat_ack import chat_ack

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=success_transport,
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        result = await chat_ack('thread-abc', 'Acknowledged!', client)
    assert result == ack_response


async def test_it_rejects_an_empty_or_missing_thread_id_without_making_any_http_request(
    tracking_transport,
):
    from pb_chatroom_mcp.tools.chat_ack import chat_ack

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=tracking_transport,
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        result = await chat_ack('', None, client)
    assert result == 'chat_ack requires a thread_id'
    assert tracking_transport.call_count == 0


async def test_it_returns_a_structured_error_for_404_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={'detail': 'not found'})

    from pb_chatroom_mcp.tools.chat_ack import chat_ack

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=httpx.MockTransport(handler),
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        result = await chat_ack('thread-missing', None, client)
    assert result == 'thread thread-missing not found'


async def test_it_returns_a_structured_error_for_403_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={'detail': 'forbidden'})

    from pb_chatroom_mcp.tools.chat_ack import chat_ack

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=httpx.MockTransport(handler),
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        result = await chat_ack('thread-abc', None, client)
    assert result == 'not a participant of thread thread-abc'


async def test_it_returns_the_ack_message_row_from_the_server_response():
    ack_row = {
        'id': 'msg-99',
        'thread_id': 'thread-xyz',
        'body': 'Got it',
        'participant_id': 'agent-1',
        'created_at': '2026-06-26T12:00:00Z',
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ack_row)

    from pb_chatroom_mcp.tools.chat_ack import chat_ack

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=httpx.MockTransport(handler),
        headers={'X-PB-Chatroom-Participant': 'host'},
    ) as client:
        result = await chat_ack('thread-xyz', 'Got it', client)
    assert result == ack_row
