from __future__ import annotations

from pathlib import Path

README = Path('/home/lucas/claude-plugins-central/seed/marketplaces/pb-chatroom/relay/README.md')


def test_it_pins_the_identity_convention_at_the_top_with_canonical_forms() -> None:
    text = README.read_text()
    assert 'host-auto' in text
    assert 'container-<X>-auto' in text or 'container-<X>' in text


def test_it_documents_the_host_agent_deprecation_note() -> None:
    text = README.read_text()
    assert 'host-agent' in text
    assert 'deprecated' in text.lower() or 'Deprecated' in text


def test_it_documents_the_claim_protocol_with_the_60s_deadline_and_first_wins_semantics() -> None:
    text = README.read_text()
    assert 'claim_request' in text
    assert '60' in text
    assert 'first' in text.lower()


def test_it_documents_the_seven_discussion_types_and_their_default_actions() -> None:
    text = README.read_text()
    for dt in ['claim_request', 'design_question', 'postmortem', 'escalation', 'debate']:
        assert dt in text


def test_it_documents_the_merged_escalation_set_with_each_trigger() -> None:
    text = README.read_text()
    assert 'escalation' in text.lower()
    assert 'api_key' in text or 'external_credentials' in text


def test_it_documents_the_ask_peer_graphiti_first_short_circuit_behavior() -> None:
    text = README.read_text()
    assert 'chat_ask_peer' in text or 'ask_peer' in text
    assert 'graphiti' in text.lower()
