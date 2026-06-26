from __future__ import annotations

from pathlib import Path

import pytest

DOCKERFILE = Path('/home/lucas/claude-plugins-central/seed/marketplaces/pb-chatroom/relay/Dockerfile')


@pytest.fixture
def dockerfile_text():
    return DOCKERFILE.read_text()


def test_it_has_from_python_3_11_slim_as_the_base_image(dockerfile_text):
    assert 'FROM python:3.11-slim' in dockerfile_text


def test_it_installs_the_claude_cli_binary_in_a_layer_before_the_relay_package(dockerfile_text):
    claude_idx = dockerfile_text.index('claude-code')
    relay_idx = dockerfile_text.index('pip install')
    assert claude_idx < relay_idx


def test_it_copies_the_relay_package_and_installs_it_via_pip(dockerfile_text):
    assert 'pip install' in dockerfile_text


def test_it_exposes_port_8000_for_the_healthcheck(dockerfile_text):
    assert 'EXPOSE 8000' in dockerfile_text


def test_it_sets_the_cmd_to_invoke_pb_chatroom_relay_run(dockerfile_text):
    assert 'pb-chatroom-relay' in dockerfile_text
    assert 'run' in dockerfile_text
