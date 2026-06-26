"""MCP tool: chat_ack."""

from __future__ import annotations

import httpx


async def chat_ack(
    thread_id: str,
    body: str | None,
    client: httpx.AsyncClient,
) -> dict | str:
    if not thread_id:
        return 'chat_ack requires a thread_id'

    payload: dict = {} if body is None else {'body': body}
    url = f'/api/threads/{thread_id}/ack'
    try:
        response = await client.post(url, json=payload)
    except httpx.ConnectError:
        base = str(client.base_url).rstrip('/')
        return f'server unreachable at {base} — is pb-chatroom-server running?'

    if response.status_code == 404:
        return f'thread {thread_id} not found'

    if response.status_code == 403:
        return f'not a participant of thread {thread_id}'

    return response.json()
