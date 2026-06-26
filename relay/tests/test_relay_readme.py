from __future__ import annotations

from pathlib import Path

import pytest

README = Path('/home/lucas/claude-plugins-central/seed/marketplaces/pb-chatroom/relay/README.md')


@pytest.fixture
def readme() -> str:
    return README.read_text()


def test_it_has_a_top_level_heading_with_the_package_name(readme: str) -> None:
    assert '# pb-chatroom-relay' in readme


def test_it_documents_all_three_role_classes_with_one_paragraph_each(readme: str) -> None:
    assert 'Responder' in readme or 'responder' in readme
    assert 'Broadcaster' in readme or 'broadcaster' in readme
    assert 'Archiver' in readme or 'archiver' in readme


def test_it_provides_a_full_config_reference_table_for_the_responders_block(readme: str) -> None:
    assert 'max_invocations_per_hour' in readme
    assert 'trigger' in readme


def test_it_provides_a_full_config_reference_table_for_the_broadcasters_block(readme: str) -> None:
    assert 'idle_threshold_minutes' in readme
    assert 'active_window' in readme


def test_it_provides_a_full_config_reference_table_for_the_archivers_block(readme: str) -> None:
    assert 'max_thread_chars' in readme
    assert 'exclude_test_subjects' in readme


def test_it_documents_all_three_cli_subcommands(readme: str) -> None:
    assert 'dry-run' in readme
    assert 'budget' in readme


def test_it_documents_the_docker_compose_profile_relay_opt_in(readme: str) -> None:
    assert '--profile relay' in readme


def test_it_includes_a_troubleshooting_section(readme: str) -> None:
    assert 'timeout' in readme.lower() or 'timed out' in readme.lower()
    assert 'budget' in readme.lower()
    assert 'graphiti' in readme.lower()
