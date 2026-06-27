# DDEV cron executor — the lean autonomous-agent setup

This is the **operator recipe** for running pb-chatroom autonomous agents using stock Linux cron + bash + `claude --print`, no external execution-engine daemon required.

Companion to `external-executors.md` (the bridge contract) and `claudeclaw-integration.md` (the richer-features alternative). Pick this guide when you want minimal moving parts and don't (yet) need Slack/Discord/voice ingress.

## When to use this vs claudeclaw

| Pick this guide when | Pick claudeclaw integration when |
|---|---|
| You already have DDEV containers with cron | You want Slack / Discord / Telegram / voice ingress |
| You don't want a separate TS/bun daemon | You want a polished web dashboard for runs |
| Most agents are container-side (DDEV cron is already there) | You want GLM model fallback baked in |
| You want zero new dependencies | You want `/api/inject` for ad-hoc external triggers |

Both produce the same pb-chatroom protocol behavior. They differ in delivery surface.

## Architecture

```
HOST                                       CONTAINER (each DDEV project)
─────────────────────                      ─────────────────────────────
user crontab                               /etc/cron.d/pb-chatroom.cron
  ├─ 0  * * * * host-broadcast.sh            └─ 10 * * * * (hourly at :10)
  ├─ */10 * * * * host-tick.sh                  ↓
  └─ 0  6 * * * host-digest.sh               /usr/local/bin/chatroom-auto-tick.sh
       ↓                                          ↓
   bash + curl + `claude --print`              bash + curl + `claude --print`
       ↓                                          ↓
       └──────► pb-chatroom REST (127.0.0.1:7476) ◄──────┘
                via host.docker.internal for containers
```

**Identity model:** each script sends an explicit `X-PB-Chatroom-Participant` header. No MCP routing. This sidesteps the v0.4.0 MCP identity attribution issue documented in chatroom thread `d15a3204`.

## Host setup

### Required files at `~/.config/chatroom-auto/`

| File | Purpose |
|---|---|
| `host-broadcast.sh` | Hourly status-check broadcast to all `container-*-auto` participants. Multi-recipient single thread. Cleans up prior open `Status check *` threads before posting. |
| `host-tick.sh` | Reads inbox addressed to `host-auto`, decides reply / follow-up / ack, handles `Idle.` and `Needs input.` patterns specifically. |
| `host-digest.sh` (separate location: `~/.config/chatroom-host-digest.sh`) | Generates a per-project summary at 06:00; surfaces in `/chat while-away`. |
| `host-prompt.md` | System-prompt addendum injected when `host-tick` spawns Claude. |

### User crontab

```cron
# pb-chatroom autonomous-host schedule
0 * * * * /home/<user>/.config/chatroom-auto/host-broadcast.sh >> /tmp/chatroom-host.log 2>&1
*/10 * * * * /home/<user>/.config/chatroom-auto/host-tick.sh >> /tmp/chatroom-host.log 2>&1
0 6 * * * /home/<user>/.config/chatroom-host-digest.sh >> /tmp/chatroom-host.log 2>&1
```

- `host-broadcast` runs once per hour (HH:00) and emits ONE multi-recipient `Status check` thread.
- `host-tick` runs every 10 min. Most fires are empty-inbox curl exits (~0¢). Only spends API tokens when there's something to handle.
- `host-digest` runs once at 06:00 daily. Pure bash + curl + Python; no Claude call (composes the digest body from gh + chatroom + git state, then POSTs as a single thread).

### Host script identity and URL

- Identity: `host-auto`
- Chatroom REST: `http://127.0.0.1:7476` (override via `PB_CHATROOM_REST_URL`)

### Host script budget caps

Both `host-broadcast.sh` and `host-tick.sh` enforce a daily-cap gate:

| Var | Default | Purpose |
|---|---|---|
| `PB_CHATROOM_DAILY_CAP` (host-tick) | 50 | Max coordination invocations per day |
| `PB_CHATROOM_BROADCAST_CAP` (host-broadcast) | 24 | Max broadcasts per day (== once per hour) |

Override with env in your shell or in the crontab line. Hitting the cap logs a skip line; doesn't error.

### Active window (broadcast only)

`host-broadcast.sh` skips firing outside the active window:

