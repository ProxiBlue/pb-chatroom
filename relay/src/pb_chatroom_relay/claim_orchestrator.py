"""ClaimOrchestrator — tracks 60s deadlines on claim_request threads and escalates."""

from __future__ import annotations

from datetime import datetime, timedelta

from pb_chatroom_relay.budget import Clock, UtcClock
from pb_chatroom_relay.client import ChatroomClient


class ClaimOrchestrator:
    """Track per-thread deadlines for claim_request threads.

    On each polling tick, call ``observe_threads`` with the current open
    thread list.  The orchestrator arms a deadline per unseen claim_request
    thread, cancels it on a successful CLAIM, and posts an escalation message
    when the deadline elapses with no claim.

    Args:
        client: ChatroomClient used to post escalation messages.
        claim_deadline_seconds: Seconds from thread creation before escalating.
        clock: Injectable clock (defaults to UtcClock for production).
    """

    def __init__(
        self,
        client: ChatroomClient,
        claim_deadline_seconds: int = 60,
        clock: Clock | None = None,
    ) -> None:
        self._client = client
        self._deadline_s = claim_deadline_seconds
        self._clock = clock or UtcClock()
        self._armed: dict[str, datetime] = {}  # thread_id -> deadline_at

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def observe_threads(self, threads: list[dict]) -> None:
        """Called on each polling tick with the current open threads."""
        for thread in threads:
            if thread.get('discussion_type') != 'claim_request':
                continue
            tid = thread['id']
            claimed_by = thread.get('claimed_by')

            if claimed_by:
                # Claimed — cancel deadline if armed
                self._armed.pop(tid, None)
                continue

            # Not claimed — check or arm deadline
            if tid not in self._armed:
                # Calculate deadline from thread created_at (supports restart-resume)
                created_at = datetime.fromisoformat(thread['created_at'].replace('Z', '+00:00'))
                deadline_at = created_at + timedelta(seconds=self._deadline_s)
                self._armed[tid] = deadline_at

            # Check if deadline passed
            if self._clock.now() >= self._armed[tid]:
                await self._client.post_message(
                    tid,
                    'no claimant — escalating to Lucas',
                    discussion_type='escalation',
                )
                self._armed.pop(tid)
