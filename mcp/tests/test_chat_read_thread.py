"""Tests for MCP tool: chat_read_thread."""

from __future__ import annotations

import httpx
import pytest


THREAD_WITH_MESSAGES = {
    'id': 'thread-abc',
    'title': 'Hello world',
    'created_by': 'host',
    'created_at': '2026-06-26T00:00:00Z',
    'messages': [
        {
            'id': 'msg-1',
            'thread_id': 'thread-abc',
            'content': 'First message',
            'created_by': 'host',
            'created_at': '2026-06-26T00:01:00Z',
        },
        {
            'id': 'msg-2',
            'thread_id': 'thread-abc',
            'content': 'Second message',
            'created_by': 'agent-a',
            'created_at': '2026-06-26T00:02:00Z',
        },
    ],
}


def _make_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_it_fetches_a_thread_with_messages_via_the_rest_api():
    from pb_chatroom_mcp.tools.chat_read_thread import chat_read_thread

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == '/api/threads/thread-abc'
        return httpx.Response(200, json=THREAD_WITH_MESSAGES)

    client = httpx.AsyncClient(
        base_url='http://test',
        transport=_make_transport(handler),
    )
    result = await chat_read_thread('thread-abc', client)
    assert result == THREAD_WITH_MESSAGES


@pytest.mark.asyncio
async def test_it_returns_a_structured_error_when_thread_id_is_missing_or_empty():
    from pb_chatroom_mcp.tools.chat_read_thread import chat_read_thread

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError('should not be called')

    client = httpx.AsyncClient(
        base_url='http://test',
        transport=_make_transport(handler),
    )
    result_empty = await chat_read_thread('', client)
    assert result_empty == 'thread_id is required'

    result_none = await chat_read_thread(None, client)  # type: ignore[arg-type]
    assert result_none == 'thread_id is required'


@pytest.mark.asyncio
async def test_it_returns_a_structured_error_for_404_responses():
    from pb_chatroom_mcp.tools.chat_read_thread import chat_read_thread

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text='Not Found')

    client = httpx.AsyncClient(
        base_url='http://test',
        transport=_make_transport(handler),
    )
    result = await chat_read_thread('missing-thread', client)
    assert result == 'thread missing-thread not found'


@pytest.mark.asyncio
async def test_it_returns_a_structured_error_when_the_server_is_unreachable():
    from pb_chatroom_mcp.tools.chat_read_thread import chat_read_thread

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('connection refused')

    client = httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=_make_transport(handler),
    )
    result = await chat_read_thread('thread-abc', client)
    assert result == 'server unreachable at http://127.0.0.1:7476 — is pb-chatroom-server running?'


@pytest.mark.asyncio
async def test_it_preserves_message_ordering_from_the_server_response():
    from pb_chatroom_mcp.tools.chat_read_thread import chat_read_thread

    messages = [
        {'id': f'msg-{i}', 'content': f'Message {i}', 'created_at': f'2026-06-26T00:0{i}:00Z'}
        for i in range(5)
    ]
    payload = {**THREAD_WITH_MESSAGES, 'messages': messages}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(
        base_url='http://test',
        transport=_make_transport(handler),
    )
    result = await chat_read_thread('thread-abc', client)
    assert isinstance(result, dict)
    assert result['messages'] == messages
