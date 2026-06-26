"""Shared pytest fixtures for the pb-chatroom-relay suite."""

from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption(
        '--run-e2e',
        action='store_true',
        default=False,
        help='Run e2e docker-compose tests',
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption('--run-e2e'):
        skip_e2e = pytest.mark.skip(reason='Pass --run-e2e to run e2e tests')
        for item in items:
            if 'e2e' in item.keywords:
                item.add_marker(skip_e2e)


@pytest.fixture
def tmp_responders_path(tmp_path):
    """Per-test responders.json — keeps fixtures isolated under parallel HCF
    workers. Tests write whatever YAML / JSON they need to this path.
    """
    return tmp_path / 'responders.json'


@pytest.fixture
def tmp_state_dir(tmp_path):
    """Per-test cursor / state directory."""
    d = tmp_path / 'state'
    d.mkdir()
    return d
