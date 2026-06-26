"""ClaimAnnouncer — creates claim_request threads for newly eligible GH tickets."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pb_chatroom_relay.client import ChatroomClient

_ANNOUNCED_FILE = 'announced_tickets.json'


class ClaimAnnouncer:
    """Announce newly eligible GitHub tickets as claim_request threads.

    Args:
        client: ChatroomClient used to create threads.
        auto_agents: List of *-auto participant IDs to address the thread to.
        state_path: Directory where ``announced_tickets.json`` is kept.
    """

    def __init__(
        self,
        client: ChatroomClient,
        auto_agents: list[str],
        state_path: Path,
    ) -> None:
        self._client = client
        self._auto_agents = auto_agents
        self._state_path = state_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def announce(self, ticket: dict) -> bool:
        """Announce *ticket* as a claim_request thread if not already announced.

        Returns True if a new thread was created, False otherwise.
        """
        if not self._auto_agents:
            return False

        ticket_key = f"{ticket['repo']}#{ticket['number']}"

        announced = self._load_announced()
        if ticket_key in announced:
            return False

        body = self._format_body(ticket)
        subject = f"Claim request: {ticket['title']}"

        await self._client.create_root_thread(
            subject=subject,
            body=body,
            to_participant=self._auto_agents[0],
            to_participants=self._auto_agents,
            discussion_type='claim_request',
            metadata={'ticket_key': ticket_key},
        )

        announced.add(ticket_key)
        self._save_announced(announced)
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _announced_path(self) -> Path:
        return self._state_path / _ANNOUNCED_FILE

    def _load_announced(self) -> set[str]:
        path = self._announced_path()
        if not path.exists():
            return set()
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return set(data)
        except (json.JSONDecodeError, TypeError):
            return set()

    def _save_announced(self, announced: set[str]) -> None:
        path = self._announced_path()
        tmp = path.with_suffix('.tmp')
        tmp.write_text(
            json.dumps(sorted(announced), indent=2),
            encoding='utf-8',
        )
        os.replace(tmp, path)

    @staticmethod
    def _format_body(ticket: dict) -> str:
        labels_str = ', '.join(ticket.get('labels', []))
        number = ticket['number']
        return (
            f"**Ticket:** [{ticket['title']}]({ticket['url']})\n"
            f"**Labels:** {labels_str}\n"
            f"**Repo:** {ticket['repo']}\n\n"
            f"Reply with `CLAIM: #{number} — <one-line scope>` to claim this ticket.\n"
            'First valid CLAIM within 60 seconds wins.'
        )
