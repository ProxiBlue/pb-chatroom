from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
DOCS_PLAN_HISTORY = PROJECT_ROOT / 'docs' / 'plan-history'
RELAY_DIR = PROJECT_ROOT / 'relay'


def test_it_places_the_v0_3_0_brief_under_docs_plan_history():
    assert (DOCS_PLAN_HISTORY / 'v0_3_0.md').exists()


def test_it_places_the_v0_4_0_original_brief_under_docs_plan_history():
    assert (DOCS_PLAN_HISTORY / 'v0_4_0-original.md').exists()


def test_it_places_the_v0_4_0_revised_brief_under_docs_plan_history():
    assert (DOCS_PLAN_HISTORY / 'v0_4_0-revised.md').exists()


def test_it_removes_the_original_brief_locations_under_relay():
    assert not (RELAY_DIR / 'HCF_PLAN_BRIEF.md').exists()
    assert not (RELAY_DIR / 'HCF_PLAN_BRIEF.v0.3.0.md').exists()
    assert not (RELAY_DIR / 'HCF_PLAN_BRIEF.v0.4.0-original.md').exists()


def test_it_adds_a_docs_plan_history_readme_indexing_the_three_briefs_in_date_order():
    readme = DOCS_PLAN_HISTORY / 'README.md'
    assert readme.exists()
    content = readme.read_text()
    assert 'v0_3_0.md' in content
    assert 'v0_4_0-original.md' in content
    assert 'v0_4_0-revised.md' in content
