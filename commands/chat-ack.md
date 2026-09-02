---
description: Acknowledge a thread, optionally sending a final reply body
argument-hint: "<thread_id> [-- <body>]"
---

Acknowledge a thread directly via REST — do NOT use the `chat_ack` MCP tool.
(The MCP server is a single shared host process; identity resolution there
is broken for every non-host caller — every MCP-routed `chat_ack` attributes
as `host` regardless of who actually called it, and can silently close a
thread under the wrong identity. See docs/ddev-cron-executor.md.)

Resolve identity and REST URL in shell:

```sh
PARTICIPANT="${PB_CHATROOM_PARTICIPANT_ID:-${DDEV_PROJECT:+container-$(echo "$DDEV_PROJECT" | tr 'A-Z' 'a-z')}}"
PARTICIPANT="${PARTICIPANT:-host}"

if [ -n "${DDEV_PROJECT:-}" ] || [ -f /.dockerenv ]; then
  PB_CHATROOM_REST_HOST="${PB_CHATROOM_REST_HOST:-host.docker.internal}"
else
  PB_CHATROOM_REST_HOST="${PB_CHATROOM_REST_HOST:-127.0.0.1}"
fi
PB_CHATROOM_REST_URL="http://${PB_CHATROOM_REST_HOST}:7476"
```

Then ack (body optional — omit `-d` entirely, or pass it, to include a
closing message; the server defaults the body to `"Ack"` when none is sent):

```sh
curl -s -X POST "${PB_CHATROOM_REST_URL}/api/threads/$ARG_THREAD_ID/ack" \
  -H "Content-Type: application/json" \
  -H "X-PB-Chatroom-Participant: ${PARTICIPANT}" \
  ${ARG_BODY:+-d "$(python3 -c 'import json,sys; print(json.dumps({"body": sys.argv[1]}))' "$ARG_BODY")"}
```

Marks the thread status as `acked`. Output: `thread acked: $ARG_THREAD_ID`.
If the curl exits non-zero, surface the error along with the resolved
`PB_CHATROOM_REST_URL`.

## Nudge the chatroom→Graphiti ingestion (host callers only)

If this ack is running on the **host** (`$PARTICIPANT` resolved to `host`,
not a `container-*` id — containers have no writable path to the host state
dir today), append the thread id to the priority queue the ingest-chatroom
cron sweep drains first, so this thread gets ingested on the *next* run
instead of waiting for its normal listing pass:

```sh
if [ "$PARTICIPANT" = "host" ]; then
  mkdir -p "$HOME/.pb-graphiti/state"
  echo "$ARG_THREAD_ID" >> "$HOME/.pb-graphiti/state/chatroom-priority-queue.txt"
fi
```

Best-effort — do not fail the ack if this write fails (e.g. dir not
writable). Container-originated acks don't have an equivalent nudge path
yet; the thread still gets picked up by the ingest sweep's normal listing
pass within its cadence, just without the priority jump.

## After acking

Acking closes the thread's business — it is not an invitation to keep
digging into that thread or wander into other open threads unless the user
actually asked you to work through the inbox. Return to whatever you were
doing before the chatroom pulled you in. If the user's actual request is
still open, answer that — don't let chatroom triage become the main thread.
