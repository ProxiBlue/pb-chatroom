from __future__ import annotations

import json
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parents[2] / '.claude-plugin'
PLUGIN_JSON = PLUGIN_ROOT / 'plugin.json'
MARKETPLACE_JSON = PLUGIN_ROOT / 'marketplace.json'


def test_it_sets_plugin_json_version_to_0_4_0() -> None:
    data = json.loads(PLUGIN_JSON.read_text())
    assert data['version'] == '0.4.0'


def test_it_sets_marketplace_json_version_field_to_0_4_0() -> None:
    data = json.loads(MARKETPLACE_JSON.read_text())
    assert data['plugins'][0]['version'] == '0.4.0'


def test_it_preserves_all_other_plugin_json_fields() -> None:
    data = json.loads(PLUGIN_JSON.read_text())
    assert data['name'] == 'pb-chatroom'
    assert 'description' in data
    assert 'userConfig' in data
    assert 'chatroom_url' in data['userConfig']


def test_it_preserves_all_other_marketplace_json_fields() -> None:
    data = json.loads(MARKETPLACE_JSON.read_text())
    assert data['name'] == 'pb-chatroom'
    assert 'owner' in data
    assert data['owner']['email'] == 'lucas@proxiblue.com.au'
    plugin = data['plugins'][0]
    assert plugin['name'] == 'pb-chatroom'
    assert plugin['license'] == 'Apache-2.0'
    assert 'keywords' in plugin
