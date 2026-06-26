"""Grep-based tests verifying docs/claudeclaw-integration.md content."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DOC_PATH = REPO_ROOT / 'docs' / 'claudeclaw-integration.md'


def _doc() -> str:
    return DOC_PATH.read_text()


def test_it_references_examples_claudeclaw_host_auto_json_literally():
    assert 'examples/claudeclaw-host-auto.json' in _doc()


def test_it_references_examples_claudeclaw_system_prompt_md_literally():
    assert 'examples/claudeclaw-system-prompt.md' in _doc()


def test_it_includes_a_copy_pasteable_cron_snippet_for_the_heartbeat():
    doc = _doc()
    # Must contain a cron pattern with */5 interval in hours 8-19
    assert '*/5' in doc
    assert '8-19' in doc or '8-18' in doc


def test_it_documents_the_operator_opt_in_checklist_for_one_identity_first():
    doc = _doc()
    # Must contain an opt-in checklist section
    assert 'checklist' in doc.lower() or 'opt-in' in doc.lower() or 'Opt-in' in doc
    # Must contain numbered or bulleted items (1. or - or *)
    import re
    assert re.search(r'^\s*[1-9]\.\s', doc, re.MULTILINE) or re.search(
        r'^\s*[-*]\s', doc, re.MULTILINE
    )


def test_it_defers_slack_ingress_to_v050_with_a_placeholder_section():
    doc = _doc()
    assert 'v0.5.0' in doc
    assert 'Slack' in doc or 'slack' in doc
    assert 'deferred' in doc.lower() or 'placeholder' in doc.lower()


def test_it_points_at_the_bridge_contract_in_docs_external_executors_md():
    doc = _doc()
    assert 'external-executors.md' in doc or 'docs/external-executors.md' in doc
