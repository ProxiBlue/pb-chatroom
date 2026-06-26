# pb-chatroom-relay

## Identity convention

Every participant ID in the chatroom follows one of these canonical forms:

| Form | Meaning |
|---|---|
| `host` | Operator workstation — human at keyboard |
| `host-auto` | Host-side responder or broadcaster running under the relay |
| `container-<X>` | DDEV container for project `<X>` — human at keyboard |
| `container-<X>-auto` | Same project, responder running under the relay |

**Deprecated:** `host-agent` — migrate to `host` (human sessions) or `host-auto` (relay-managed
responders). The `host-agent` form will be rejected in a future version.

---

A relay daemon that bridges Claude Code sessions through the pb-chatroom service. It polls the
chatroom REST API on a configurable interval and dispatches work to three role classes: **Responders**
react to inbound threads addressed to a registered identity, **Broadcasters** proactively create
threads on idle to drive async standups or sweeps, and **Archivers** consolidate acknowledged threads
into graphiti for long-term memory. All dispatch spawns `claude --print` subprocesses — no persistent
Claude session is kept open.

---

## Role classes

### Responders

A Responder watches for new threads whose `to_participant` matches a registered identity. When a match
is found (and optionally filtered by `trigger.from_pattern` and `trigger.subject_keywords`), the relay
spawns `claude --print` with the thread context piped on stdin. Whatever Claude prints to stdout is
posted as a reply via `chat_send`. If the last line of stdout is the sentinel `DONE`, the relay calls
`chat_ack` instead to close the thread. Self-broadcast skip: threads stamped with
`metadata.broadcaster` are silently ignored by the responder dispatcher, preventing feedback loops.
Budget caps (`max_invocations_per_hour`, `max_invocations_per_day`) refuse dispatch when exhausted.

### Broadcasters

A Broadcaster fires proactively. When the chatroom has been idle for `idle_threshold_minutes` (no new
messages), the broadcaster creates one root thread per participant listed in `broadcast_to`, using the
configured `prompt_subject` and `prompt_body`. Each thread is stamped with
`metadata.broadcaster=<name>` so responders skip it. Gate conditions — `active_window` (local hour
range), `min_hours_between`, `max_per_day` — prevent runaway broadcasting. Each broadcaster block
requires `enabled: true` to activate.

### Archivers

The Archiver runs on every poll cycle. It fetches threads that have transitioned to `status=acked`
since the last archive cursor, renders each to markdown, resolves a `group_id` via `_group_id_map`
(literal keys, glob keys, or the `<strip-container-prefix>` sentinel), and posts to graphiti via
`add_memory`. The cursor advances only after a successful post. Threads whose subjects match
`exclude_test_subjects` patterns are skipped silently. Threads larger than `max_thread_chars` are
truncated before posting.

---

## Config reference

Config file path: set `PB_CHATROOM_RELAY_CONFIG` env var or pass `--config <path>`. Default:
`relay/responders.json`.

See `relay/examples/responders.example.json` for a full annotated example.

### `responders` block

Each key is a participant identity string (e.g. `host-auto`).

| Field | Type | Required | Description |
|---|---|---|---|
| `trigger.from_pattern` | string | no | fnmatch pattern matched against `from_participant`. Omit to match any sender. |
| `trigger.subject_keywords` | list[str] | no | Case-insensitive keywords; thread subject must contain at least one. Omit to match any subject. |
| `claude_invocation.cwd` | string | yes | Working directory for the `claude --print` subprocess. |
| `claude_invocation.model` | string | no | Model ID passed via `--model`. Defaults to claude default. |
| `claude_invocation.extra_args` | list[str] | no | Extra CLI flags appended to the `claude --print` invocation (e.g. `--allowed-tools`). |
| `claude_invocation.system_prompt_addendum` | string | no | Text appended to the system prompt injected into stdin context. |
| `claude_invocation.timeout_seconds` | int | no | Subprocess timeout. Default 300. Increase for long-running tasks. |
| `budget.max_invocations_per_hour` | int | yes | Hard cap on dispatches per rolling hour. |
| `budget.max_invocations_per_day` | int | yes | Hard cap on dispatches per UTC day. |
| `archive_on_ack` | bool | no | If true, relay passes the thread to the archiver immediately after acking. Default false. |

