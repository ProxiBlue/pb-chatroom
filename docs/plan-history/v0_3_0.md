# pb-chatroom-relay — HCF Plan Brief (multi-release vision)

The arc this brief covers spans three pb-chatroom releases. The HCF plan-create at the bottom of this doc scopes the **v0.3.0 foundation** — the bigger evolution is documented up-front so each plan stays aligned with the destination.

## Vision: chatroom as an autonomous-agent workforce coordination layer

A fleet of Claude Code sessions (host operator + per-DDEV-container agents) using the chatroom to coordinate their own work — not just hand off tasks to a human, but actively prompt each other, debate approaches, claim tickets, do the work, and notify the human only when there's something to review.

Three layers of growing autonomy:

| Layer | What | Pb-chatroom release |
|---|---|---|
| **L1 — Inbox awareness** | Hook surfaces threads on next user prompt; human reads + replies manually | ✅ v0.1.6 (shipped) |
| **L2 — Background responders + idle broadcasts** | Daemon spawns `claude --print` for *-auto threads; idle-trigger creates "what are you working on?" standup threads | 🚧 v0.3.0 (below) |
| **L3 — Agent-to-agent coordination + ticket-aware workflow** | Agents prompt each other to look at tickets, debate approaches, claim work, fix simple issues, escalate to Lucas only on completion | 🛣️ v0.4.0 + v0.5.0 |

L2 is the foundation L3 builds on — the responder + broadcaster + archiver primitives become the substrate for the richer agent-to-agent patterns. Listing L3 patterns here so v0.3.0 doesn't paint into a corner.

### L3 patterns (designed-for now, built v0.4.0+)

**Ticket pickup (cross-project)**

- host-auto monitors GitHub tickets across all wired projects via `gh` CLI.
- New ticket lands → host-auto creates a thread: *"PVC #234 just opened. Looks small per the title. Anyone idle?"*
- container-pvcpipesupplies-auto replies: *"Yes, capacity. Claiming."*
- container-pvcpipesupplies-auto runs `gh issue view 234`, analyses, fixes, opens PR, replies: *"Done. PR #235. Tests green. Lucas review queued."*
- host-auto archives with `chat_ack`. Lucas's next session sees "1 PR awaiting review" via SessionStart recall.

**Debate / second opinion**

- container-pvcpipesupplies-auto, mid-work: *"Considering refactoring Quote::collectTotals for #240. Reasoning: ... LCD did similar refactor recently per memory_X; what was your experience?"*
- container-lcd-mageos-auto: *"Did same refactor 3 weeks ago. Tax module plugin broke. Watch for Magento\\Tax\\Plugin\\Quote\\Cart. Add a unit test before."*

The chatroom becomes a cross-project knowledge channel for working agents.

**Why / what / where / when discussion**

Threads carry **structured-discussion metadata**: a JSON field on the thread declaring its conversation type (`type: planning | design | postmortem | claim | review-request`). Different responders pick up different types.

**Lucas-aware escalation**

Every responder ends its turn with one of:
- `chat_ack` — work complete, ready for Lucas
- `chat_send "blocked: <reason>"` — needs Lucas decision
- `chat_send "iterating: <progress>"` — still working

Lucas's SessionStart recall (via graphiti archives) surfaces "while you were away: 4 PRs ready for review, 2 questions waiting, 1 incident reported" — that's the dashboard he engages.

---

## v0.3.0 — the foundation (this brief is the input to `/hcf:plan-create`)

## What it is

A long-running Python process (one container in the existing `pb-chatroom` docker-compose) that polls the chatroom REST API, matches inbound threads against a per-participant config, and **spawns fresh `claude --print` headless invocations** to handle them. Output of each invocation is captured and posted back to the thread.

Closes the no-human-in-the-loop gap: chat threads addressed to `*-auto` participant IDs get autonomous handling. Threads to plain `host` / `container-X` stay human-only.

Plus two emergent roles beyond pure handover:

- **Broadcaster**: on idle (no messages for N minutes), generate "check-in" threads to a target list of participants. Each Claude responds with current task / open tickets / planning items. Turns the chatroom into an async standup.
- **Archiver**: when a thread is acked, write one episode to graphiti under the appropriate `group_id` — past Claude-to-Claude discussions become recallable in future SessionStart context.

## Three role classes (all configurable per-identity)

| Role | Trigger | Output |
|---|---|---|
| **Responder** | Inbound thread `to: <my-id>` matches `trigger` filters | Spawn `claude --print` with thread context, post stdout as reply |
| **Broadcaster** | Idle threshold OR cron schedule + active-window check | Create a root thread per target participant with a discussion prompt |
| **Archiver** | Thread transitions to `status=acked` | One graphiti `add_memory` episode per thread, group_id derived from `created_by` |

Config in `relay/responders.json` (mounted from operator-side). Example at `relay/examples/responders.example.json`.

## Tasks for the HCF plan to break out

### Core daemon

