"""Tests asserting relay service has been removed from docker-compose.yml."""

from __future__ import annotations

from pathlib import Path

import yaml

COMPOSE_FILE = Path(__file__).parent.parent.parent / 'docker-compose.yml'

# Snapshot of expected server service block (pre-relay-rip state, unchanged).
_EXPECTED_SERVER = {
    'build': './server',
    'ports': ['7476:7476'],
    'volumes': ['./data:/data'],
    'environment': {'PB_CHATROOM_DB_PATH': '/data/chatroom.db'},
    'restart': 'unless-stopped',
    'healthcheck': {
        'test': ['CMD', 'curl', '-fsS', 'http://127.0.0.1:7476/healthz'],
        'interval': '10s',
        'timeout': '3s',
        'retries': 3,
    },
}

# Snapshot of expected mcp service block (pre-relay-rip state, unchanged).
_EXPECTED_MCP = {
    'build': './mcp',
    'ports': ['7477:7477'],
    'environment': {'PB_CHATROOM_SERVER_URL': 'http://server:7476'},
    'depends_on': {'server': {'condition': 'service_healthy'}},
    'restart': 'unless-stopped',
}


def _load() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text())


def test_it_does_not_declare_a_relay_service() -> None:
    cfg = _load()
    assert 'relay' not in cfg.get('services', {})


def test_it_does_not_declare_a_relay_profile() -> None:
    raw = COMPOSE_FILE.read_text()
    assert 'profiles:' not in raw


def test_it_preserves_the_server_service_block() -> None:
    cfg = _load()
    assert cfg['services']['server'] == _EXPECTED_SERVER


def test_it_preserves_the_mcp_service_block() -> None:
    cfg = _load()
    assert cfg['services']['mcp'] == _EXPECTED_MCP


def test_it_does_not_reference_relay_responders_json_as_a_bind_mount() -> None:
    raw = COMPOSE_FILE.read_text()
    assert 'relay/responders.json' not in raw


def test_it_does_not_reference_relay_state_as_a_bind_mount() -> None:
    raw = COMPOSE_FILE.read_text()
    assert 'relay/state' not in raw
