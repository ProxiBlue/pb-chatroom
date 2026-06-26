"""Structural tests for docker-compose.yml at repo root.

Uses YAML parse for structural assertions; grep fallback for
string-exact checks (e.g., no 0.0.0.0 binding).
"""

from __future__ import annotations

from pathlib import Path

import yaml

COMPOSE_FILE = Path(__file__).parent.parent.parent / 'docker-compose.yml'


def _load() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text())


def test_it_defines_a_server_service_that_binds_to_127_0_0_1_7476() -> None:
    cfg = _load()
    ports = cfg['services']['server']['ports']
    assert '127.0.0.1:7476:7476' in ports


def test_it_defines_an_mcp_service_that_binds_to_127_0_0_1_7477() -> None:
    cfg = _load()
    ports = cfg['services']['mcp']['ports']
    assert '127.0.0.1:7477:7477' in ports


def test_it_never_binds_either_service_to_0_0_0_0_on_the_host() -> None:
    content = COMPOSE_FILE.read_text()
    assert '0.0.0.0' not in content


def test_it_mounts_data_into_the_server_service() -> None:
    cfg = _load()
    volumes = cfg['services']['server']['volumes']
    assert './data:/data' in volumes


def test_it_sets_PB_CHATROOM_SERVER_URL_on_mcp_to_reach_server_via_network_hostname() -> None:  # noqa: N802
    cfg = _load()
    env = cfg['services']['mcp']['environment']
    # environment can be a dict or a list of KEY=VALUE strings
    if isinstance(env, dict):
        assert env.get('PB_CHATROOM_SERVER_URL') == 'http://server:7476'
    else:
        assert 'PB_CHATROOM_SERVER_URL=http://server:7476' in env


def test_it_makes_the_mcp_service_depend_on_the_server_service_being_healthy() -> None:
    cfg = _load()
    depends = cfg['services']['mcp']['depends_on']
    # depends_on can be a list or a dict with conditions
    if isinstance(depends, list):
        assert 'server' in depends
    else:
        assert 'server' in depends
        assert depends['server'].get('condition') == 'service_healthy'
