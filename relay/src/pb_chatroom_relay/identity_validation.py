from __future__ import annotations

import logging

from pb_chatroom_relay.config import RespondersConfig
from pb_chatroom_relay.identity import is_canonical, is_deprecated, migration_target

logger = logging.getLogger(__name__)


class IdentityValidationError(ValueError):
    """Raised when one or more unknown identities are found in the relay config."""


def validate_identities(config: RespondersConfig) -> None:
    """Scan *config* for invalid participant identities.

    - Unknown identities (neither canonical nor deprecated) raise ``IdentityValidationError``
      listing every offending entry.
    - Deprecated identities (e.g. ``host-agent``) emit a ``logging.WARNING`` naming the
      identity and its migration target but do NOT block startup.
    """
    unknowns: list[str] = []

    def _check(identity: str, location: str) -> None:
        if is_canonical(identity):
            return
        if is_deprecated(identity):
            target = migration_target(identity)
            logger.warning(
                "DEPRECATED identity '%s' in %s — migrate to: %s",
                identity,
                location,
                target,
            )
        else:
            unknowns.append(f'{identity!r} (in {location})')

    for responder_key in config.responders:
        _check(responder_key, 'responders')

    for broadcaster_name, bc in config.broadcasters.items():
        for target_identity in bc.broadcast_to:
            _check(target_identity, f'broadcasters[{broadcaster_name!r}].broadcast_to')

    if unknowns:
        joined = ', '.join(unknowns)
        raise IdentityValidationError(
            f'Relay startup aborted — unknown identities detected: {joined}'
        )
