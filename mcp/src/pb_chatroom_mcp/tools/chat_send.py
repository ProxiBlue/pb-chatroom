"""MCP tool: chat_send — post a message to an existing thread."""

from __future__ import annotations

import httpx


async def chat_send(thread_id: str, body: str, client: httpx.AsyncClient) -> object:
    """Post a message to thread_id. thread_id is structurally required."""
    if not thread_id:
        return (
            'chat_send requires a thread_id'
            ' — root-thread creation is parent-only via /chat threads-open'
        )

    if not body:
        return 'body is required'

    try:
        response = await client.post(
            f'/api/threads/{thread_id}/messages',
            json={'body': body},
        )
    except httpx.ConnectError:
        return f'server unreachable at {client.base_url} — is pb-chatroom-server running?'

    if response.status_code == 404:
        return f'thread {thread_id} not found'

    if response.status_code == 403:
        return f'not a participant of thread {thread_id}'

    return response.json()
