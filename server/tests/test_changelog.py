from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
CHANGELOG = PROJECT_ROOT / 'CHANGELOG.md'


def _text() -> str:
    return CHANGELOG.read_text()


def test_it_documents_v0_4_0_as_the_current_release():
    text = _text()
    assert '## [0.4.0]' in text
    assert '2026-06-27' in text


def test_it_includes_a_removed_section_noting_the_relay_daemon_was_deleted():
    text = _text()
    assert '### Removed' in text
    assert 'relay' in text.lower()
    # Three confirmed bugs must be mentioned
    assert 'IsADirectoryError' in text
    assert 'KeyError' in text


def test_it_includes_an_added_section_listing_the_coordination_layer_features():
    text = _text()
    assert '### Added' in text
    assert 'CLAIM' in text
    assert 'multi-recipient' in text
    assert 'discussion_type' in text
    assert 'escalation' in text
    assert 'dashboard' in text
    assert 'chat_ask_peer' in text
    assert 'identity' in text


def test_it_includes_a_changed_section_noting_the_claudeclaw_integration_recipe():
    text = _text()
    assert '### Changed' in text
    assert 'claudeclaw' in text.lower()


def test_it_back_fills_v0_1_0_with_a_one_liner():
    text = _text()
    assert '## [0.1.0]' in text
    # One-liner — FastAPI REST basics must be mentioned
    assert 'FastAPI' in text


def test_it_back_fills_v0_3_0_with_a_one_liner():
    text = _text()
    assert '## [0.3.0]' in text
    assert 'Relay' in text or 'relay' in text


def test_it_follows_the_keep_a_changelog_header_format_with_semver_and_dates():
    text = _text()
    assert 'Keep a Changelog' in text
    # Unreleased section present
    assert '## [Unreleased]' in text
    # Footer reference links present
    assert '[0.4.0]:' in text
    assert '[0.3.0]:' in text
    assert '[0.1.0]:' in text
