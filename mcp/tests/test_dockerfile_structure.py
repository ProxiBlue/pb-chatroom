"""Structural (grep-based) tests for mcp/Dockerfile."""

import re
from pathlib import Path


def dockerfile_text() -> str:
    return (Path(__file__).parent.parent / 'Dockerfile').read_text()


def test_it_exposes_port_7477():
    assert 'EXPOSE 7477' in dockerfile_text()


def test_it_defines_a_healthcheck():
    assert 'HEALTHCHECK' in dockerfile_text()


def test_it_installs_the_package_and_its_runtime_deps_via_uv():
    text = dockerfile_text()
    assert 'uv' in text
    assert 'uv pip install' in text


def test_it_runs_the_pb_chatroom_mcp_server_module_as_the_entrypoint():
    text = dockerfile_text()
    assert 'pb_chatroom_mcp.server' in text
    assert 'CMD' in text


def test_it_does_not_COPY_the_tests_directory_into_the_image():
    text = dockerfile_text()
    copy_lines = [line for line in text.splitlines() if re.match(r'^\s*COPY', line)]
    for line in copy_lines:
        assert 'tests' not in line, f'Found COPY of tests dir: {line}'
