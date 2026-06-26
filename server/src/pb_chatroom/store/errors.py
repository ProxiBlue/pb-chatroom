"""Store-layer errors for pb-chatroom."""

from __future__ import annotations


class ThreadNotFoundError(Exception):
    """Raised when a thread_id does not exist in the threads table."""


class ClaimConflictError(Exception):
    """Raised when a thread is already claimed by a different participant."""

    def __init__(self, claimed_by: str) -> None:
        super().__init__(f'Thread already claimed by {claimed_by!r}')
        self.claimed_by = claimed_by
