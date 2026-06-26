from __future__ import annotations

import json
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent.parent.parent / 'examples'
CONFIG_FILE = EXAMPLES_DIR / 'claudeclaw-host-auto.json'


def load_config() -> dict:
    return json.loads(CONFIG_FILE.read_text())


def test_it_is_valid_json():
    assert CONFIG_FILE.exists(), f'File not found: {CONFIG_FILE}'
    data = load_config()
    assert isinstance(data, dict)


def test_it_declares_a_host_auto_identity_in_the_identity_or_participant_block():
    data = load_config()
    identity = data.get('identity') or data.get('participant', {}).get('id', '')
    assert identity == 'host-auto'


def test_it_sets_a_heartbeat_interval_of_5_minutes():
    data = load_config()
    assert data['heartbeat']['intervalMinutes'] == 5


def test_it_restricts_heartbeat_to_local_hours_8_through_19():
    data = load_config()
    hb = data['heartbeat']
    assert hb['activeWindowStart'] == '08:00'
    assert hb['activeWindowEnd'] == '19:00'


def test_it_sets_max_invocations_per_hour_to_20():
    data = load_config()
    assert data['budget']['maxInvocationsPerHour'] == 20


def test_it_sets_max_invocations_per_day_to_100():
    data = load_config()
    assert data['budget']['maxInvocationsPerDay'] == 100


def test_it_enables_glm_fallback():
    data = load_config()
    assert data['glmFallback'] is True


def test_it_sets_allowed_user_ids_to_an_empty_array():
    data = load_config()
    assert data['allowedUserIds'] == []


def test_it_references_the_pb_chatroom_mcp_url_via_host_docker_internal_port_7477():
    data = load_config()
    servers = data['mcp']['servers']
    chatroom = servers['pb-chatroom']
    assert 'host.docker.internal:7477' in chatroom['url']
    assert chatroom['url'].endswith('/mcp')