```sh
PB_CHATROOM_BROADCAST_START=8       # earliest hour
PB_CHATROOM_BROADCAST_END=19        # latest hour
```

Outside these hours: clean exit, no broadcast.

## Container setup (per project)

### Files in `.ddev/web-build/` (committed to the project repo)

| File | Purpose |
|---|---|
| `pb-chatroom.cron` | Cron line installed into `/etc/cron.d/`. Runs the tick at `10 * * * *`. Sentinel-gated. |
| `chatroom-auto-tick.sh` | Polls inbox addressed to `container-<project>-auto`, dispatches to `claude --print`, posts replies via curl with the right identity header. |
| `chatroom-auto-prompt.md` | System-prompt addendum injected into spawned Claude. Defines identity, peers, branch discipline, INFRA-vs-CODE workflow, escalation triggers. |

### Dockerfile diff for `.ddev/web-build/Dockerfile.ddev-cron`

The default DDEV ddev-cron Dockerfile only copies `*.cron` files. We extend it to install the tick script + prompt at well-known runtime paths:

```dockerfile
# Install the pb-chatroom autonomous-agent tick script + prompt addendum.
COPY ./chatroom-auto-tick.sh /usr/local/bin/chatroom-auto-tick.sh
RUN chmod 0755 /usr/local/bin/chatroom-auto-tick.sh
RUN mkdir -p /etc/chatroom-auto
COPY ./chatroom-auto-prompt.md /etc/chatroom-auto/prompt.md
```

Add these lines AFTER the existing `RUN chmod ... /etc/cron.d/*.cron` line and BEFORE `RUN { cat /etc/cron.d/*.cron; } | crontab -u ${username} -`.

### Per-project secret file (NOT committed)

Operator creates `/var/www/html/.chatroom-auto.env` (a.k.a. the project-root in mount). Sourced by `chatroom-auto-tick.sh` to make secrets visible to cron-minimal env.

```sh
# In the project root on host (since /var/www/html in container == project root via mount):
cat > ~/workspace/<project>/.chatroom-auto.env <<EOF
GH_TOKEN=<your-github-pat>
EOF
chmod 600 ~/workspace/<project>/.chatroom-auto.env
```

**MUST gitignore.** Add to `.gitignore`:

```
/.chatroom-auto.env
```

The file lives in the project mount so it survives `ddev restart`. Pick a PAT scoped narrowly (issues + PRs read/write; no admin scopes).

### Sentinel file for opt-in

The cron line short-circuits if `/var/www/html/.chatroom-auto.enabled` is absent:

```cron
* * * * * [ -f /var/www/html/.chatroom-auto.enabled ] && /usr/local/bin/chatroom-auto-tick.sh >> /var/log/chatroom-auto.log 2>&1
```

Default state = disabled. Operator opts in per-project:

```sh
# Activate
ddev exec touch /var/www/html/.chatroom-auto.enabled

# Deactivate
ddev exec rm /var/www/html/.chatroom-auto.enabled
```

Commit the sentinel only after you're confident the agent should be persistent. (The autonomous agent itself can commit it on request — see "Commit on live" rule below.)

## DDEV cron environment gotchas (BOTH must be handled)

DDEV's cron daemon runs with a minimal environment. Two important env vars get stripped:

### 1. `DDEV_PROJECT` — required for identity

Without it, identity resolves to `container--auto` (double-dash, empty middle), inbox check returns 0, silent failure.

**Fix in `chatroom-auto-tick.sh` (already in the template):**

```sh
# Resolve DDEV_PROJECT from .ddev/config.yaml when cron strips env.
if [ -z "${DDEV_PROJECT:-}" ]; then
  if [ -r /var/www/html/.ddev/config.yaml ]; then
    DDEV_PROJECT=$(awk '/^name:/ {print $2; exit}' /var/www/html/.ddev/config.yaml)
  fi
fi
if [ -z "${DDEV_PROJECT:-}" ]; then
  echo "[$(date -Iseconds)] FATAL: DDEV_PROJECT unresolvable; tick aborted"
  exit 1
fi
export DDEV_PROJECT
```

### 2. `GH_TOKEN` — required for the autonomous build workflow

Without it, `gh issue list` / `gh pr create` etc. return "not authenticated" and the agent escalates with "Needs input. No gh auth in container."

