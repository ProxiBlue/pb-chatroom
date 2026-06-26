"""Tests for MCP tool: chat_claim."""

from __future__ import annotations

import httpx

CLAIM_PAYLOAD = {
    'claimed_by': 'agent-1',
    'claimed_at': '2026-06-26T00:00:00Z',
    'claim_scope': 'investigate the auth bug',
}


async def test_it_claims_an_unclaimed_thread_and_returns_the_claim_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CLAIM_PAYLOAD)

    from pb_chatroom_mcp.tools.chat_claim import chat_claim

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=httpx.MockTransport(handler),
        headers={'X-PB-Chatroom-Participant': 'agent-1'},
    ) as client:
        result = await chat_claim('thread-abc', 'investigate the auth bug', client)
    assert result == CLAIM_PAYLOAD


async def test_it_returns_the_claim_payload_on_idempotent_retry_by_the_same_agent():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CLAIM_PAYLOAD)

    from pb_chatroom_mcp.tools.chat_claim import chat_claim

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=httpx.MockTransport(handler),
        headers={'X-PB-Chatroom-Participant': 'agent-1'},
    ) as client:
        result = await chat_claim('thread-abc', 'investigate the auth bug', client)
    assert result == CLAIM_PAYLOAD


async def test_it_raises_a_tool_error_including_the_existing_claimer_when_409_received():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={'detail': {'claimed_by': 'agent-2'}})

    from pb_chatroom_mcp.tools.chat_claim import chat_claim

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=httpx.MockTransport(handler),
        headers={'X-PB-Chatroom-Participant': 'agent-1'},
    ) as client:
        result = await chat_claim('thread-abc', 'my scope', client)
    assert result == 'claim conflict: thread already claimed by agent-2'


async def test_it_requires_thread_id_and_scope_arguments():
    class TrackingTransport(httpx.MockTransport):
        def __init__(self, handler):
            super().__init__(handler)
            self.call_count = 0

        def handle_request(self, request: httpx.Request) -> httpx.Response:
            self.call_count += 1
            return super().handle_request(request)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CLAIM_PAYLOAD)

    transport = TrackingTransport(handler)

    from pb_chatroom_mcp.tools.chat_claim import chat_claim

    async with httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=transport,
        headers={'X-PB-Chatroom-Participant': 'agent-1'},
    ) as client:
        result_no_thread = await chat_claim('', 'some scope', client)
        result_no_scope = await chat_claim('thread-abc', '', client)

    assert result_no_thread == 'chat_claim requires a thread_id'
    assert result_no_scope == 'scope is required'
    assert transport.call_count == 0


async def test_it_is_included_in_the_mcp_server_tool_list():
    from mcp.types import ListToolsRequest

    from pb_chatroom_mcp.server import build_mcp_server

    server = build_mcp_server()
    handler = server.request_handlers[ListToolsRequest]
    result = await handler(ListToolsRequest(method='tools/list', params=None))
    tool_names = [tool.name for tool in result.root.tools]
    assert 'chat_claim' in tool_names
