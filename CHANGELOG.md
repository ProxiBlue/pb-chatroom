# Changelog

All notable changes to pb-chatroom are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- **`/chat ask-peer` (`commands/chat-ask-peer.md`)** — REST equivalent of the MCP-only `chat_ask_peer` tool: graphiti-first lookup (direct graphiti tool call, score >= 0.6 short-circuits with no thread) falling back to a `POST /api/threads` design_question thread via curl + `X-PB-Chatroom-Participant`, closing the last MCP-only gap noted in 0.4.1.
- **Dashboard ack button** — the per-thread view renders an `ack` button on open threads. It POSTs to `/api/threads/{id}/ack` as the seed message's recipient (the participant the ack is owed from), so an operator can acknowledge a thread from the web UI. Single-recipient threads close immediately; multi-recipient (broadcast) threads record that recipient's ack and close once all recipients have acked.

---

## [0.4.1] — 2026-08-06

### Fixed

- **MCP identity attribution — dropped MCP as the default interface.** The MCP server was registered as a single shared `type: http` process (`host.docker.internal:7477`), not a per-session local subprocess. Its `resolve_participant_id()` read `$DDEV_PROJECT`/`$PB_CHATROOM_PARTICIPANT_ID` from that one process's own environment, which never carries a caller's env — every MCP-routed `chat_send`/`chat_ack`, from any container, silently attributed as `host`. Found live on 2026-08-06: a container session replied to and then acked (closed) its own proposal thread, entirely under the `host` identity, with the host never having reviewed the content.

### Changed

- `commands/chat-read.md`, `chat-send.md`, `chat-ack.md`, `chat-threads.md` rewritten to call the REST API directly via `curl` with an explicit `X-PB-Chatroom-Participant` header, matching the pattern `chat-threads-open.md` and `chat-while-away.md` already used.
- `.mcp.json` — `mcpServers` emptied; nothing registers the MCP server by default.
- `mcp/` source kept in-tree for reference; not wired into any command.

---

## [0.4.0] — 2026-06-27

### Added

- **CLAIM protocol** — multi-recipient `claim_request` threads; server-enforced first-wins via conditional UPDATE (409 on conflict, idempotent same-agent); `chat_claim` MCP tool; 60 s deadline orchestrated by relay-replacement executor.
- **Multi-recipient threads** — `to_participants[]` on POST /api/threads; per-recipient ack tracking via `thread_recipients` table; status flips to `acked` only when all recipients ack.
- **Structured discussion_type metadata** — 7 typed modes: `claim_request`, `claim_accepted`, `design_question`, `debate`, `postmortem`, `escalation`, free-form null. REST + MCP pass it through.
- **Escalation evaluator** — 7 merged rules in the coordination protocol (competing approaches, arch changes, prod data, cost cap, low confidence, external creds, tests broken). Replaces reply with `discussion_type=escalation` on trigger.
- **Dashboard escalation panel** — live counts + jump-to links for open escalations, postmortems, active CLAIMs.
- **`chat_ask_peer` MCP tool** — graphiti-first short-circuit; falls back to `design_question` thread.
- **identity convention pin** — canonical forms: `host`, `host-auto`, `container-<X>`, `container-<X>-auto`. `host-agent` deprecated with migration note.
- **claudeclaw integration recipe** — `examples/claudeclaw-host-auto.json` + `examples/claudeclaw-system-prompt.md` + `docs/claudeclaw-integration.md` for cron/heartbeat-driven executor pairing.
- `docs/external-executors.md` — bridge contract + three executor options (claudeclaw recommended; claude-code-scheduler; shell while-loop).
- `/chat while-away` slash command — surfaces unread escalations + postmortems on session start.
- `docs/agent-to-agent.md` — turn-by-turn protocol examples for all five coordination patterns.
- `docs/plan-history/` — archived plan briefs (v0.3.0, v0.4.0 original, v0.4.0 revised).
- `CHANGELOG.md` — this file.

### Changed

- pb-chatroom is now **protocol + storage** only. The always-on execution engine is operator-chosen (claudeclaw recommended). See `docs/external-executors.md`.
- `docker-compose.yml` reduced to two services: `server` + `mcp`. No `--profile relay`.
- Plugin version bumped to `0.4.0` in `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`.

### Removed

- **`relay/` daemon** (Responder, Broadcaster, Archiver) — deleted. Three confirmed production wire-up bugs on first smoke test:
  1. `relay/config.py:173` → `IsADirectoryError` (no default config file shipped)
  2. `docker-compose.yml` relay service had `ports: []` — `/healthz` unreachable
  3. `relay/polling.py:62` → `KeyError: 'updated_at'` (server schema uses `last_message_at`)
  Relay code is archived at `docs/plan-history/v0_4_0-revised.md` and preserved in git at commit `baa4801` on `feature/agent-coordination-v0-4-0`.

---

## [0.3.0] — 2026-06-26

- Relay daemon substrate (Responder, Broadcaster, Archiver) — shipped at commit `baa4801`. See `docs/plan-history/v0_3_0.md`.

---

## [0.1.0] — 2026-06-26

- FastAPI REST + SQLite + MCP server (`chat_send`, `chat_list_threads`, `chat_read_thread`, `chat_ack`) + HTML dashboard + slash commands + docker-compose stack. Two services: `server` + `mcp`.

---

[Unreleased]: https://github.com/proxiblue/pb-chatroom/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/proxiblue/pb-chatroom/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/proxiblue/pb-chatroom/compare/v0.1.0...v0.3.0
[0.1.0]: https://github.com/proxiblue/pb-chatroom/releases/tag/v0.1.0
