"""MCP tool: chat_list_threads."""

from __future__ import annotations

import httpx

from pb_chatroom_mcp.identity import resolve_participant_id


async def chat_list_threads(
    *,
    client: httpx.AsyncClient,
    to: str | None = None,
    status: str | None = None,
) -> list[dict] | str:
    """List threads via GET /api/threads.

    Args:
        client: Shared httpx async client pointed at the chatroom server.
        to: Filter by recipient participant ID. Defaults to the caller's resolved identity.
        status: Optional status filter ('open' or 'acked').

    Returns:
        List of thread dicts, or a structured error string on failure.
    """
    if to is None:
        to = resolve_participant_id()

    params: dict[str, str] = {'to': to}
    if status is not None:
        params['status'] = status

    try:
        response = await client.get('/api/threads', params=params)
    except httpx.ConnectError:
        return f'server unreachable at {client.base_url} — is pb-chatroom-server running?'

    if response.status_code < 200 or response.status_code >= 300:
        return f'server error {response.status_code}: {response.text}'

    return response.json()
