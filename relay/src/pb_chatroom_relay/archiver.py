"""Archiver — fetches acked threads, renders to markdown, dispatches to graphiti."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, Protocol

from pb_chatroom_relay.config import ArchiverConfig
from pb_chatroom_relay.state import State


# ---------------------------------------------------------------------------
# GraphitiClient protocol
# ---------------------------------------------------------------------------


class GraphitiClient(Protocol):
    async def add_memory(self, group_id: str, content: str, source_type: str) -> None: ...


# ---------------------------------------------------------------------------
# Pure rendering helper
# ---------------------------------------------------------------------------


def render_thread(thread: dict[str, Any], messages: list[dict[str, Any]]) -> str:
    """Return markdown: subject header + chronological messages."""
    lines = [f"# {thread['subject']}", '']
    for msg in sorted(messages, key=lambda m: m['created_at']):
        lines.append(f"**{msg['from_participant']}** ({msg['created_at']}):")
        lines.append(msg['body'])
        lines.append('')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# group_id resolution
# ---------------------------------------------------------------------------

_STRIP_CONTAINER_SENTINEL = '<strip-container-prefix>'
_CONTAINER_PREFIX = 'container-'


def resolve_group_id(participant: str, group_id_map: dict[str, str]) -> str:
    """Resolve a group_id for *participant* from *group_id_map*.

    Resolution order:
    1. Exact literal match.
    2. fnmatch wildcard match (first wins).

    For the sentinel value ``<strip-container-prefix>``, strip the
    ``container-`` prefix from *participant*.
    """
    # 1. Exact literal
    if participant in group_id_map:
        value = group_id_map[participant]
        return _apply_sentinel(participant, value)

    # 2. Wildcard
    for pattern, value in group_id_map.items():
        if fnmatch.fnmatch(participant, pattern):
            return _apply_sentinel(participant, value)

    return participant


def _apply_sentinel(participant: str, value: str) -> str:
    if value == _STRIP_CONTAINER_SENTINEL:
        if participant.startswith(_CONTAINER_PREFIX):
            return participant[len(_CONTAINER_PREFIX) :]
        return participant
    return value


# ---------------------------------------------------------------------------
# Archiver
# ---------------------------------------------------------------------------


class Archiver:
    """Fetches acked threads since *cursor*, renders and dispatches to graphiti."""

    def __init__(
        self,
        config: ArchiverConfig,
        chatroom: Any,
        graphiti: GraphitiClient,
    ) -> None:
        self._config = config
        self._chatroom = chatroom
        self._graphiti = graphiti

    async def archive_since(
        self,
        cursor: str | None,
        state: State,
        state_path: Path,
    ) -> None:
        """Fetch acked threads updated after *cursor* and archive each to graphiti."""
        threads: list[dict[str, Any]] = await self._chatroom.list_threads(
            since=cursor, status='acked'
        )

        for thread in threads:
            subject: str = thread['subject']

            # Skipped threads advance cursor (intentional exclusion, not failure)
            if subject in self._config.exclude_test_subjects:
                state.archive_cursor = thread['updated_at']
                state.save(state_path)
                continue

            # Fetch full thread detail (with messages)
            detail = await self._chatroom.get_thread(thread['id'])
            messages: list[dict[str, Any]] = detail.get('messages', [])

            rendered = render_thread(detail, messages)

            if self._config.max_thread_chars and len(rendered) > self._config.max_thread_chars:
                rendered = rendered[: self._config.max_thread_chars]

            participant: str = thread.get('from_participant', '')
            group_id = resolve_group_id(participant, self._config.group_id_map)

            try:
                await self._graphiti.add_memory(
                    group_id=group_id,
                    content=rendered,
                    source_type='text',
                )
            except Exception:
                # Do not advance cursor — will retry on next poll
                continue

            # Advance cursor only on success
            state.archive_cursor = thread['updated_at']
            state.save(state_path)
