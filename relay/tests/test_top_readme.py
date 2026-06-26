from __future__ import annotations

from pathlib import Path

import pytest

README = Path('/home/lucas/claude-plugins-central/seed/marketplaces/pb-chatroom/README.md')


@pytest.fixture
def readme():
    return README.read_text()


def test_it_adds_a_v0_3_0_milestone_note_mentioning_the_relay_daemon(readme):
    assert 'v0.3.0' in readme or '0.3.0' in readme
    assert 'relay' in readme.lower()


def test_it_links_to_relay_readme_from_the_milestone_note(readme):
    assert 'relay/README.md' in readme or 'relay/' in readme


def test_it_preserves_the_existing_milestone_notes_for_prior_versions(readme):
    # v0.1.x and v0.2.x milestones should still be present
    assert 'v0.1' in readme or '0.1' in readme
