# Changelog

All notable changes to pb-chatroom are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- **Dashboard ack button** — the per-thread view renders an `ack` button on open threads. It POSTs to `/api/threads/{id}/ack` as the seed message's recipient (the participant the ack is owed from), so an operator can acknowledge a thread from the web UI. Single-recipient threads close immediately; multi-recipient (broadcast) threads record that recipient's ack and close once all recipients have acked.

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
