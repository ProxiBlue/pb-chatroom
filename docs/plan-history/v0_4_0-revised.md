# pb-chatroom v0.4.0 (revised) — Coordination Layer + Rip Relay + claudeclaw as Ignitor

This brief is the input to `/hcf:plan-create`. It REPLACES the previous v0.4.0 brief (archived at `relay/HCF_PLAN_BRIEF.v0.4.0-original.md`).

## Context — why this revision

The original v0.4.0 brief scoped two things in one release:
1. **Coordination layer** in pb-chatroom (CLAIM, multi-recipient threads, discussion_type, escalation set, identity-convention pin, dashboard panel, ask-peer tool, schema migration)
2. **Headless relay daemon** (Responder/Broadcaster/Archiver — the always-on execution engine)

The HCF build at commit `baa4801` on `feature/agent-coordination-v0-4-0` completed both. **All 366 unit tests pass.** But end-to-end smoke testing surfaced 3 production wire-up bugs in the relay daemon component (exactly the integration-gap pattern from `feedback_hcf_build_integration_gaps.md`):

| # | File / Symptom | Root cause |
|---|---|---|
| 1 | `relay/config.py:173` → `IsADirectoryError: '/app/relay/responders.json'` | No default config file shipped; docker bind-mount auto-creates target as directory |
| 2 | E2E test → `Connection refused` at `localhost:8000/healthz` | `docker-compose.yml:44` has `ports: []` for the relay service |
| 3 | `relay/polling.py:62` → `KeyError: 'updated_at'` | Relay reads thread field `updated_at`; server schema uses `last_message_at` (per `server/src/pb_chatroom/store/schema.py:17`) |

Audit found schema-mismatch assumptions in `relay/archiver.py:122,154` (same `updated_at` issue) and `relay/dispatcher.py:107,127` + `relay/archiver.py:140` (`from_participant` field assumed on thread; lives on messages only — thread has `created_by`). Bugs 4–6 once 1–3 cleared.

The server-side v0.4.0 work is **clean**. Smoke confirmed:
- ✅ Multi-recipient thread POST → returns `recipients[]`
- ✅ `discussion_type` column round-trips
- ✅ All MCP tool source files exist (chat_send, chat_list_threads, chat_read_thread, chat_ack, chat_claim, chat_ask_peer)
- ✅ Server v0.4.0 migration ran cleanly on the existing v0.3.0 production DB
- ✅ All thread endpoints functional

## Strategic shift — claudeclaw as the event ignitor

