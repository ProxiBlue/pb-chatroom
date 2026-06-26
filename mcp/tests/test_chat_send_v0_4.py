"""Tests for MCP tool: chat_send v0.4 — discussion_type pass-through."""

from __future__ import annotations

import json

import httpx
import pytest


@pytest.fixture
def message_response() -> dict:
    return {
        'id': 'msg-42',
        'thread_id': 'thread-xyz',
        'body': 'Reply text',
        'participant_id': 'host',
        'created_at': '2026-06-26T00:00:00Z',
    }


def _make_client(handler, base_url: str = 'http://127.0.0.1:7476') -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        transport=httpx.MockTransport(handler),
        headers={'X-PB-Chatroom-Participant': 'host'},
    )


async def test_it_posts_a_message_with_no_discussion_type_for_back_compat(message_response):
    """Back-compat: no discussion_type → request body only has 'body'."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=message_response)

    from pb_chatroom_mcp.tools.chat_send import chat_send

    async with _make_client(handler) as client:
        result = await chat_send(thread_id='thread-xyz', body='Reply text', client=client)

    assert result == message_response
    assert len(captured) == 1
    payload = json.loads(captured[0].content)
    assert payload == {'body': 'Reply text'}
    assert 'discussion_type' not in payload


async def test_it_forwards_discussion_type_to_the_rest_api_when_provided(message_response):
    """When discussion_type given, it appears in the POST payload."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=message_response)

    from pb_chatroom_mcp.tools.chat_send import chat_send

    async with _make_client(handler) as client:
        result = await chat_send(
            thread_id='thread-xyz',
            body='Reply text',
            client=client,
            discussion_type='debate',
        )

    assert result == message_response
    payload = json.loads(captured[0].content)
    assert payload == {'body': 'Reply text', 'discussion_type': 'debate'}


async def test_it_rejects_discussion_type_values_not_in_the_allowed_enum_at_the_mcp_boundary():
    """Invalid discussion_type returns error string without making HTTP request."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={})

    from pb_chatroom_mcp.tools.chat_send import chat_send

    async with _make_client(handler) as client:
        result = await chat_send(
            thread_id='thread-xyz',
            body='Reply text',
            client=client,
            discussion_type='invalid_type',
        )

    assert result == "invalid discussion_type: 'invalid_type'"
    assert call_count == 0


async def test_it_returns_the_created_message_id_on_success(message_response):
    """Result dict contains 'id' field from REST response."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=message_response)

    from pb_chatroom_mcp.tools.chat_send import chat_send

    async with _make_client(handler) as client:
        result = await chat_send(
            thread_id='thread-xyz',
            body='Reply text',
            client=client,
            discussion_type='claim_request',
        )

    assert isinstance(result, dict)
    assert result['id'] == 'msg-42'
