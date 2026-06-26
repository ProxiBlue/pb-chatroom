"""Participant ID resolution for pb-chatroom.

Resolution order:
1. PB_CHATROOM_PARTICIPANT_ID env var (verbatim, wins over all)
2. DDEV_PROJECT env var → 'container-<value>' (lower-cased)
3. Fallback: 'host'

Resolved IDs must match [a-z0-9_-]+ and be 1–64 chars.
"""

from __future__ import annotations

import os
import re

_VALID = re.compile(r'^[a-z0-9_-]+$')
_MAX_LEN = 64


def _validate(id_: str) -> str:
    if not _VALID.match(id_):
        raise ValueError(f'Participant ID {id_!r} contains characters outside [a-z0-9_-]')
    if len(id_) > _MAX_LEN:
        raise ValueError(f'Participant ID must be at most {_MAX_LEN} characters, got {len(id_)}')
    return id_


def resolve_participant_id() -> str:
    """Return the participant ID for the current process."""
    override = os.environ.get('PB_CHATROOM_PARTICIPANT_ID')
    if override is not None:
        return _validate(override)

    project = os.environ.get('DDEV_PROJECT')
    if project is not None:
        return _validate(f'container-{project.lower()}')

    return 'host'
