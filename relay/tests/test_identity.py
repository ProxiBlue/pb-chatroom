from __future__ import annotations

from pb_chatroom_relay.identity import (
    explain_rejection,
    is_canonical,
    is_deprecated,
    migration_target,
)


def test_it_accepts_host_as_canonical() -> None:
    assert is_canonical('host') is True


def test_it_accepts_host_auto_as_canonical() -> None:
    assert is_canonical('host-auto') is True


def test_it_accepts_container_pvcpipesupplies_as_canonical() -> None:
    assert is_canonical('container-pvcpipesupplies') is True


def test_it_accepts_container_pvcpipesupplies_auto_as_canonical() -> None:
    assert is_canonical('container-pvcpipesupplies-auto') is True


def test_it_returns_a_friendly_explanation_when_an_identity_is_rejected() -> None:
    # deprecated identity — explanation mentions migration target
    explanation = explain_rejection('host-agent')
    assert explanation
    assert 'host-agent' in explanation
    assert 'host' in explanation

    # unknown identity — explanation mentions it is unknown/unrecognised
    explanation = explain_rejection('relay-bot')
    assert explanation
    assert 'relay-bot' in explanation

    # canonical identity — no explanation needed
    assert explain_rejection('host') in ('', None)


def test_it_rejects_unknown_identities_such_as_relay_bot_or_host_special() -> None:
    assert is_canonical('relay-bot') is False
    assert is_deprecated('relay-bot') is False
    assert is_canonical('host-special') is False
    assert is_deprecated('host-special') is False


def test_it_rejects_host_agent_as_deprecated_and_reports_the_migration_target() -> None:
    assert is_canonical('host-agent') is False
    assert is_deprecated('host-agent') is True
    target = migration_target('host-agent')
    assert target is not None
    assert 'host' in target
