"""Graphiti-first peer-response helper for design_question threads."""

from __future__ import annotations

from typing import Protocol


class GraphitiSearchClient(Protocol):
    async def search_facts(self, query: str, group_id: str) -> list[dict]: ...


async def graphiti_first_reply(
    topic: str,
    participant: str,
    graphiti: GraphitiSearchClient,
    relevance_threshold: float = 0.6,
) -> str | None:
    """Return excerpt string if facts above threshold, else None."""
    try:
        from .identity import derive_group_id

        group_id = derive_group_id(participant)
        facts = await graphiti.search_facts(query=topic, group_id=group_id)
        if facts:
            best = max(facts, key=lambda f: f.get('score', 0))
            if best.get('score', 0) >= relevance_threshold:
                excerpt = best.get('fact', '') or str(best)
                return f'Graphiti found relevant experience:\n\n{excerpt}'
    except Exception:
        pass
    return None
