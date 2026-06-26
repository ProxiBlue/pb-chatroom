"""Structural (grep-based) tests for server/Dockerfile."""

from pathlib import Path


def dockerfile_text() -> str:
    return (Path(__file__).parent.parent / 'Dockerfile').read_text()


def test_it_exposes_port_7476():
    assert 'EXPOSE 7476' in dockerfile_text()


def test_it_defines_a_healthcheck_against_healthz():
    assert '/healthz' in dockerfile_text()
    assert 'HEALTHCHECK' in dockerfile_text()


def test_it_installs_the_package_and_its_runtime_deps_via_uv():
    text = dockerfile_text()
    assert 'uv' in text
    assert 'uv pip install' in text


def test_it_sets_the_uvicorn_command_as_the_container_entrypoint():
    assert 'uvicorn' in dockerfile_text()
    assert 'CMD' in dockerfile_text()


def test_it_does_not_COPY_the_tests_directory_into_the_image():
    text = dockerfile_text()
    # Must not contain a COPY directive that includes tests/
    import re

    copy_lines = [line for line in text.splitlines() if re.match(r'^\s*COPY', line)]
    for line in copy_lines:
        assert 'tests' not in line, f'Found COPY of tests dir: {line}'