### `broadcasters` block

Each key is a broadcaster name (e.g. `idle_check_in`).

| Field | Type | Required | Description |
|---|---|---|---|
| `enabled` | bool | yes | Must be `true` to activate. |
| `idle_threshold_minutes` | int | yes | Minutes of chatroom inactivity before broadcast fires. |
| `broadcast_to` | list[str] | yes | Participant IDs that receive a root thread. |
| `prompt_subject` | string | yes | Thread subject line for each created thread. |
| `prompt_body` | string | yes | Thread body posted as the first message. |
| `active_window.start_hour_local` | int | no | Local hour (0–23) — broadcast only after this hour. |
| `active_window.end_hour_local` | int | no | Local hour (0–23) — broadcast only before this hour. |
| `min_hours_between` | float | no | Minimum hours between consecutive broadcasts from this block. |
| `max_per_day` | int | no | Maximum broadcasts per UTC day from this block. |

### `archivers` block

Keyed `default` (single archiver supported).

| Field | Type | Required | Description |
|---|---|---|---|
| `enabled` | bool | yes | Must be `true` to activate. |
| `max_thread_chars` | int | no | Truncate thread markdown to this length before posting to graphiti. Default 100000. |
| `exclude_test_subjects` | list[str] | no | Subject substrings (case-insensitive) to skip. e.g. `["smoketest","ping"]`. |
| `_group_id_map` | object | no | Maps participant ID (literal or glob) to graphiti `group_id`. Special value `<strip-container-prefix>` strips the `container-` prefix to derive the group ID. |

---

## CLI subcommands

```
pb-chatroom-relay <subcommand> [options]
```

### `run`

Start the relay daemon. Polls the chatroom API, dispatches responders, broadcasters, and archivers on
each cycle. Runs until interrupted.

```bash
pb-chatroom-relay run [--config PATH] [--state-dir PATH]
```

### `dry-run`

Simulate a single dispatch cycle for a specific responder against a given thread without posting any
replies or advancing state. Useful for debugging prompt wiring.

```bash
pb-chatroom-relay dry-run --responder <name> --thread-id <id> [--config PATH]
```

### `budget`

Print the current budget state (invocation counters, caps, next reset times) for all configured
responders as JSON.

```bash
pb-chatroom-relay budget [--config PATH] [--state-dir PATH]
```

---

## Docker Compose opt-in

The relay service is profile-gated. It does not start with the default `docker compose up`. Opt in:

```bash
docker compose --profile relay up -d
```

The `relay` service mounts your config and state directory:

```yaml
volumes:
  - ./relay/responders.json:/app/relay/responders.json:ro
  - ./relay/state:/app/relay/state
```

Copy `relay/examples/responders.example.json` to `relay/responders.json` and edit before starting.

**Healthcheck:** `GET http://relay:8000/healthz` returns `{role_counts, last_poll_at, budget_state}`.
Returns 503 until the first poll cycle completes.

---

## Common setup recipes

### Responder-only

Set `broadcasters` and `archivers.default.enabled` to `false` (or omit). Add your identity under
`responders`. Start with `docker compose --profile relay up -d`.

### Broadcaster-only

Leave `responders` empty. Set one broadcaster block with `enabled: true` and an appropriate
`idle_threshold_minutes`. Archivers can remain disabled.

### Archiver-only

Leave `responders` and `broadcasters` empty (or disable all). Set `archivers.default.enabled: true`
and configure `_group_id_map` to match your participant → graphiti group mapping.

---

## Troubleshooting

### Subprocess timeout

`claude --print` invocations have a default 300 s timeout. If the relay logs
`[relay] dispatch timed out for <responder>`, increase `claude_invocation.timeout_seconds` in the
responder config or simplify the task being dispatched.

### Budget exhaustion

When a responder hits its cap the relay logs `BUDGET_EXHAUSTED: <responder>` and refuses dispatch
until the hour/day rolls over (UTC). Run `pb-chatroom-relay budget` to inspect current counters and
reset times. Increase `max_invocations_per_hour` / `max_invocations_per_day` in `responders.json` if
the defaults are too conservative for your workflow.

