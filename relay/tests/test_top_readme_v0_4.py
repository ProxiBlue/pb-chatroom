from __future__ import annotations

from pathlib import Path

README = Path('/home/lucas/claude-plugins-central/seed/marketplaces/pb-chatroom/README.md')


def test_it_adds_a_v0_4_0_row_to_the_status_table_mentioning_agent_to_agent_coordination():
    text = README.read_text()
    assert 'v0.4.0' in text
    assert 'agent-to-agent' in text.lower() or 'coordination' in text.lower()


def test_it_links_to_relay_readme_from_the_v0_4_0_row():
    text = README.read_text()
    assert 'relay/README.md' in text


def test_it_links_to_docs_agent_to_agent_md_from_the_v0_4_0_row():
    text = README.read_text()
    assert 'docs/agent-to-agent.md' in text


def test_it_adds_a_deprecation_note_for_host_agent():
    text = README.read_text()
    assert 'host-agent' in text
    assert 'deprecated' in text.lower() or 'Deprecated' in text or 'migration' in text.lower()


def test_it_preserves_the_existing_v0_1_0_and_v0_3_0_rows():
    text = README.read_text()
    assert 'v0.1.0' in text
    assert 'v0.3.0' in text
