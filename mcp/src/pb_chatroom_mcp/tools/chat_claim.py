"""MCP tool: chat_claim."""

from __future__ import annotations

import httpx


async def chat_claim(
    thread_id: str,
    scope: str,
    client: httpx.AsyncClient,
) -> dict | str:
    if not thread_id:
        return 'chat_claim requires a thread_id'
    if not scope:
        return 'scope is required'
    try:
        response = await client.post(
            f'/api/threads/{thread_id}/claim',
            json={'scope': scope},
        )
    except httpx.ConnectError:
        return f'server unreachable at {client.base_url}'
    if response.status_code == 404:
        return f'thread {thread_id} not found'
    if response.status_code == 409:
        detail = response.json().get('detail', {})
        existing = detail.get('claimed_by', 'unknown')
        return f'claim conflict: thread already claimed by {existing}'
    return response.json()
