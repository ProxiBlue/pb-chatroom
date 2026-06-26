"""Guard-rail tests: no relay-daemon / responder / broadcaster / archiver wording.

Applies to user-facing files. docs/plan-history/ is explicitly excluded — those
files document the deleted system as history.
"""

from __future__ import annotations

from pathlib import Path

# Project root is three levels up from server/tests/
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _text(rel: str) -> str:
    return (PROJECT_ROOT / rel).read_text().lower()


def _plan_history_texts() -> list[str]:
    ph = PROJECT_ROOT / 'docs' / 'plan-history'
    return [p.read_text().lower() for p in ph.rglob('*') if p.is_file()]


# ---------------------------------------------------------------------------
# Requirement 1
# ---------------------------------------------------------------------------


def test_it_finds_no_relay_daemon_references_in_readme_md():
    text = _text('README.md')
    assert 'relay daemon' not in text, 'README.md still contains "relay daemon"'


# ---------------------------------------------------------------------------
# Requirement 2
# ---------------------------------------------------------------------------


def test_it_finds_no_responder_broadcaster_archiver_references_in_mcp_tests():
    mcp_tests = PROJECT_ROOT / 'mcp' / 'tests'
    for path in mcp_tests.rglob('*.py'):
        text = path.read_text().lower()
        # Test function names are OK — only docstrings/comments are checked.
        # Strategy: exclude lines that are actual test function definitions,
        # then scan remaining lines for forbidden phrases.
        bad_lines = []
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('async def test_') or stripped.startswith('def test_'):
                continue  # function name itself is exempt
            for phrase in (
                'relay daemon',
                'relay archiver',
                'responder daemon',
                'broadcaster daemon',
            ):
                if phrase in line:
                    bad_lines.append(f'{path.name}:{lineno}: {line.strip()!r}')
        assert not bad_lines, 'Forbidden relay-daemon phrases in mcp/tests:\n' + '\n'.join(
            bad_lines
        )


# ---------------------------------------------------------------------------
# Requirement 3
# ---------------------------------------------------------------------------


def test_it_finds_no_relay_daemon_references_in_docs_except_plan_history():
    docs = PROJECT_ROOT / 'docs'
    plan_history = docs / 'plan-history'
    for path in docs.rglob('*.md'):
        if path.is_relative_to(plan_history):
            continue  # plan-history is explicitly exempt
        text = path.read_text().lower()
        assert 'relay daemon' not in text, (
            f'{path.relative_to(PROJECT_ROOT)} still contains "relay daemon"'
        )


# ---------------------------------------------------------------------------
# Requirement 4
# ---------------------------------------------------------------------------


def test_it_preserves_docs_plan_history_mentions_of_the_relay_daemon():
    texts = _plan_history_texts()
    assert any('relay daemon' in t for t in texts), (
        'docs/plan-history/ should retain "relay daemon" references as historical record'
    )


# ---------------------------------------------------------------------------
# Requirement 5
# ---------------------------------------------------------------------------


def test_it_allows_the_words_responder_and_broadcaster_to_appear_inside_docs_plan_history_files():
    texts = _plan_history_texts()
    assert any('responder' in t for t in texts), (
        'docs/plan-history/ should retain "responder" references as historical record'
    )
    assert any('broadcaster' in t for t in texts), (
        'docs/plan-history/ should retain "broadcaster" references as historical record'
    )
