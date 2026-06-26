"""Tests for pb_chatroom_relay.config — pydantic models + JSON loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pb_chatroom_relay.config import load_responders_config

EXAMPLE_JSON = Path(__file__).parent.parent / 'examples' / 'responders.example.json'


def test_it_loads_the_example_responders_json_file_without_validation_errors():
    config = load_responders_config(EXAMPLE_JSON)
    assert config is not None


def test_it_parses_responder_claude_invocation_block_with_cwd_model_extra_args_system_prompt_addendum():  # noqa: E501
    config = load_responders_config(EXAMPLE_JSON)
    invocation = config.responders['host-auto'].claude_invocation
    assert invocation.cwd == '/home/lucas/workspace'
    assert invocation.model == 'claude-haiku-4-5-20251001'
    assert invocation.extra_args == ['--allowed-tools', 'Read,Bash,chat_send,chat_ack']
    assert 'autonomous chatroom triage responder' in invocation.system_prompt_addendum


def test_it_parses_broadcaster_active_window_with_start_hour_local_and_end_hour_local():
    config = load_responders_config(EXAMPLE_JSON)
    window = config.broadcasters['idle_check_in'].active_window
    assert window is not None
    assert window.start_hour_local == 8
    assert window.end_hour_local == 19


def test_it_parses_archiver_group_id_map_with_literal_keys_and_wildcard_keys():
    config = load_responders_config(EXAMPLE_JSON)
    gmap = config.archivers['default'].group_id_map
    assert gmap['host'] == 'host'
    assert gmap['host-*'] == 'host'
    assert gmap['container-*'] == '<strip-container-prefix>'


def test_it_raises_a_validation_error_when_broadcaster_active_window_hour_is_outside_0_23(
    tmp_responders_path,
):
    data = {
        'responders': {},
        'broadcasters': {
            'bad_window': {
                'enabled': True,
                'active_window': {'start_hour_local': 25, 'end_hour_local': 8},
            }
        },
        'archivers': {},
    }
    tmp_responders_path.write_text(json.dumps(data))
    with pytest.raises(ValidationError):
        load_responders_config(tmp_responders_path)


def test_it_raises_a_validation_error_when_responder_budget_max_invocations_per_hour_is_negative(
    tmp_responders_path,
):
    data = {
        'responders': {
            'bad_responder': {
                'trigger': {'from_pattern': '*', 'subject_keywords': []},
                'claude_invocation': {
                    'cwd': '/tmp', 'model': 'x', 'extra_args': [], 'system_prompt_addendum': ''
                },
                'budget': {'max_invocations_per_hour': -1, 'max_invocations_per_day': 10},
                'archive_on_ack': False,
            }
        },
        'broadcasters': {},
        'archivers': {},
    }
    tmp_responders_path.write_text(json.dumps(data))
    with pytest.raises(ValidationError):
        load_responders_config(tmp_responders_path)


def test_it_ignores_underscore_prefixed_comment_keys_doc_comment_rotation_group_id_map(
    tmp_responders_path,
):
    data = {
        '_documentation': 'top-level comment — should be ignored',
        'responders': {
            '_doc': 'section comment — should be ignored',
            'host-auto': {
                'trigger': {'from_pattern': '*', 'subject_keywords': []},
                'claude_invocation': {
                    'cwd': '/tmp', 'model': 'x', 'extra_args': [], 'system_prompt_addendum': ''
                },
                'budget': {'max_invocations_per_hour': 5, 'max_invocations_per_day': 20},
                'archive_on_ack': False,
            },
        },
        'broadcasters': {
            'idle_check_in': {
                'enabled': True,
                '_rotation': 'future rotation note — should be ignored',
                'active_window': {'start_hour_local': 8, 'end_hour_local': 19},
                'broadcast_to': [],
                'prompt_subject': 's',
                'prompt_body': 'b',
            }
        },
        'archivers': {
            '_doc': 'archiver comment — should be ignored',
            'default': {
                'enabled': True,
                'graphiti_group_id_resolution': 'none',
                '_group_id_map': {'host': 'host'},
                '_comment': 'another comment — should be ignored',
                'max_thread_chars': 1000,
                'exclude_test_subjects': [],
            },
        },
    }
    tmp_responders_path.write_text(json.dumps(data))
    # Must not raise — all underscore keys silently dropped
    config = load_responders_config(tmp_responders_path)
    assert 'host-auto' in config.responders
    assert config.archivers['default'].group_id_map == {'host': 'host'}
