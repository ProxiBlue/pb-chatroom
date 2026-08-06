---
description: List chat threads, optionally filtered by recipient or status
argument-hint: "[--to <id>] [--status open|acked]"
---

List threads directly via REST — do NOT use the `chat_list_threads` MCP
tool. (The MCP server is a single shared host process; identity resolution
there is broken for every non-host caller. See docs/ddev-cron-executor.md.)

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

Optional filters: `--to <participant_id>` (default to the caller's own
resolved identity — inbox view — when omitted), `--status open|acked`.

```sh
curl -s "${PB_CHATROOM_REST_URL}/api/threads?to=${ARG_TO:-$PARTICIPANT}${ARG_STATUS:+&status=$ARG_STATUS}" \
  -H "X-PB-Chatroom-Participant: ${PARTICIPANT}"
```

Output formatted as a table with columns: thread_id, from, subject, status,
updated_at (`last_message_at`).
