# Testing conventions

pb-chatroom uses pytest for the FastAPI service and the MCP wrapper. TDD is the expected workflow — tdd-worker writes a failing test first, then the minimum code to pass, then refactors.

## Where tests live

```
server/
└── tests/
    ├── conftest.py        # shared fixtures (TestClient, temp SQLite, fake clock)
    ├── test_messages.py   # POST /api/messages, GET /api/messages
    ├── test_threads.py    # GET /api/threads, GET /api/threads/{id}, /ack
    ├── test_identity.py   # $DDEV_PROJECT → container-X resolution
    └── ...
mcp/
└── tests/
    ├── conftest.py
    ├── test_chat_send.py
    ├── test_chat_list_threads.py
    └── ...
```

## How to run tests

Targeted (per-file or per-function) — preferred during TDD red/green/refactor:

```bash
cd server
uv run pytest tests/test_messages.py::test_post_message_creates_thread -xvs
```

Per-module (all tests in one file):

```bash
cd server
uv run pytest tests/test_messages.py -xvs
```

Full project suite (run at plan-end only, NOT per-task — parallel-collision risk on the SQLite store):

```bash
cd server && uv run pytest -xvs && cd ../mcp && uv run pytest -xvs
```

## Parallel-test discipline

tdd-worker MUST scope test invocations to **targeted tests only** (per file or per test function), NOT the full suite. Reason: HCF spawns workers in parallel and a full-suite run from each worker collides on the shared SQLite file. The orchestrator runs the full suite ONCE at plan-end, after all worker tasks complete.

If a test needs the SQLite store, fixture-provide it via a per-test temp dir (`tmp_path` fixture). No shared global DB across tests.

## Conventions

- Use `pytest.fixture` for setup; never test-class inheritance.
- Use `httpx.AsyncClient` against the FastAPI app for HTTP-level tests, not `requests`.
- Use `pytest-asyncio` mode `auto` so async tests are picked up automatically.
- For time-sensitive logic (message timestamps, thread sort order), inject a fake clock fixture rather than `time.sleep`.
- Coverage target: 90%+ on the `pb_chatroom` module. The MCP wrapper gets thinner coverage (it's mostly a tool definition layer) — focus tests there on the "subagent write requires thread_id" enforcement.

## Test isolation

Every test gets a fresh SQLite file via the `tmp_path` fixture. No `--reuse-db` or singleton DB. Worker parallel safety relies on this.

## When NOT to run tests

- During plan-create — that's design, not implementation.
- Inside the MCP server runtime — the server is the thing being tested, not the runner.
- Against the production-running compose stack — tests use the TestClient, not network calls to a running service.