Per discussion with Lucas (2026-06-26): the always-on engine should be an external dependency, not homegrown. We adopt **claudeclaw** (https://github.com/moazbuilds/claudeclaw — 1218★, ~15k downloads/14d, TypeScript daemon) as the **event ignitor** for pb-chatroom.

**Division of responsibility:**

| Layer | Tool | Owns |
|---|---|---|
| Event ignition | claudeclaw | Heartbeat, cron, `/api/inject` endpoint, future Slack/Discord/Telegram/voice ingress, web dashboard, GLM model fallback |
| Coordination protocol | pb-chatroom | Threads, identities, CLAIM, discussion_type, escalation, multi-recipient, graphiti archives, MCP tools |
| Headless invocation | claudeclaw | Spawns `claude --print` with chatroom MCP available; captures output |

**Integration shape: claudeclaw configuration, not custom bridge code.** We do NOT write a Python adapter that polls chatroom and POSTs to claudeclaw. Instead:

- claudeclaw's heartbeat is configured with a system-prompt addendum that teaches Claude the chatroom protocol
- Heartbeat fires every N minutes (operator-configurable, default 5 min) → Claude wakes up, runs `chat_list_threads` on its own identity, replies / claims / escalates per protocol
- claudeclaw `/api/inject` (deferred Slack ingress) becomes the operator-facing trigger for ad-hoc invocations

**Slack ingress is OUT OF SCOPE for this brief** (blocked on Lucas's local Linux access issue; per his direction "assume slack integration works, circle to usage later"). The brief delivers the **cron/heartbeat-driven ignition path** which is testable end-to-end without Slack.

## v0.4.0 (revised) scope — what THIS plan delivers

### Phase A — Rip broken relay/ daemon code

1. **Delete `relay/src/`, `relay/tests/`, `relay/Dockerfile`, `relay/pyproject.toml`, `relay/uv.lock`, `relay/responders.json`, `relay/examples/`, `relay/README.md`.**
2. **Move plan-history docs** (`HCF_PLAN_BRIEF.md`, `HCF_PLAN_BRIEF.v0.3.0.md`, `HCF_PLAN_BRIEF.v0.4.0-original.md`) from `relay/` to a new `docs/plan-history/`. After move, `relay/` no longer exists.
3. **Remove the `relay` service** from `docker-compose.yml`. No more `--profile relay`. Two services: `server` + `mcp`.
4. **Audit `server/`, `mcp/`, `commands/`, `agents/`, `docs/`** for references to the old "responder/broadcaster/archiver daemon" pattern. Where they appear in user-facing docs, replace with the new "claudeclaw + chatroom" pattern.

### Phase B — Verify the coordination-layer keeps work

5. **Run full server + MCP test suites** (`uv run pytest` in each). Expect 134 server + 49 mcp = 183 tests pass.
6. **Smoke-test all v0.4.0 server endpoints**: multi-recipient POST, discussion_type round-trip, chat_claim conflict path (409 on race), chat_ask_peer graphiti-first short-circuit, `/while-away` slash command, dashboard escalation panel.
7. **Verify the v0.4.0 schema migration is non-destructive**: v0.4.0 only ADDED columns (`recipients` table, `claimed_by`/`claimed_at`/`claim_scope`/`discussion_type` on threads). A v0.3.0 client reading a v0.4.0 DB should still work for the v0.3.0 subset. Verify via a quick read-only smoke test.

### Phase C — Add claudeclaw integration recipe (configuration + docs, no new code)

8. **Create `docs/external-executors.md`** — design rationale + recommended pairings:
   - **claudeclaw** for Slack/Discord/Telegram/voice + cron/heartbeat (RECOMMENDED)
   - **claude-code-scheduler** (501★) for cron-only deployments
   - **plain `claude --print` in a shell while-loop** for minimal deployments
   - Bridge contract: external executor polls `GET /api/threads?to=<my-id>&status=open` and posts replies via `POST /api/threads/<id>/messages` with `X-PB-Chatroom-Participant: <my-id>` header
9. **Create `docs/claudeclaw-integration.md`** — step-by-step recipe for the cron/heartbeat-driven path:
   - Install claudeclaw on the host or per-DDEV-container
   - Configure heartbeat with cwd pointing at a workspace that has the pb-chatroom MCP server mounted in its `.mcp.json`
   - Sample `claudeclaw settings.json` snippet (provided below as `examples/claudeclaw-host-auto.json`)
   - Sample heartbeat system-prompt addendum that teaches Claude the chatroom protocol (CLAIM format, escalation triggers, discussion_type usage, graphiti-first ask-peer pattern) (provided below as `examples/claudeclaw-system-prompt.md`)
   - Operator opt-in checklist: how to start with one identity (`host-auto`) and add more as confidence grows
   - **Defer Slack-bot setup** to a "v0.5.0 — Slack ingress" section with a placeholder ("test once local Linux access restored").
10. **Create `examples/claudeclaw-host-auto.json`** — a working claudeclaw settings.json that:
    - Defines heartbeat every 5 minutes during 08:00–19:00 local
    - Wires the chatroom MCP into the spawned Claude session
    - Caps budget (max 20 invocations/hour, 100/day)
    - Enables GLM fallback for cost protection
    - Has `allowedUserIds` empty (post-v1.0.26 = block-everyone default; Slack ingress requires explicit opt-in later)
11. **Create `examples/claudeclaw-system-prompt.md`** — the system-prompt addendum that teaches a freshly-spawned Claude:
    - Its identity (e.g. `host-auto` or `container-pvcpipesupplies-auto`)
    - To call `chat_list_threads` first thing
    - The CLAIM protocol (60s window, scope-line)
    - The 11-rule escalation set (must escalate, not auto-fix)
    - Graphiti-first ask-peer ordering
    - To respond with `chat_send` for in-progress and `chat_ack` for done

### Phase D — Document the operator setup

12. **Update `README.md` Status / Roadmap section**:
    - v0.4.0 row: coordination layer + claudeclaw recipe
    - v0.5.0 row: Slack ingress (deferred, pending Lucas's local access fix); identity registry (per LCD bug `207ca92a` — `chat_list_participants` + `/api/participants` endpoint)
    - Drop the "Subagent tool access" v0.4.0 line (shipped in v0.1.x — already removed once, restore if regressed)
13. **Update `docs/agent-to-agent.md`** to reflect that the patterns described are PROTOCOL only (claudeclaw or another executor does the actual triggering).
14. **Add a "Quick Start with claudeclaw" section to `README.md`** — 5 lines pointing at `docs/claudeclaw-integration.md`.

### Phase E — Release prep

15. **Bump versions to `0.4.0`** in `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json`. (`relay/pyproject.toml` is gone after Phase A.)
16. **Update `CHANGELOG.md`** (create if missing) — list v0.4.0 features actually shipping + the relay-rip rationale + the claudeclaw integration path.
17. **Stage a merge commit to `main`** from `feature/agent-coordination-v0-4-0`. Tag `v0.4.0`. **Do NOT push.** Lucas pushes after manual review.

## Integration acceptance criteria — must be true at end of plan

- `docker compose up -d` brings up 2 healthy services (server + mcp); no `relay` service, no `--profile relay` flag works (the profile is gone, not just disabled).
- Running the `examples/claudeclaw-host-auto.json` config against a real claudeclaw install on the host produces a heartbeat-driven Claude invocation that successfully calls `chat_list_threads` and posts at least one valid reply to an existing inbox thread. (This is the v0.5.0 candidate — install + manual verification is the operator's job, but the brief includes a smoke checklist.)
- All v0.4.0 server tests stay green.
- No references to "responder" / "broadcaster" / "archiver" daemon code anywhere in the repo except in `docs/plan-history/` (preserved as history).
- README + docs make it obvious to a new operator that pb-chatroom is **protocol + storage**, and the executor is **operator-chosen** (with claudeclaw as the recommended default).

## What this brief explicitly does NOT do

- Does NOT write custom Python/TypeScript bridge code. The integration is **claudeclaw config + system prompt + chatroom MCP**, nothing more.
- Does NOT install claudeclaw automatically (operator runs `claude plugin install claudeclaw@claudeclaw` themselves per their README).
- Does NOT validate Slack ingress (deferred to v0.5.0, blocked on local access).
- Does NOT fix the 3 confirmed relay bugs (the relay is being deleted, not fixed).
- Does NOT touch the existing chatroom production DB at `data/chatroom.db` (already migrated by the test session; the migration is the keeper).
- Does NOT add the identity-registry endpoint LCD requested (thread `207ca92a`) — that's v0.5.0 scope, not v0.4.0.

## Constraints / hard rules

- **No new feature work in the chatroom server itself.** Server is feature-complete for v0.4.0 at `baa4801`.
- **Server + MCP tests must stay green throughout.**
- **No HCF post-implementation pipeline on relay code.** It's being deleted.
- **No version bump above 0.4.0.** This is the same v0.4.0 release, reshaped.
- **Preserve git history of `baa4801`.** Don't squash. Removal is a new commit on top.
- **Examples must be REAL working configs**, not pseudo-code. Operator must be able to copy `examples/claudeclaw-host-auto.json` into their claudeclaw install and have it work (modulo their own MCP URL).

## Hand-off to HCF

Run from `~/claude-plugins-central/seed/marketplaces/pb-chatroom/`:

```
/hcf:plan-create
```

Use this file as plan-create input. HCF will produce a `_plan.md` with the task breakdown (probably 10–14 tasks). Review, then `/hcf:plan-orchestrate`.

Per `feedback_hcf_build_integration_gaps.md`: the integration-gap discipline still applies — but the surface is small. One integration test: `docker compose up -d` → curl `/healthz` on server + mcp; both 200 within 60s. Plus a doc-acceptance check: `docs/claudeclaw-integration.md` includes a literal `examples/claudeclaw-host-auto.json` reference + a copy-pasteable cron snippet.

Per `feedback_hcf_plan_orchestrate_overlay.md`: `/hcf:plan-orchestrate` runs native; `gitnexus-reviewer` is in `pipeline.md`'s `post-implementation` slot.

## Reference — what's in v0.4.0 final (after this brief executes)

| Component | State |
|---|---|
| `server/` | All v0.4.0 work intact |
| `mcp/` | All v0.4.0 tools |
| `commands/` | All v0.4.0 slash commands |
| `agents/` | chat-archive agent (unchanged) |
| `hooks/` | UserPromptSubmit inbox hook (unchanged) |
| `docs/` | agent-to-agent.md, external-executors.md (new), claudeclaw-integration.md (new), plan-history/ (archived briefs) |
| `examples/` | claudeclaw-host-auto.json (new), claudeclaw-system-prompt.md (new) |
| `relay/` | **DELETED** |
| `docker-compose.yml` | 2 services: server + mcp |
| `README.md` | Reflects coordination + claudeclaw recipe; v0.5.0 = Slack ingress + identity registry |
| `CHANGELOG.md` | New file documenting v0.4.0 reshape |
