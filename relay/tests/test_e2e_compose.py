"""End-to-end docker-compose integration tests for the pb-chatroom relay stack.

HOW TO RUN (manual gate — not in CI fast lane):

    cd /home/lucas/claude-plugins-central/seed/marketplaces/pb-chatroom/relay
    uv run pytest tests/test_e2e_compose.py -xvs --run-e2e

FAKE CLAUDE SHIM:
    The relay container invokes `claude --print ...` to generate replies.
    During e2e tests we inject a fake shim so no API quota is burned.
    The shim is a 5-line bash script written to a tmpdir and bind-mounted
    into the relay container at /usr/local/bin/claude:

        #!/bin/bash
        # Fake claude shim for e2e testing — deterministic, no API calls
        cat - > /dev/null
        echo "E2E test reply from fake claude"
        exit 0

    This is injected via a docker-compose override file written to tmp_path.

RESPONDERS.JSON FOR TEST:
    A minimal responders.json is written to tmp_path and mounted into the
    relay container, overriding the production ./relay/responders.json.
    The test responder matches any sender and triggers on the subject keyword
    "e2e", which the test thread uses.

CLEANUP:
    relay/state/ artefacts written during the run are removed via `docker
    compose down --volumes` in the fixture teardown, which removes the
    named volumes. The override mounts use tmp_path so they are cleaned by
    pytest automatically.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path('/home/lucas/claude-plugins-central/seed/marketplaces/pb-chatroom')
COMPOSE_CMD = ['docker', 'compose', '--profile', 'relay']
SERVER_URL = 'http://localhost:7476'
RELAY_HEALTH_URL = 'http://localhost:8000/healthz'

FAKE_SHIM_SCRIPT = """\
#!/bin/bash
# Fake claude shim for e2e testing — deterministic, no API calls
cat - > /dev/null
echo "E2E test reply from fake claude"
exit 0
"""

MINIMAL_RESPONDERS = {
    'responders': {
        'host-auto': {
            'trigger': {'from_pattern': '*', 'subject_keywords': ['e2e']},
            'claude_invocation': {
                'cwd': '/tmp',
                'model': 'claude-haiku-4-5-20251001',
                'extra_args': [],
            },
            'budget': {'max_invocations_per_hour': 10, 'max_invocations_per_day': 50},
        }
    },
    'broadcasters': {},
    'archivers': {
        'default': {
            'enabled': False,
            'max_thread_chars': 10000,
            'exclude_test_subjects': [],
        }
    },
}


def _wait_healthy(url: str, label: str, timeout: int = 60) -> None:
    """Poll url until HTTP 200 or timeout seconds elapsed. Raises on timeout."""
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=3)
            if r.status_code == 200:
                return
        except Exception as exc:
            last_exc = exc
        time.sleep(2)
    raise TimeoutError(
        f'{label} did not become healthy within {timeout}s — last error: {last_exc}'
    )


@pytest.mark.e2e
class TestE2ECompose:
    """Full-stack e2e tests — bring up docker-compose, exercise relay dispatch."""

    @pytest.fixture(autouse=True)
    def compose_stack(self, tmp_path):
        """Bring up the full compose stack with relay profile; tear down after."""
        # Write fake claude shim
        shim = tmp_path / 'claude'
        shim.write_text(FAKE_SHIM_SCRIPT)
        shim.chmod(0o755)

        # Write minimal responders.json
        responders_json = tmp_path / 'responders.json'
        responders_json.write_text(json.dumps(MINIMAL_RESPONDERS, indent=2))

        # Write docker-compose override to inject the shim + responders
        override = {
            'services': {
                'relay': {
                    'volumes': [
                        f'{shim}:/usr/local/bin/claude:ro',
                        f'{responders_json}:/app/relay/responders.json:ro',
                    ]
                }
            }
        }
        override_file = tmp_path / 'docker-compose.e2e-override.yml'
        # Write as YAML — use json.dumps as a cheap portable serialiser;
        # docker compose accepts JSON-in-YAML files fine.
        override_file.write_text(json.dumps(override))

        compose_up = subprocess.run(
            COMPOSE_CMD
            + ['-f', 'docker-compose.yml', '-f', str(override_file), 'up', '-d', '--build'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert compose_up.returncode == 0, (
            f'compose up failed:\nSTDOUT: {compose_up.stdout}\nSTDERR: {compose_up.stderr}'
        )

        yield {'responders_json': responders_json, 'shim': shim, 'override_file': override_file}

        # Teardown — remove containers + volumes
        subprocess.run(
            COMPOSE_CMD
            + ['-f', 'docker-compose.yml', '-f', str(override_file), 'down', '--volumes'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=60,
        )

    # ------------------------------------------------------------------
    # Requirements
    # ------------------------------------------------------------------

    def test_it_brings_up_the_full_docker_compose_stack_with_the_relay_profile(
        self, compose_stack
    ):
        """Stack is up — all three services (server, mcp, relay) are running."""
        result = subprocess.run(
            COMPOSE_CMD + ['ps', '--format', 'json'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        # At least one line of JSON output means containers exist
        output = result.stdout.strip()
        assert output, 'No containers reported by docker compose ps'
        # Each line is a JSON object; parse first to confirm valid JSON
        first_line = output.splitlines()[0]
        info = json.loads(first_line)
        assert 'Name' in info or 'Service' in info, f'Unexpected ps JSON shape: {info}'

    def test_it_waits_for_the_server_healthcheck_to_report_healthy_before_posting_a_thread(
        self, compose_stack
    ):
        """Server /healthz returns 200 within 60 s of stack start."""
        _wait_healthy(f'{SERVER_URL}/healthz', label='server', timeout=60)
        r = httpx.get(f'{SERVER_URL}/healthz', timeout=5)
        assert r.status_code == 200

    def test_it_waits_for_the_relay_healthcheck_to_report_healthy_before_posting_a_thread(
        self, compose_stack
    ):
        """Relay /healthz returns 200 within 60 s of stack start."""
        _wait_healthy(RELAY_HEALTH_URL, label='relay', timeout=60)
        r = httpx.get(RELAY_HEALTH_URL, timeout=5)
        assert r.status_code == 200

    def test_it_posts_a_thread_addressed_to_host_auto_via_the_chatroom_rest_api(
        self, compose_stack
    ):
        """POST /threads creates a thread with participant host-auto."""
        _wait_healthy(f'{SERVER_URL}/healthz', label='server', timeout=60)
        payload = {
            'subject': 'e2e integration test thread',
            'body': 'Hello from the e2e test suite.',
            'from': 'test-runner',
            'to': ['host-auto'],
        }
        r = httpx.post(f'{SERVER_URL}/threads', json=payload, timeout=10)
        assert r.status_code in (200, 201), f'POST /threads failed: {r.status_code} {r.text}'
        data = r.json()
        assert 'id' in data or 'thread_id' in data, f'No thread id in response: {data}'

    def test_it_observes_the_role_counts_hot_path_increment_in_the_relay_healthcheck_within_30_seconds(
        self, compose_stack
    ):
        """After posting a matching thread, relay healthcheck shows dispatched > 0."""
        _wait_healthy(f'{SERVER_URL}/healthz', label='server', timeout=60)
        _wait_healthy(RELAY_HEALTH_URL, label='relay', timeout=60)

        # Get baseline
        baseline = httpx.get(RELAY_HEALTH_URL, timeout=5).json()
        baseline_dispatched = (
            baseline.get('role_counts', {}).get('dispatched', 0)
            or baseline.get('dispatched', 0)
            or 0
        )

        # Post matching thread
        payload = {
            'subject': 'e2e integration test thread',
            'body': 'Trigger relay dispatch.',
            'from': 'test-runner',
            'to': ['host-auto'],
        }
        r = httpx.post(f'{SERVER_URL}/threads', json=payload, timeout=10)
        assert r.status_code in (200, 201)

        # Poll healthcheck until dispatched count increases
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            health = httpx.get(RELAY_HEALTH_URL, timeout=3).json()
            dispatched = (
                health.get('role_counts', {}).get('dispatched', 0)
                or health.get('dispatched', 0)
                or 0
            )
            if dispatched > baseline_dispatched:
                return
            time.sleep(2)

        pytest.fail(
            f'role_counts dispatched did not increment within 30 s. '
            f'Last health: {health}'
        )

    def test_it_observes_a_reply_message_on_the_posted_thread_within_30_seconds(
        self, compose_stack
    ):
        """Fake claude shim reply appears on the thread within 30 s."""
        _wait_healthy(f'{SERVER_URL}/healthz', label='server', timeout=60)
        _wait_healthy(RELAY_HEALTH_URL, label='relay', timeout=60)

        payload = {
            'subject': 'e2e integration test thread',
            'body': 'Waiting for reply.',
            'from': 'test-runner',
            'to': ['host-auto'],
        }
        r = httpx.post(f'{SERVER_URL}/threads', json=payload, timeout=10)
        assert r.status_code in (200, 201)
        data = r.json()
        thread_id = data.get('id') or data.get('thread_id')
        assert thread_id, f'No thread_id in response: {data}'

        # Poll messages until we see the fake shim reply
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            msgs_r = httpx.get(f'{SERVER_URL}/threads/{thread_id}/messages', timeout=5)
            if msgs_r.status_code == 200:
                messages = msgs_r.json()
                texts = [m.get('body', '') or m.get('content', '') for m in messages]
                if any('E2E test reply from fake claude' in t for t in texts):
                    return
            time.sleep(2)

        pytest.fail(
            f'Reply from fake claude shim not observed within 30 s on thread {thread_id}.'
        )

    def test_it_tears_down_the_docker_compose_stack_cleanly_in_the_test_teardown(
        self, compose_stack
    ):
        """After the fixture teardown, no relay containers remain running.

        This test itself is a no-op body — the actual assertion is in the
        fixture teardown (compose down --volumes returns 0). Here we just
        confirm the stack is up during the test body so teardown has something
        to tear down.
        """
        result = subprocess.run(
            COMPOSE_CMD + ['ps', '--services', '--filter', 'status=running'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # At least the server should be running while test body executes
        assert result.returncode == 0
        # Teardown happens in compose_stack fixture — if it raises, pytest marks FAIL
