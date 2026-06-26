from __future__ import annotations

from pathlib import Path

DOC_PATH = Path(__file__).parent.parent.parent / 'docs' / 'agent-to-agent.md'


def _doc() -> str:
    return DOC_PATH.read_text()


def test_it_removes_references_to_the_relay_daemon_doing_the_triggering() -> None:
    text = _doc()
    # Relay daemon must not appear as the triggering actor
    assert 'relay daemon' not in text.lower(), (
        'docs/agent-to-agent.md still references "relay daemon" as a triggering component'
    )


def test_it_uses_neutral_executor_language_for_the_trigger_source() -> None:
    text = _doc()
    assert 'executor' in text.lower(), (
        'docs/agent-to-agent.md must use neutral "executor" language for the trigger source'
    )


def test_it_links_to_docs_external_executors_md_for_executor_choice() -> None:
    text = _doc()
    assert 'docs/external-executors.md' in text or 'external-executors.md' in text, (
        'docs/agent-to-agent.md must link to docs/external-executors.md'
    )


def test_it_links_to_docs_claudeclaw_integration_md_for_the_recommended_pairing() -> None:
    text = _doc()
    assert 'docs/claudeclaw-integration.md' in text or 'claudeclaw-integration.md' in text, (
        'docs/agent-to-agent.md must link to docs/claudeclaw-integration.md'
    )


def test_it_preserves_the_five_existing_protocol_patterns_ticket_pickup_design_question_debate_escalation_while_away() -> None:  # noqa: E501
    text = _doc()
    patterns = [
        'ticket pickup',
        'design question',
        'debate',
        'escalation',
        'while-away',
    ]
    for pattern in patterns:
        assert pattern.lower() in text.lower(), (
            f'docs/agent-to-agent.md is missing protocol pattern: "{pattern}"'
        )
