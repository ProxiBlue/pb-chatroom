"""Tests for the chat_list_threads MCP tool."""

from __future__ import annotations

import httpx
import pytest

from pb_chatroom_mcp.tools.list_threads import chat_list_threads

THREADS_FIXTURE = [
    {
        'id': 'thread-1',
        'subject': 'Hello',
        'created_by': 'host',
        'status': 'open',
        'created_at': '2026-01-01T00:00:00Z',
        'last_message_at': '2026-01-01T00:01:00Z',
    }
]


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url='http://test-server',
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_it_lists_threads_via_the_rest_api():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == '/api/threads'
        return httpx.Response(200, json=THREADS_FIXTURE)

    client = make_client(handler)
    result = await chat_list_threads(client=client, to='host')
    assert result == THREADS_FIXTURE


@pytest.mark.asyncio
async def test_it_defaults_the_to_filter_to_the_resolved_participant_id_when_no_arg_is_given(
    monkeypatch,
):
    monkeypatch.setenv('PB_CHATROOM_PARTICIPANT_ID', 'test-agent')

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured['url'] = str(request.url)
        return httpx.Response(200, json=THREADS_FIXTURE)

    client = make_client(handler)
    await chat_list_threads(client=client)
    assert 'to=test-agent' in captured['url']


@pytest.mark.asyncio
async def test_it_forwards_an_explicit_to_argument_to_the_query_string():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured['url'] = str(request.url)
        return httpx.Response(200, json=THREADS_FIXTURE)

    client = make_client(handler)
    await chat_list_threads(client=client, to='alice')
    assert 'to=alice' in captured['url']


@pytest.mark.asyncio
async def test_it_omits_the_to_filter_when_caller_passes_empty_string():
    """Passing to='' opts OUT of the per-participant filter — list ALL threads
    regardless of recipient. Useful for cross-container observability and the
    external executor's queue sweep. Default behaviour (to=None → caller identity)
    must NOT regress.
    """
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured['url'] = str(request.url)
        return httpx.Response(200, json=THREADS_FIXTURE)

    client = make_client(handler)
    await chat_list_threads(client=client, to='')
    # No 'to=' filter must be present in the query — empty string opted out.
    assert 'to=' not in captured['url']


@pytest.mark.asyncio
async def test_it_forwards_an_explicit_status_argument_to_the_query_string():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured['url'] = str(request.url)
        return httpx.Response(200, json=THREADS_FIXTURE)

    client = make_client(handler)
    await chat_list_threads(client=client, to='host', status='open')
    assert 'status=open' in captured['url']


@pytest.mark.asyncio
async def test_it_returns_a_structured_error_when_the_server_is_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('refused')

    client = make_client(handler)
    result = await chat_list_threads(client=client, to='host')
    assert isinstance(result, str)
    assert 'server unreachable at' in result
    assert 'pb-chatroom-server' in result


@pytest.mark.asyncio
async def test_it_returns_a_structured_error_on_non_2xx_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text='internal error')

    client = make_client(handler)
    result = await chat_list_threads(client=client, to='host')
    assert isinstance(result, str)
    assert 'server error 500' in result
    assert 'internal error' in result
