---
description: Send a reply message to an existing thread via REST
argument-hint: "<thread_id> -- <body>"
---

Send a message to an existing thread directly via REST — do NOT use the
`chat_send` MCP tool. (The MCP server is a single shared host process;
identity resolution there is broken for every non-host caller — every
MCP-routed `chat_send` attributes as `host` regardless of who actually
called it. See docs/ddev-cron-executor.md.)

Resolve identity and REST URL in shell:

```sh
PARTICIPANT="${PB_CHATROOM_PARTICIPANT_ID:-${DDEV_PROJECT:+container-${DDEV_PROJECT}}}"
PARTICIPANT="${PARTICIPANT:-host}"

if [ -n "${DDEV_PROJECT:-}" ] || [ -f /.dockerenv ]; then
  PB_CHATROOM_REST_HOST="${PB_CHATROOM_REST_HOST:-host.docker.internal}"
else
  PB_CHATROOM_REST_HOST="${PB_CHATROOM_REST_HOST:-127.0.0.1}"
fi
PB_CHATROOM_REST_URL="http://${PB_CHATROOM_REST_HOST}:7476"
```

Then send:

```sh
curl -s -X POST "${PB_CHATROOM_REST_URL}/api/threads/$ARG_THREAD_ID/messages" \
  -H "Content-Type: application/json" \
  -H "X-PB-Chatroom-Participant: ${PARTICIPANT}" \
  -d "$(python3 -c 'import json,sys; print(json.dumps({"body": sys.argv[1]}))' "$ARG_BODY")"
```

Output the result as: `message sent: <id>`. If the curl exits non-zero,
surface the error along with the resolved `PB_CHATROOM_REST_URL`.
