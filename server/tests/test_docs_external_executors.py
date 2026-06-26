"""Grep-based tests verifying docs/external-executors.md content."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DOC = (REPO_ROOT / 'docs' / 'external-executors.md').read_text()


def test_it_explains_why_the_executor_is_operator_chosen_rather_than_bundled():
    assert 'operator-chosen' in DOC or 'operator chosen' in DOC
    assert 'protocol' in DOC and 'storage' in DOC


def test_it_lists_claudeclaw_as_the_recommended_option():
    assert 'claudeclaw' in DOC
    assert 'Recommended' in DOC or 'recommended' in DOC


def test_it_lists_claude_code_scheduler_as_the_cron_only_option():
    assert 'claude-code-scheduler' in DOC
    assert 'cron' in DOC


def test_it_lists_plain_shell_while_loop_as_the_minimal_option():
    assert 'while true' in DOC or 'while-loop' in DOC or 'while loop' in DOC
    assert 'shell' in DOC or 'bash' in DOC or 'Bash' in DOC


def test_it_documents_the_bridge_contract_for_GET_POST_and_ack_endpoints():
    assert '/api/threads' in DOC
    assert '/api/threads/<id>/messages' in DOC or '/api/threads/{id}/messages' in DOC
    assert '/api/threads/<id>/ack' in DOC or '/api/threads/{id}/ack' in DOC


def test_it_documents_the_X_PB_Chatroom_Participant_header():
    assert 'X-PB-Chatroom-Participant' in DOC
