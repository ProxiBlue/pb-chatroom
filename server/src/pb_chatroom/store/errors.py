"""Store-layer errors for pb-chatroom."""

from __future__ import annotations


class ThreadNotFoundError(Exception):
    """Raised when a thread_id does not exist in the threads table."""
