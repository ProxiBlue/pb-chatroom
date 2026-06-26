"""MCP tool: chat_read_thread — reads a thread with its messages from the REST API."""

from __future__ import annotations

import httpx


async def chat_read_thread(
    thread_id: str | None,
    client: httpx.AsyncClient,
) -> dict | str:
    """Fetch a thread and its messages via GET /api/threads/{thread_id}.

    Returns the ThreadWithMessages dict on success, or a structured error string.
    """
    if not thread_id:
        return 'thread_id is required'

    url = f'/api/threads/{thread_id}'
    try:
        response = await client.get(url)
    except httpx.ConnectError:
        base = str(client.base_url).rstrip('/')
        return f'server unreachable at {base} — is pb-chatroom-server running?'

    if response.status_code == 404:
        return f'thread {thread_id} not found'

    if response.status_code >= 300:
        return f'server error {response.status_code}: {response.text}'

    return response.json()
