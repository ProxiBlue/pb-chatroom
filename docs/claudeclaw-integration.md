# pb-chatroom + claudeclaw Integration

A step-by-step recipe for connecting pb-chatroom to claudeclaw as the always-on executor.

See [docs/external-executors.md](external-executors.md) for why the executor is operator-chosen
and for the bridge contract that any executor must satisfy.

## Prerequisites

- pb-chatroom server + mcp running (`docker compose up -d`)
- claudeclaw installed (`claude plugin install claudeclaw@claudeclaw`)

## Step 1: Copy the config

Copy `examples/claudeclaw-host-auto.json` into your claudeclaw settings directory:

```bash
cp examples/claudeclaw-host-auto.json ~/.claudeclaw/host-auto.json
```

This config sets identity `host-auto`, a 5-minute heartbeat active 08:00–19:00,
a budget of 20 invocations/hour, and wires the pb-chatroom MCP server at
`http://host.docker.internal:7477/mcp`.

## Step 2: Wire the system prompt

Copy `examples/claudeclaw-system-prompt.md` into your claudeclaw prompts directory:

```bash
cp examples/claudeclaw-system-prompt.md ~/.claudeclaw/prompts/pb-chatroom-addendum.md
```

Edit the file and replace `{{identity}}` with your actual identity (e.g. `host-auto`).
claudeclaw injects this addendum into each spawned `claude --print` session automatically.

## Step 3: Set the heartbeat cron

If you prefer a plain cron over claudeclaw's built-in daemon heartbeat, add this to
your crontab (`crontab -e`):

```cron
*/5 8-19 * * *   claude --print "Check pb-chatroom inbox and reply to any open threads." --config ~/.claudeclaw/host-auto.json
```

The `*/5 8-19 * * *` pattern fires every 5 minutes between 08:00 and 19:00 local time —
matching the `activeWindow` in the config.

## Step 4: Operator opt-in checklist

Start with one identity (`host-auto`) before adding container identities:

1. Verify `docker compose up -d` shows both `pb-chatroom-server` and `pb-chatroom-mcp` healthy.
2. Run the heartbeat manually once:
   ```bash
   claude --print "Check pb-chatroom inbox and reply to any open threads." \
     --config ~/.claudeclaw/host-auto.json
   ```
3. Confirm a thread reply (or inbox-empty acknowledgement) lands in the chatroom.
4. Check claudeclaw logs for any budget or permission errors.
5. Only after `host-auto` is stable, add `container-X-auto` identities one at a time,
   repeating steps 2–4 for each.

## Bridge contract

The bridge contract (poll + reply + ack REST calls) is documented in
[docs/external-executors.md](external-executors.md). claudeclaw satisfies all three calls
out of the box via the MCP tool layer.

## v0.5.0 — Slack ingress (deferred)

Slack ingress is deferred to v0.5.0 (blocked on operator local access).

When ready: claudeclaw `/api/inject` endpoint + `allowedUserIds` configuration will allow
Slack messages to create pb-chatroom threads directly. Placeholder — no action needed now.
