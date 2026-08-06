---
description: Read all messages in a thread in chronological order
argument-hint: "<thread_id>"
---

Read a thread directly via REST — do NOT use the `chat_read_thread` MCP tool.
(The MCP server is a single shared host process; identity resolution there
is broken for every non-host caller. See docs/ddev-cron-executor.md.)

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

Then fetch:

```sh
curl -s "${PB_CHATROOM_REST_URL}/api/threads/$ARG_THREAD_ID" \
  -H "X-PB-Chatroom-Participant: ${PARTICIPANT}"
```

Format the `messages` array as a chronological list, one entry per message:
`<from_participant> -> <to_participant> · <kind> · <created_at>` followed by
the body. If the curl exits non-zero or returns 404, surface the error along
with the resolved `PB_CHATROOM_REST_URL` so the operator can diagnose
connectivity.
