"""MCP tool: chat_ask_peer — graphiti-first design question."""

from __future__ import annotations

from typing import Protocol

import httpx


class GraphitiSearchClient(Protocol):
    async def search_facts(self, query: str, group_id: str) -> list[dict]: ...


def _derive_group_id(participant: str) -> str:
    """Strip container- prefix; host-* → host."""
    if participant.startswith('container-'):
        name = participant[len('container-') :]
        if name.endswith('-auto'):
            name = name[: -len('-auto')]
        return name
    if participant.startswith('host'):
        return 'host'
    return participant


async def chat_ask_peer(
    topic: str,
    target_participant: str,
    body: str,
    chatroom_client: httpx.AsyncClient,
    graphiti_client: GraphitiSearchClient,
    relevance_threshold: float = 0.6,
    caller_participant: str = 'host',
) -> object:
    group_id = _derive_group_id(target_participant)

    # Graphiti-first
    try:
        facts = await graphiti_client.search_facts(query=topic, group_id=group_id)
        if facts:
            best = max(facts, key=lambda f: f.get('score', 0))
            if best.get('score', 0) >= relevance_threshold:
                return {'source': 'graphiti', 'facts': facts}
    except Exception:
        pass  # fail-open

    # Fall through: post design_question thread
    try:
        response = await chatroom_client.post(
            '/api/threads',
            json={
                'to': target_participant,
                'subject': f'Design question: {topic}',
                'body': body,
                'discussion_type': 'design_question',
            },
        )
        return response.json()
    except httpx.ConnectError:
        return f'server unreachable at {chatroom_client.base_url}'
