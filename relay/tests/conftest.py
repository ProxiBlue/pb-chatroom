"""Shared pytest fixtures for the pb-chatroom-relay suite."""

from __future__ import annotations

import pytest


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
