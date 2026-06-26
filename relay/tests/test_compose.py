from __future__ import annotations

from pathlib import Path

import pytest
import yaml

COMPOSE_PATH = Path(
    '/home/lucas/claude-plugins-central/seed/marketplaces/pb-chatroom/docker-compose.yml'
)


@pytest.fixture
def compose():
    return yaml.safe_load(COMPOSE_PATH.read_text())


def test_it_adds_a_relay_service_block_to_docker_compose_yml(compose):
    assert 'relay' in compose['services']


def test_it_puts_the_relay_service_under_the_relay_profile(compose):
    assert compose['services']['relay']['profiles'] == ['relay']


def test_it_mounts_relay_responders_json_read_only(compose):
    volumes = compose['services']['relay']['volumes']
    assert any('responders.json' in v and ':ro' in v for v in volumes)


def test_it_mounts_relay_state_directory_read_write(compose):
    volumes = compose['services']['relay']['volumes']
    assert any('state' in v and ':ro' not in v for v in volumes)


def test_it_sets_depends_on_server_and_mcp_with_condition_service_healthy(compose):
    depends_on = compose['services']['relay']['depends_on']
    assert depends_on['server']['condition'] == 'service_healthy'
    assert depends_on['mcp']['condition'] == 'service_healthy'


def test_it_has_a_healthcheck_pointing_at_port_8000_healthz_inside_the_container(compose):
    hc = compose['services']['relay']['healthcheck']
    assert any('8000' in str(item) and 'healthz' in str(item) for item in hc['test'])


def test_it_sets_restart_unless_stopped_to_match_the_other_services(compose):
    assert compose['services']['relay']['restart'] == 'unless-stopped'
