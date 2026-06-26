from __future__ import annotations

import logging

import pytest

from pb_chatroom_relay.config import RespondersConfig
from pb_chatroom_relay.identity_validation import IdentityValidationError, validate_identities


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(
    responders: dict | None = None,
    broadcasters: dict | None = None,
) -> RespondersConfig:
    return RespondersConfig.model_validate(
        {
            'responders': responders or {},
            'broadcasters': broadcasters or {},
        }
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_it_accepts_a_config_containing_only_canonical_identities() -> None:
    cfg = _config(
        responders={'host': {}, 'host-auto': {}},
        broadcasters={
            'b1': {'broadcast_to': ['container-foo'], 'enabled': False},
        },
    )
    # must not raise
    validate_identities(cfg)


def test_it_raises_a_startup_error_when_an_unknown_identity_appears_in_responders() -> None:
    cfg = _config(responders={'relay-bot': {}})
    with pytest.raises(IdentityValidationError) as exc_info:
        validate_identities(cfg)
    assert 'relay-bot' in str(exc_info.value)


def test_it_raises_a_startup_error_when_an_unknown_identity_appears_in_broadcast_to() -> None:
    cfg = _config(
        broadcasters={'b1': {'broadcast_to': ['mystery-identity'], 'enabled': False}},
    )
    with pytest.raises(IdentityValidationError) as exc_info:
        validate_identities(cfg)
    assert 'mystery-identity' in str(exc_info.value)


def test_it_emits_a_deprecation_warning_when_host_agent_appears_as_a_responder_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _config(responders={'host-agent': {}})
    with caplog.at_level(logging.WARNING, logger='pb_chatroom_relay'):
        validate_identities(cfg)
    assert any('host-agent' in r.message for r in caplog.records)


def test_it_emits_a_deprecation_warning_when_host_agent_appears_in_broadcast_to(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _config(
        broadcasters={'b1': {'broadcast_to': ['host-agent'], 'enabled': False}},
    )
    with caplog.at_level(logging.WARNING, logger='pb_chatroom_relay'):
        validate_identities(cfg)
    assert any('host-agent' in r.message for r in caplog.records)


def test_it_does_not_block_startup_for_deprecated_identities() -> None:
    cfg = _config(responders={'host-agent': {}})
    # must not raise
    validate_identities(cfg)


def test_it_includes_the_migration_target_in_every_deprecation_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _config(responders={'host-agent': {}})
    with caplog.at_level(logging.WARNING, logger='pb_chatroom_relay'):
        validate_identities(cfg)
    warning_messages = [r.message for r in caplog.records if 'host-agent' in r.message]
    assert warning_messages, 'expected at least one warning mentioning host-agent'
    # migration target for host-agent is 'host or host-auto'
    for msg in warning_messages:
        assert 'host' in msg, f'migration target not in warning: {msg!r}'
