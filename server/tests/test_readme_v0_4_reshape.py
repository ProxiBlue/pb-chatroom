from __future__ import annotations

from pathlib import Path

README = Path(__file__).parents[2] / 'README.md'


def _readme() -> str:
    return README.read_text()


def test_it_shows_the_v0_4_0_row_mentioning_the_claudeclaw_recipe():
    text = _readme()
    assert 'v0.4.0' in text
    assert 'claudeclaw' in text.lower()


def test_it_shows_the_v0_5_0_row_mentioning_slack_ingress_and_identity_registry():
    text = _readme()
    assert 'v0.5.0' in text
    assert 'slack' in text.lower()
    assert 'identity registry' in text.lower()


def test_it_does_not_mention_a_bundled_relay_daemon():
    text = _readme()
    assert 'relay daemon' not in text.lower()
    assert 'bundled relay' not in text.lower()


def test_it_links_to_docs_claudeclaw_integration_md_from_a_quick_start_section():
    text = _readme()
    assert 'docs/claudeclaw-integration.md' in text
    # Must appear under a Quick Start heading that references claudeclaw
    lines = text.splitlines()
    qs_idx = next(
        (
            i
            for i, l in enumerate(lines)
            if 'quick start' in l.lower() and 'claudeclaw' in l.lower() and l.startswith('#')
        ),
        None,
    )
    assert qs_idx is not None, 'No "Quick Start with claudeclaw" heading found'
    # Find the link within the next 10 lines (section is ≤5 lines)
    section_lines = lines[qs_idx : qs_idx + 10]
    assert any('docs/claudeclaw-integration.md' in l for l in section_lines)


def test_it_preserves_the_existing_v0_1_0_and_v0_3_0_status_rows():
    text = _readme()
    assert 'v0.1.0' in text
    assert 'v0.3.0' in text


def test_it_does_not_contain_a_stale_subagent_tool_access_v0_4_0_line():
    text = _readme()
    # Stale line pattern: "Subagent tool access" appearing as a v0.4.0 bullet/entry
    lower = text.lower()
    # The phrase shouldn't appear as a v0.4.0 descriptor in the status table
    # Strategy: find v0.4.0 row content and ensure it doesn't contain the stale phrase
    v04_idx = lower.find('v0.4.0')
    if v04_idx == -1:
        return  # no v0.4.0 at all — covered by other test
    # Grab the line(s) of the v0.4.0 table row
    start = lower.rfind('\n', 0, v04_idx)
    end = lower.find('\n', v04_idx)
    row_content = lower[start:end]
    assert 'subagent tool access' not in row_content
