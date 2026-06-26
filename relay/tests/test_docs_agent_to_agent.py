from __future__ import annotations

from pathlib import Path

DOCS = Path('/home/lucas/claude-plugins-central/seed/marketplaces/pb-chatroom/docs/agent-to-agent.md')


def test_it_documents_the_ticket_pickup_flow_turn_by_turn_from_gh_issue_to_archiver():
    text = DOCS.read_text()
    assert 'claim_request' in text
    assert 'gh issue' in text or 'gh_polling' in text or 'GH' in text


def test_it_documents_the_design_question_flow_turn_by_turn_including_graphiti_short_circuit():
    text = DOCS.read_text()
    assert 'design_question' in text
    assert 'graphiti' in text.lower()
    assert 'short-circuit' in text or 'threshold' in text.lower()


def test_it_documents_the_debate_flow_turn_by_turn_including_2_round_escalation():
    text = DOCS.read_text()
    assert 'escalation' in text.lower()
    assert 'competing' in text.lower() or 'trade-off' in text.lower() or 'approach' in text.lower()


def test_it_documents_the_escalation_flow_turn_by_turn_for_at_least_three_rules():
    text = DOCS.read_text()
    rules = [
        'multiple_competing_approaches',
        'confidence_below_threshold',
        'external_credentials',
        'prod_data_access',
        'cost_trigger',
        'architectural_changes',
        'tests_broken',
    ]
    matched = [r for r in rules if r in text]
    assert len(matched) >= 3


def test_it_documents_the_while_away_recall_flow_from_session_start_to_compact_list():
    text = DOCS.read_text()
    assert 'while-away' in text or 'while_away' in text or 'chat-while-away' in text
    assert 'SessionStart' in text or 'session start' in text.lower()


def test_it_includes_a_section_linking_back_to_relay_readme_for_config_reference():
    text = DOCS.read_text()
    assert 'relay/README.md' in text or 'relay/readme.md' in text.lower()