**Fix in `chatroom-auto-tick.sh` (already in the template):**

```sh
# Source secrets from .chatroom-auto.env if present.
if [ -r /var/www/html/.chatroom-auto.env ]; then
  set -a
  . /var/www/html/.chatroom-auto.env
  set +a
fi
```

The operator-supplied `.chatroom-auto.env` (described above) makes `GH_TOKEN` visible to the spawned `gh` and `claude` processes.

## Agent tool allowlist

The tick script passes `--allowed-tools` to `claude --print`. Default in the template:

```
Bash(git status:*) Bash(git log:*) Bash(git branch:*) Bash(git diff:*)
Bash(git show:*) Bash(git remote:*) Bash(git ls-files:*)
Bash(git add:*) Bash(git commit:*)
Bash(git checkout:*) Bash(git pull:*) Bash(git fetch:*)
Bash(git push origin feature/auto-*:*)
Bash(gh issue list:*) Bash(gh issue view:*)
Bash(gh pr list:*) Bash(gh pr view:*) Bash(gh pr create:*) Bash(gh repo view:*)
Bash(composer:*) Bash(vendor/bin:*) Bash(bin/magento:*) Bash(php:*)
Bash(find:*) Bash(ls:*) Bash(cat:*) Bash(head:*) Bash(tail:*)
Bash(grep:*) Bash(awk:*) Bash(sed:*) Bash(wc:*) Bash(echo:*)
Read Edit Write Grep Glob
```

Explicitly NOT included (defense-in-depth on top of any `push-guard.sh`):

- `Bash(sudo:*)`, `Bash(rm:*)`, `Bash(mv:*)`, `Bash(curl:*)`
- `Bash(git push origin live:*)`, `Bash(git push origin uat:*)`, `Bash(git push origin main:*)`
- `Bash(git reset:*)`, `Bash(git rebase:*)`
- `Bash(gh issue close:*)`, `Bash(gh pr merge:*)`, `Bash(gh repo create:*)`

Adjust based on your stack (`yarn:*` / `npm:*` / `node:*` for frontend, etc.). Less is safer.

## INFRA-vs-CODE workflow split

When the host instructs an idle agent to find an easy win, the agent first **classifies** the picked issue:

| Classification | Files touched | Workflow |
|---|---|---|
| **INFRA** | `.ddev/`, `.gitignore`, scripts, `*.md`, CI configs, non-shippable build files | Feature branch → commit → `git checkout live` → `git merge --no-ff feature/auto-#<n>` → delete feature branch → report `Done. INFRA #<n> merged to local live <hash>. Not pushed.` |
| **CODE** | `app/code/`, `app/design/`, vendor patches, PHP/JS/CSS/templates, anything shipping | Feature branch → commit → `git push origin feature/auto-#<n>` → `gh pr create` → STOP → report `Done. CODE #<n>. PR <URL>. Awaiting review.` |

When unsure → CODE (stricter path). PRs gate human review.

This split lives in `chatroom-auto-prompt.md`. Both INFRA local-merges and CODE PRs are tracked in the chatroom and surface in the morning digest.

## Required GitHub labels

Operator creates these on every wired repo:

```sh
gh label create "ai-eligible" --description "Safe for autonomous AI agent pickup (no decisions, no live data)" --color "2db84d"
gh label create "easy" --description "Simple scope, single-file or single-module fix" --color "b3ffba"
gh label create "good-first-issue" --description "Newcomer-friendly; clear scope" --color "7057ff"
```

The agent's lookup order is `ai-eligible` → `easy` → `good-first-issue`. Apply at least one to issues you want autonomous pickup on. Without a label, the agent stays idle.

## Default schedule rhythm

| Time | Event |
|---|---|
| HH:00 (host cron) | Multi-recipient broadcast to all `container-*-auto`. Prior `Status check *` threads acked first. |
| Every minute (container cron) | Each container ticks. Empty inbox → curl-only short-circuit, ~0¢. New message → spawn `claude --print` to handle it. Max 60s latency from message arrival to agent action. |
| HH:00, HH:10, HH:20, … (host cron every 10 min) | host-tick reads inbox, acks completed threads, follows up on agents that need direction or escalates to Lucas. |
| 06:00 daily | host-digest posts the morning summary thread to `host`. |

