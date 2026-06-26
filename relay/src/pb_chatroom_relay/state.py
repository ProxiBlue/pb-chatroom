"""Relay state persistence — per-role cursors and per-responder budget counters."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class State:
    """In-memory state for the relay daemon backed by a single JSON file."""

    def __init__(
        self,
        poll_cursor: str | None = None,
        archive_cursor: str | None = None,
        budget: dict[str, Any] | None = None,
        broadcaster_state: dict[str, Any] | None = None,
    ) -> None:
        self.poll_cursor = poll_cursor
        self.archive_cursor = archive_cursor
        self.budget: dict[str, Any] = budget if budget is not None else {}
        self.broadcaster_state: dict[str, Any] = (
            broadcaster_state if broadcaster_state is not None else {}
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> State:
        """Return a State from *path*, or a fresh zero-state if the file is absent."""
        if not path.exists():
            return cls()
        raw = path.read_text(encoding='utf-8')
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f'malformed state file at {path}: {exc}') from exc
        return cls(
            poll_cursor=data.get('poll_cursor'),
            archive_cursor=data.get('archive_cursor'),
            budget=data.get('budget', {}),
            broadcaster_state=data.get('broadcaster_state', {}),
        )

    def save(self, path: Path) -> None:
        """Atomically write state to *path* using a tmp file + os.replace."""
        data: dict[str, Any] = {
            'poll_cursor': self.poll_cursor,
            'archive_cursor': self.archive_cursor,
            'budget': self.budget,
            'broadcaster_state': self.broadcaster_state,
        }
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')
        os.replace(tmp, path)


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    """Write *data* as JSON to *path* atomically via a sibling .tmp file."""
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')
    os.replace(tmp, path)
