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
        to: Filter by recipient participant ID. When omitted (None), defaults to
            the caller's resolved identity — typical mode for "what's in my inbox?".
            Pass an empty string ('') to disable the filter entirely and list ALL
            open threads regardless of recipient — useful for cross-container
            observability and debugging.
        status: Optional status filter ('open' or 'acked').

    Returns:
        List of thread dicts, or a structured error string on failure.
    """
    if to is None:
        to = resolve_participant_id()

    params: dict[str, str] = {}
    if to:
        # Only attach the filter when 'to' is a non-empty string. Empty-string
        # means "no filter" — list ALL threads.
        params['to'] = to
    if status is not None:
        params['status'] = status

    try:
        response = await client.get('/api/threads', params=params)
    except httpx.ConnectError:
        return f'server unreachable at {client.base_url} — is pb-chatroom-server running?'

    if response.status_code < 200 or response.status_code >= 300:
        return f'server error {response.status_code}: {response.text}'

    return response.json()
