from __future__ import annotations

import re

_CANONICAL_PATTERNS = [
    re.compile(r'^host$'),
    re.compile(r'^host-auto$'),
    re.compile(r'^container-[a-z0-9][a-z0-9-]*[a-z0-9]$'),
]


_DEPRECATED: dict[str, str] = {
    'host-agent': 'host or host-auto',
}


def is_canonical(identity: str) -> bool:
    return any(p.match(identity) for p in _CANONICAL_PATTERNS)


def is_deprecated(identity: str) -> bool:
    return identity in _DEPRECATED


def migration_target(identity: str) -> str | None:
    return _DEPRECATED.get(identity)


_CONTAINER_PREFIX = 'container-'
_AUTO_SUFFIX = '-auto'


def derive_group_id(participant: str) -> str:
    """Derive a graphiti group_id from a participant identity string."""
    name = participant
    if name.endswith(_AUTO_SUFFIX):
        name = name[: -len(_AUTO_SUFFIX)]
    if name.startswith(_CONTAINER_PREFIX):
        name = name[len(_CONTAINER_PREFIX) :]
    if name.startswith('host'):
        return 'host'
    return name


def explain_rejection(identity: str) -> str | None:
    if is_canonical(identity):
        return None
    if is_deprecated(identity):
        target = _DEPRECATED[identity]
        return f"'{identity}' is deprecated — use {target} instead."
    return f"'{identity}' is not a recognised canonical identity."
