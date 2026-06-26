"""Grep-based tests verifying README.md and NOTICE content for Phase 1 deliverables."""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
README = (REPO_ROOT / 'README.md').read_text()
NOTICE = (REPO_ROOT / 'NOTICE').read_text()


def test_it_documents_docker_compose_up_d_as_the_quickstart():
    assert 'docker compose up -d' in README
    # Must be in a Quick start section
    assert '## Quick start' in README or '## Quick Start' in README


def test_it_lists_all_five_slash_commands_in_the_slash_commands_section():
    assert 'Slash commands' in README
    assert 'chat-threads-open' in README
    assert 'chat-send' in README
    assert 'chat-threads' in README
    assert 'chat-read' in README
    assert 'chat-ack' in README


def test_it_describes_the_structural_subagent_write_enforcement_accurately():
    # Must reflect structural enforcement, not just convention
    assert 'MCP exposes no root-thread creation tool' in README or \
        'no root-thread creation' in README


def test_it_includes_aiosqlite_jinja2_and_pydantic_settings_in_notice():
    assert 'aiosqlite' in NOTICE
    assert 'jinja2' in NOTICE or 'Jinja2' in NOTICE
    assert 'pydantic-settings' in NOTICE


def test_it_documents_the_mcp_url_for_both_host_and_ddev_container_sessions():
    assert 'http://localhost:7477/mcp' in README
    assert 'http://host.docker.internal:7477/mcp' in README
