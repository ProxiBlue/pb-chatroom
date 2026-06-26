"""BroadcasterEmitter — fires root threads for each broadcast_to participant."""

from __future__ import annotations

import logging
from datetime import datetime

from pb_chatroom_relay.client import ChatroomClient
from pb_chatroom_relay.config import BroadcasterConfig
from pb_chatroom_relay.idle import IdleSupervisor

logger = logging.getLogger(__name__)


class BroadcasterEmitter:
    """Emit one root thread per participant for a given broadcaster config."""

    def __init__(self, client: ChatroomClient, idle_supervisor: IdleSupervisor) -> None:
        self._client = client
        self._idle_supervisor = idle_supervisor

    async def emit(
        self,
        broadcaster_name: str,
        broadcaster_config: BroadcasterConfig,
        now: datetime,
    ) -> int:
        """Create one root thread per participant; return count of successes."""
        created_count = 0
        for target in broadcaster_config.broadcast_to:
            try:
                await self._client.create_root_thread(
                    subject=broadcaster_config.prompt_subject,
                    body=broadcaster_config.prompt_body,
                    to_participant=target,
                    metadata={'broadcaster': broadcaster_name},
                )
                created_count += 1
            except Exception:
                logger.exception(
                    'broadcaster %r: failed to create thread for participant %r',
                    broadcaster_name,
                    target,
                )

        if created_count > 0:
            self._idle_supervisor.record_emission(broadcaster_name, now)

        return created_count