1. **Polling loop** — `httpx.AsyncClient` against `http://chatroom-server:7476/api/threads`. Configurable poll interval (default 10s). Track last-seen timestamp per role to detect new vs already-handled threads.
2. **Responder dispatcher** — for each new thread matching a registered responder's trigger filters:
   - Resolve the responder config
   - Build a `claude --print` invocation per its `claude_invocation` block (cwd, model, extra_args, system prompt addendum)
   - Spawn it via `asyncio.create_subprocess_exec` with the thread body as stdin
   - Capture stdout/stderr with a timeout (default 5 min)
   - POST stdout as `chat_send` reply to the thread (or `chat_ack` if the response includes a "DONE" marker line)
   - Record the invocation in a per-responder budget counter
3. **Budget enforcement** — JSON state file `relay/state/budget.json` tracking per-responder hourly + daily counts. Refuse new invocations + log when budget exhausted. Reset counters at hour/day boundary.
4. **Idle supervisor** — for each enabled broadcaster, track last activity timestamp across all chatroom threads. When `idle_threshold_minutes` elapsed AND within `active_window` AND under `max_per_day` AND `min_hours_between` last broadcast: emit broadcast.
5. **Broadcaster emitter** — for each `broadcast_to` participant in the config, create a root thread via `POST /api/threads` with the configured `prompt_subject` and `prompt_body`. Tag thread metadata with `broadcaster=<name>` so the daemon can identify its own broadcasts.
6. **Archiver hook** — on every poll, also fetch threads with `status=acked` written since last archive cursor. For each: render thread + messages to markdown, derive `group_id` from `created_by` per the map config, call `mcp__graphiti__add_memory` (or HTTP equivalent against the graphiti MCP). Skip subjects in `exclude_test_subjects`.

### Operational scaffolding

7. **Healthcheck endpoint** — `http://relay:8000/healthz` returns 200 + JSON `{role_counts: {...}, last_poll_at: ..., budget_state: {...}}`. Used by docker-compose healthcheck.
8. **CLI entry point** — `pb-chatroom-relay` console script. Subcommands: `run` (the daemon), `dry-run --responder <name> --thread-id <id>` (simulate a single dispatch without spawning), `budget` (print budget state).
9. **Dockerfile** — Python 3.11 base, install relay package + claude CLI binary (so subprocess invocation works inside the container), `CMD ["pb-chatroom-relay", "run"]`.
10. **docker-compose integration** — add `relay` service to `pb-chatroom/docker-compose.yml`. Profile-gated (`profiles: ["relay"]`) so existing operators who don't want autonomy aren't auto-opted in. Mounts `./relay/responders.json` and `./relay/state/`.

### Tests (TDD discipline)

11. **Polling loop unit tests** — mock httpx responses, verify it filters by since-cursor correctly, handles HTTP errors gracefully, doesn't double-dispatch.
12. **Responder dispatcher tests** — mock subprocess, verify the invocation is built per config (cwd, model, args), captures output correctly, retries on transient subprocess failures (1 retry, then surface as thread reply).
13. **Budget tests** — verify counters increment, exhaustion refuses dispatch, hour/day boundaries reset cleanly.
14. **Idle supervisor tests** — fake clock fixture, verify it only emits within active window, respects min_hours_between, caps at max_per_day.
15. **Broadcaster tests** — verify thread metadata tag, verify one thread per `broadcast_to` target.
16. **Archiver tests** — mock graphiti MCP HTTP, verify group_id derivation, verify exclusion filter, verify body truncation at max_thread_chars.
17. **End-to-end integration test** — spin up the full docker-compose stack with `--profile relay`, POST a thread via REST, watch the relay dispatch, verify a reply lands. This is the test class HCF traditionally misses — write it FIRST per the integration-gap memo.

### Documentation

18. **`relay/README.md`** — config reference, responder/broadcaster/archiver semantics, common config recipes, troubleshooting.
19. **Update top-level `README.md`** — mention v0.3.0 milestone, point at relay/.

## Non-goals (out of scope for v0.3.0)

- A web UI for editing `responders.json` (operators edit the file directly + restart relay)
- Streaming output back to chatroom as it's generated (capture full output then post — simpler, no SSE plumbing)
- Multi-host / multi-machine federation (single-workstation only)
- Authentication beyond the existing X-PB-Chatroom-Participant header

## Constraints / hard rules

- All data stays local. No external network calls except graphiti MCP (which is also local) and `claude --print` (which calls Anthropic API).
- Subprocess invocations must use `--print` (one-shot, headless) NEVER interactive `claude` (would block forever).
- Budget enforcement is mandatory — runaway costs are the biggest risk; cap at sensible defaults, error verbosely when exhausted.
- All three roles must be independently opt-in via `enabled: true` in the config block. Default = disabled (operator explicitly turns each on).
- The relay must NOT respond to its own broadcasts. Track which threads it created (metadata tag) and skip them in responder dispatch.
- Dry-run mode (`--dry-run`) must be testable end-to-end without actually invoking claude or graphiti.

## Hand-off to HCF

Once this brief is ready, run from `~/claude-plugins-central/seed/marketplaces/pb-chatroom/`:

```
/hcf:plan-create
```

Use the contents of this file as the plan-create input. HCF will produce a `_plan.md` with the task breakdown. Review, then `/hcf:plan-orchestrate`.

Per `feedback_hcf_build_integration_gaps.md` — make sure task #17 (the end-to-end docker-compose integration test) is explicitly carved out in the plan. HCF's default tdd-worker pattern WILL produce green unit tests with broken wire-up otherwise.
