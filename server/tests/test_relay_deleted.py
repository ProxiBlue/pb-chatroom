from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
RELAY_ROOT = PROJECT_ROOT / 'relay'


def test_it_removes_the_relay_directory_entirely():
    assert not RELAY_ROOT.exists(), f'relay/ still exists at {RELAY_ROOT}'


def test_it_removes_relay_src_module_from_the_working_tree():
    assert not (RELAY_ROOT / 'src').exists(), f'relay/src still exists at {RELAY_ROOT / "src"}'


def test_it_removes_relay_tests_from_the_working_tree():
    assert not (RELAY_ROOT / 'tests').exists(), f'relay/tests still exists at {RELAY_ROOT / "tests"}'


def test_it_removes_relay_dockerfile_from_the_working_tree():
    assert not (RELAY_ROOT / 'Dockerfile').exists(), 'relay/Dockerfile still exists'


def test_it_removes_relay_pyproject_toml_from_the_working_tree():
    assert not (RELAY_ROOT / 'pyproject.toml').exists(), 'relay/pyproject.toml still exists'
