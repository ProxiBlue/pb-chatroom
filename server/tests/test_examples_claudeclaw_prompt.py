from __future__ import annotations

from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent.parent.parent / 'examples'
PROMPT_FILE = EXAMPLES_DIR / 'claudeclaw-system-prompt.md'


def load_prompt() -> str:
    return PROMPT_FILE.read_text()


def test_it_includes_a_placeholder_for_the_agent_identity():
    assert PROMPT_FILE.exists(), f'File not found: {PROMPT_FILE}'
    content = load_prompt()
    assert '{{identity}}' in content or '[YOUR-IDENTITY]' in content, (
        'Prompt must contain identity placeholder ({{identity}} or [YOUR-IDENTITY])'
    )


def test_it_instructs_claude_to_call_chat_list_threads_as_the_first_action():
    content = load_prompt()
    assert 'chat_list_threads' in content, 'Prompt must mention chat_list_threads'
    # Must appear as a first-action instruction, not just a passing mention
    lower = content.lower()
    assert 'first' in lower or 'before anything' in lower or 'start by' in lower, (
        'Prompt must instruct chat_list_threads as first action'
    )


def test_it_documents_the_claim_format_with_the_60_second_window_and_a_scope_line():
    content = load_prompt()
    assert 'CLAIM' in content or 'chat_claim' in content, 'Prompt must document CLAIM protocol'
    assert '60' in content, 'Prompt must mention the 60 second window'
    assert 'scope' in content.lower(), 'Prompt must mention scope line'


def test_it_documents_the_escalation_set_as_must_escalate_not_auto_fix():
    content = load_prompt()
    lower = content.lower()
    assert 'must' in lower and 'escalat' in lower, (
        'Prompt must use "must escalate" language (not auto-fix)'
    )
    # All 7 escalation rules must appear
    rules = [
        'multiple_competing_approaches',
        'architectural_changes',
        'prod_data_access',
        'cost_trigger',
        'confidence_below_threshold',
        'external_credentials',
        'tests_broken',
    ]
    for rule in rules:
        assert rule in content, f'Prompt must list escalation rule: {rule}'


def test_it_documents_graphiti_first_ordering_for_chat_ask_peer():
    content = load_prompt()
    assert 'graphiti' in content.lower(), 'Prompt must mention graphiti'
    assert 'chat_ask_peer' in content, 'Prompt must mention chat_ask_peer'
    lower = content.lower()
    assert 'first' in lower or 'before' in lower, (
        'Prompt must document graphiti-first ordering'
    )


def test_it_documents_discussion_type_usage():
    content = load_prompt()
    assert 'discussion_type' in content, 'Prompt must document discussion_type'
    # Should list at least some of the known types
    known_types = ['claim_request', 'design_question', 'postmortem', 'escalation']
    found = [t for t in known_types if t in content]
    assert len(found) >= 2, (
        f'Prompt must document at least 2 discussion_type values, found: {found}'
    )


def test_it_documents_chat_send_for_in_progress_and_chat_ack_for_done():
    content = load_prompt()
    assert 'chat_send' in content, 'Prompt must mention chat_send'
    assert 'chat_ack' in content, 'Prompt must mention chat_ack'
    lower = content.lower()
    assert 'in-progress' in lower or 'in progress' in lower or 'progress' in lower, (
        'Prompt must associate chat_send with in-progress updates'
    )
    assert 'done' in lower or 'complet' in lower or 'finish' in lower, (
        'Prompt must associate chat_ack with completion'
    )
