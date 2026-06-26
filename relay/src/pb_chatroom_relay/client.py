"""Async HTTP client wrapping the pb-chatroom REST API."""

from __future__ import annotations

from typing import Any

import httpx


class ChatroomClient:
    """Async wrapper around the chatroom REST endpoints.

    Constructed once with a base_url + participant_id; all methods reuse the
    same underlying httpx.AsyncClient and inject the X-PB-Chatroom-Participant
    header on every request.
    """

    def __init__(
        self,
        base_url: str,
        participant_id: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._participant_id = participant_id
        headers = {
            'X-PB-Chatroom-Participant': participant_id,
            'Content-Type': 'application/json',
        }
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(10.0),
            transport=transport,
        )

    # ------------------------------------------------------------------
    # Thread listing
    # ------------------------------------------------------------------

    async def list_threads(
        self, since: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all threads, optionally filtered by *since* and/or *status*."""
        params: dict[str, str] = {}
        if since is not None:
            params['updated_after'] = since
        if status is not None:
            params['status'] = status
        response = await self._client.get('/api/threads', params=params)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Thread detail
    # ------------------------------------------------------------------

    async def get_thread(self, thread_id: str) -> dict[str, Any]:
        """Return a thread and its messages."""
        response = await self._client.get(f'/api/threads/{thread_id}')
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Posting
    # ------------------------------------------------------------------

    async def post_message(self, thread_id: str, body: str) -> str:
        """Post a reply message to *thread_id*; return the created message id."""
        response = await self._client.post(
            f'/api/threads/{thread_id}/messages',
            json={'body': body},
        )
        response.raise_for_status()
        return response.json()['id']

    async def ack_thread(self, thread_id: str, body: str | None = None) -> dict[str, Any]:
        """Acknowledge *thread_id*; return the updated thread."""
        payload: dict[str, Any] = {}
        if body is not None:
            payload['body'] = body
        response = await self._client.post(
            f'/api/threads/{thread_id}/ack',
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def create_root_thread(
        self,
        subject: str,
        body: str,
        to_participant: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a root thread; return the created thread."""
        payload: dict[str, Any] = {
            'subject': subject,
            'body': body,
            'to_participant': to_participant,
        }
        if metadata is not None:
            payload['metadata'] = metadata
        response = await self._client.post('/api/threads', json=payload)
        response.raise_for_status()
        return response.json()
