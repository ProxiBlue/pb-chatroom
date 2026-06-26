"""Tests for pb_chatroom.identity — participant ID resolution."""

from __future__ import annotations

import pytest

from pb_chatroom.identity import resolve_participant_id


def test_it_returns_host_when_no_relevant_env_vars_are_set(monkeypatch):
    monkeypatch.delenv('PB_CHATROOM_PARTICIPANT_ID', raising=False)
    monkeypatch.delenv('DDEV_PROJECT', raising=False)
    assert resolve_participant_id() == 'host'


def test_it_returns_container_project_when_ddev_project_is_set(monkeypatch):
    monkeypatch.delenv('PB_CHATROOM_PARTICIPANT_ID', raising=False)
    monkeypatch.setenv('DDEV_PROJECT', 'acme')
    assert resolve_participant_id() == 'container-acme'


def test_it_returns_pb_chatroom_participant_id_verbatim_when_set_ignoring_ddev_project(monkeypatch):
    monkeypatch.setenv('PB_CHATROOM_PARTICIPANT_ID', 'my-agent')
    monkeypatch.setenv('DDEV_PROJECT', 'acme')
    assert resolve_participant_id() == 'my-agent'


def test_it_lower_cases_mixed_case_ddev_project_values(monkeypatch):
    monkeypatch.delenv('PB_CHATROOM_PARTICIPANT_ID', raising=False)
    monkeypatch.setenv('DDEV_PROJECT', 'AcmeCorp')
    assert resolve_participant_id() == 'container-acmecorp'


def test_it_raises_value_error_for_ids_containing_characters_outside_a_z0_9__(monkeypatch):
    monkeypatch.setenv('PB_CHATROOM_PARTICIPANT_ID', 'bad id!')
    with pytest.raises(ValueError, match=r'\[a-z0-9_-\]'):
        resolve_participant_id()


def test_it_raises_value_error_for_ids_longer_than_64_characters(monkeypatch):
    monkeypatch.setenv('PB_CHATROOM_PARTICIPANT_ID', 'a' * 65)
    with pytest.raises(ValueError, match='64'):
        resolve_participant_id()