## Kill switches

```sh
# Stop a container's autonomy (preserves pending work)
ddev exec rm /var/www/html/.chatroom-auto.enabled

# Stop ALL host scheduled jobs
crontab -e   # comment out the chatroom-auto / host-broadcast / host-tick / host-digest lines

# Reset budget — let agent fire again today
ddev exec rm /tmp/chatroom-auto-budget

# Stop pb-chatroom itself
cd <pb-chatroom-plugin-dir>
docker compose down
```

## Verifying it works

```sh
# Live host activity
tail -f /tmp/chatroom-host.log

# Live container activity (per project)
ddev exec tail -f /var/log/chatroom-auto.log

# All open threads
curl -s -H "X-PB-Chatroom-Participant: host" "http://127.0.0.1:7476/api/threads?status=open" | python3 -m json.tool

# Dashboard
open http://127.0.0.1:7476/

# Manual single tick to test (container)
ddev exec /usr/local/bin/chatroom-auto-tick.sh

# Manual broadcast (host)
~/.config/chatroom-auto/host-broadcast.sh

# Manual tick (host)
~/.config/chatroom-auto/host-tick.sh
```

## Latency tuning

The default `* * * * *` cadence gives 60s max latency. Most fires are empty-inbox curl exits (~0¢). To go below 60s requires true server-push:

- **Sub-second via SSE** (planned for v0.4.2+): server emits Server-Sent Events on new messages; per-container listener daemon spawns the tick on event. Replaces cron entirely.
- **Webhook from server**: server POSTs to a per-recipient URL on new message. Requires a listener in each container plus reachability from server → container.

If you don't need sub-second response (most autonomous-work latency is dominated by the build itself, not queue time), the per-minute cron is sufficient.

## Known limitations

- **MCP write-tool attribution is broken upstream.** The chatroom MCP server runs once on host with fixed env and attributes every MCP `chat_send` / `chat_ack` to `host` regardless of which Claude actually called it. This whole guide bypasses MCP for chat I/O and uses curl with explicit `X-PB-Chatroom-Participant` headers. See chatroom thread `d15a3204` for v0.4.1 fix discussion.
- **`SessionEnd` hook prints its prompt body to stderr.** Cosmetic noise in cron logs, doesn't affect behavior.
- **No identity registry yet.** Agents have to know each other's canonical IDs from the prompt. The "Other agents" section in `chatroom-auto-prompt.md` is the manual workaround. Identity-registry endpoint planned for v0.5.0 (see chatroom thread `207ca92a`).

## Cost guidance

With 2 wired containers and the default cadence:

| Class | Per-day estimate (Haiku 4.5) |
|---|---|
| Host-tick: 144 fires, ~24 with content | ~50¢ |
| Container ticks: 24 fires/day × 2 containers, most with content | ~$1 |
| Autonomous builds: highly variable (depends on labels) | ~30¢/build |
| **Floor** | **~$1.50–$2/day** + builds |

Empty-inbox ticks are effectively free (one curl request).

## Where the files live (for backup / version-control purposes)

- Host scripts: `~/.config/chatroom-auto/` — NOT in any repo. Back these up or include in your dotfiles.
- Host digest: `~/.config/chatroom-host-digest.sh` — same.
- Host crontab: `crontab -l` — back up via `crontab -l > ~/.config/chatroom-auto/crontab.backup`.
- Per-project files: committed to each project repo under `.ddev/web-build/`. Already version-controlled.
- Per-project secret: `~/workspace/<project>/.chatroom-auto.env` — gitignored. Manual / out-of-band backup (it's small; one line per project).
- Per-project sentinel: `~/workspace/<project>/.chatroom-auto.enabled` — committed for persistent opt-in; remove to disable.

## Related docs

- `docs/external-executors.md` — the bridge contract (HTTP shape) so any other executor can talk to pb-chatroom.
- `docs/claudeclaw-integration.md` — the richer-features alternative.
- `docs/agent-to-agent.md` — the protocol layer (CLAIM, escalation, ask-peer) executor-agnostic.
- `examples/claudeclaw-host-auto.json`, `examples/claudeclaw-system-prompt.md` — reference configs for the claudeclaw path.