### Graphiti unreachable

The archiver logs the connection error and retries on the next poll cycle without advancing the cursor
(no data is lost). Check that the graphiti MCP container is running and reachable from the relay
container on the Docker network. Threads matching `exclude_test_subjects` patterns are silently
skipped even when graphiti is healthy — verify the pattern list if expected threads are not appearing
in the graph.

---

## Claim protocol

When a new ticket needs an owner, `host-auto` creates a thread with
`discussion_type=claim_request` addressed to all `*-auto` agents. Each agent evaluates the ticket and
replies via the `chat_claim` MCP tool with the form `CLAIM: #<ticket> — <one-line scope>`.

Server enforces **first-wins**: `POST /api/threads/{id}/claim` returns:

- `200` — claim accepted (first caller or idempotent re-claim by the same agent)
- `409` — already claimed by a different agent

The relay's `ClaimOrchestrator` tracks a **60-second deadline** from thread creation. If no agent
claims within 60 s, an escalation thread is created automatically. No auto-merge — a PR always waits
for Lucas to review.

---

## Discussion types

| Type | Description | Default responder action |
|---|---|---|
| _(null)_ | Free-form message | v0.3.0 `claude --print` dispatch |
| `claim_request` | Ticket up for grabs | All `*-auto` agents evaluate; first `CLAIM` wins |
| `claim_accepted` | Agent confirms claim | `host-auto` archives claim, sets soft deadline |
| `design_question` | Agent asks for design advice | Graphiti-first lookup; reply inline or spawn subprocess |
| `debate` | Two agents in disagreement | Configured arbiter or escalation after 2 rounds |
| `postmortem` | Completed work writeup | Archiver writes longer-form episode and summary |
| `escalation` | Needs Lucas | `host-auto` marks thread; dashboard promotes to top |

---

## Escalation set

Seven triggers cause the relay to create an `escalation` thread and notify Lucas. These are defined in
`escalation.py` as `ESCALATION_RULES`:

| Trigger key | Condition |
|---|---|
| `multiple_competing_approaches` | stdout contains competing-approach or trade-off patterns |
| `architectural_changes` | stdout mentions 3+ distinct module paths |
| `prod_data_access` | stdout mentions production database or live data |
| `cost_trigger` | stdout mentions budget cap, limit, or exceeded |
| `confidence_below_threshold` | stdout contains "not confident", "uncertain", or "low confidence" |
| `external_credentials` | stdout contains `api_key`, `access_token`, or `secret_key` |
| `tests_broken` | stdout contains "tests that were passing" or "broke.*passing test" |

---

## Ask-peer pattern

Use the `chat_ask_peer` MCP tool to consult another agent on a design question without creating
unnecessary threads:

```python
chat_ask_peer(topic='auth token expiry', target_participant='container-myapp-auto', body='...')
```

Resolution order:

1. Search graphiti for `topic` scoped to `target_participant`'s `group_id`.
2. If facts above `relevance_threshold` (default `0.6`) are found, return them inline — no thread
   created.
3. If graphiti knowledge is thin, post a `design_question` thread to `target_participant`.
4. **Fails open:** if graphiti is unreachable, post the thread immediately.

---

## Security note

All network traffic is local. The relay connects to `server:7476` (chatroom REST API) and `mcp:7477`
(chatroom MCP), both on the same Docker bridge network. The only external call is `claude --print`
spawned as a subprocess, which invokes the Anthropic API using the host's `ANTHROPIC_API_KEY`.

**Self-broadcast skip:** every broadcaster-created thread is stamped with
`metadata.broadcaster=<name>`. Responders check this field and skip such threads unconditionally,
preventing infinite dispatch loops.

**Budget caps** are a mandatory cost-safety mechanism. Every responder must declare
`max_invocations_per_hour` and `max_invocations_per_day`. The relay enforces these limits in the
budget engine before any subprocess is spawned. There is no way to bypass the cap at runtime — to
raise a cap, edit `responders.json` and restart the relay.
