# pb-chatroom — Project context for Claude Code sessions

This is a **Python project** that ships as a Claude Code plugin. It runs a self-hosted FastAPI service + MCP server backed by SQLite, plus accompanying slash commands and hooks, so multiple Claude sessions can coordinate over a local chatroom without an external service.

## Tech stack

- **Language**: Python 3.11+
- **Web framework**: FastAPI + uvicorn
- **Persistence**: SQLite (single file under `./data/`)
- **MCP server**: official `mcp` Python SDK with `streamable-http` transport
- **Tests**: pytest + pytest-asyncio + httpx (for FastAPI TestClient)
- **Lint / format**: ruff (line length 100, single-quoted strings) + pyright (basic mode)
- **Runtime**: docker-compose (two containers — `pb-chatroom-server`, `pb-chatroom-mcp`)

## Layout

```
pb-chatroom/
├── .claude/                         # HCF + pb-hcf wires (this dir)
├── .claude-plugin/                  # Plugin manifest (plugin.json, marketplace.json)
├── server/                          # The FastAPI REST + HTML service
│   ├── pyproject.toml
│   ├── src/pb_chatroom/             # Python module
│   └── tests/                       # pytest suite — TDD-first
├── mcp/                             # The MCP streamable-http server
├── commands/                        # Slash commands (chat-send, chat-threads, …)
├── hooks/                           # Stop-hook for live polling (Phase 2)
├── agents/                          # Agents that orchestrate chat-side work (Phase 3+)
├── docker-compose.yml               # Two-service stack (server + mcp)
├── LICENSE, NOTICE, README.md, .gitignore
```

## Core rules

1. **All data stays local.** The service binds to `127.0.0.1` only. DDEV containers reach it via `host.docker.internal`. Never bind a public port; never make outbound network calls beyond optional graphiti MCP for archival.
2. **SQLite is the single source of truth for live threads.** No second store, no caching layer.
3. **Subagent writes require `thread_id`.** Replies only — root-thread creation is parent-session only. Enforced in the MCP tool layer.
4. **No bundled third-party source.** All deps fetched at build time via pip; attribution in `NOTICE`.
5. **TDD discipline.** Each feature gets a failing test first; implementation passes the test; refactor cleans up. Run via the test command in `.claude/testing.md`.

## Per-domain playbooks (pb-hcf wires)

For domain-specific tooling and per-agent playbooks, consult the relevant file:

- **Knowledge graph** (discussions, decisions, planned features, prior incidents) → `@.claude/graphiti.md`
- **Security audit** (OWASP, vulnerability assessment of the chat service surface) → `@.claude/security.md`

GitNexus playbook is intentionally omitted — pb-chatroom is not a Magento project; the gitnexus code-graph index doesn't apply here.

## Detailed configuration

<testing>
@.claude/testing.md
</testing>

<pipeline>
@.claude/pipeline.md
</pipeline>
