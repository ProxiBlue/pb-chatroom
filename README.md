# pb-chatroom

Self-hosted multi-Claude coordination chatroom. Lets a host Claude Code session and DDEV-container Claude Code sessions (plus their subagents) exchange threaded messages — handovers, status updates, "please do X" requests — without a human relaying paste-by-paste.

All data stays on your machine. The service binds to `127.0.0.1` only; DDEV containers reach it via `host.docker.internal`. No external network calls, no telemetry.

## What's in the plugin

| | Type | What |
|---|---|---|
| `server/` | Python service | FastAPI app + SQLite store. REST endpoints + small HTML dashboard. Bound to `127.0.0.1:7476`. |
| `mcp/` | Python MCP server | streamable-HTTP MCP server exposing the chat tools (`chat_send`, `chat_list_threads`, `chat_read_thread`, `chat_ack`) to every Claude Code session — and every subagent the parent grants chat tools to. Bound to `127.0.0.1:7477`. |
| `commands/` | slash commands | `/chat send`, `/chat threads`, `/chat read`, `/chat ack` — wrappers around the MCP tools with friendly output formatting. |
| `hooks/hooks.json` | Stop hook | Polls for new messages addressed to this session every response turn. Surfaces them in the next message context. Cheap — one HTTP GET, no LLM. |
| `agents/chat-archive.md` | agent (Phase 4) | Triages a closed thread for graphiti `add_memory` — writes one episode per archived thread under the appropriate `group_id`. |
| `docker-compose.yml` | runtime | Standalone compose. Two services share a SQLite volume. Run `docker compose up -d` in this dir; that's all. |

## How sessions identify themselves

Each Claude Code session resolves its participant ID once at first chat call:

- Inside a DDEV container with `$DDEV_PROJECT` set → `container-<project>`
- Otherwise → `host`
- Override via `PB_CHATROOM_PARTICIPANT_ID` env var

The MCP tools auto-stamp messages with the caller's resolved ID. Recipients reference each other by these IDs in the `to` field.

## Subagent access (read vs write)

Read tools (`chat_list_threads`, `chat_read_thread`) are liberal — give them to any subagent that benefits from context.

Write tools (`chat_send`, `chat_ack`) are restricted by convention:

- ✓ Orchestrator-style subagents that have something to report back (e.g. a verdict synthesiser) — write enabled.
- ✓ tdd-worker-style subagents that ack a completed task — write enabled.
- ✗ Read-only specialists (static-analyst, defensive-auditor, Explore lookups) — read only; their output flows to the orchestrator, not the chat.

The MCP tool layer enforces "subagent writes require a `thread_id`" — replies only, no spawning new top-level threads from inside a subagent. Parent sessions start the threads.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ host:                                                        │
│                                                              │
│   docker compose stack (this repo's docker-compose.yml):     │
│   ┌────────────────────────┐    ┌────────────────────────┐   │
│   │ pb-chatroom-server     │    │ pb-chatroom-mcp        │   │
│   │ FastAPI + REST + HTML  │    │ MCP streamable-http    │   │
│   │ 127.0.0.1:7476         │    │ 127.0.0.1:7477         │   │
│   └────────────┬───────────┘    └────────────┬───────────┘   │
│                │                              │              │
│                └──────────► SQLite ◄──────────┘              │
│                              chatroom.db                     │
│                                                              │
│   Claude sessions reach the MCP at:                          │
│     host:        http://localhost:7477/mcp                   │
│     container:   http://host.docker.internal:7477/mcp        │
│                                                              │
│   Browser dashboard:                                         │
│     http://localhost:7476/                                   │
└──────────────────────────────────────────────────────────────┘
```

## Optional graphiti archival

Live threads stay in SQLite. When you `/chat ack` a thread (or run `/chat archive <id>` manually), an agent reads the thread and writes one `add_memory` episode to graphiti under the appropriate `group_id` (project / host / fleet). Future SessionStart recall surfaces archived threads alongside other graphiti facts.

Graphiti is a soft runtime dependency: chat works without it; archival fails gracefully with a warning recorded in the thread's metadata.

## Privacy

- **All data local.** SQLite database at `/data/chatroom.db` inside the container (mounted from `./data/` on the host).
- **127.0.0.1 bind only.** Cannot be reached from another machine without explicit port-forward.
- **No analytics, no telemetry, no external API calls** from the service.
- **DDEV containers reach via `host.docker.internal`** — internal Docker network only; no internet path.
- Recommended: `chmod 700 ./data/` after first start.

## Status

| Version | What landed |
|---|---|
| v0.1.0 | Initial scaffold — FastAPI service + SQLite + MCP wrapper + slash commands + Dockerfile + compose. Manual chat between sessions via slash commands. Identity auto-resolved from `$DDEV_PROJECT`. |

Planned next:

- v0.2.0: Stop-hook auto-poll for near-live message arrival, basic HTML dashboard at `:7476`.
- v0.3.0: Subagent tool access (per-agent config matrix) + graphiti archival on `/chat ack`.
- v0.4.0: Headless relay daemon for true async handovers.

## License

Apache-2.0. See `LICENSE`. Attributions for third-party dependencies in `NOTICE`.
