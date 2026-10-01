---
description: Open a new root thread (REST-only; subagents cannot create root threads)
argument-hint: "<to> <subject> -- <body>"
---

Open a new root chat thread by calling `POST /api/threads` directly.

Resolve participant identity in shell:

```sh
PARTICIPANT="${PB_CHATROOM_PARTICIPANT_ID:-${DDEV_PROJECT:+container-$(echo "$DDEV_PROJECT" | tr 'A-Z' 'a-z')}}"
PARTICIPANT="${PARTICIPANT:-host}"
```

Resolve the REST server URL — context-aware. From inside a DDEV / dev
container the host's 127.0.0.1 is unreachable; the host is reached via
the docker-bridge gateway (host.docker.internal). From the operator's
host shell, localhost is correct.

```sh
if [ -n "${DDEV_PROJECT:-}" ] || [ -f /.dockerenv ]; then
  PB_CHATROOM_REST_HOST="${PB_CHATROOM_REST_HOST:-host.docker.internal}"
else
  PB_CHATROOM_REST_HOST="${PB_CHATROOM_REST_HOST:-127.0.0.1}"
fi
PB_CHATROOM_REST_URL="http://${PB_CHATROOM_REST_HOST}:7476"
```

Then send the request. Build the JSON body with `jq -n`, not hand-built string
interpolation — a hand-built `"{\"to\": \"$ARG_TO\", ...}"` string breaks (HTTP
422) the moment the subject or body contains a backtick, a double quote, or a
newline:

```sh
jq -n --arg to "$ARG_TO" --arg subject "$ARG_SUBJECT" --arg body "$ARG_BODY" \
  '{to: $to, subject: $subject, body: $body}' \
  | curl -s -X POST "${PB_CHATROOM_REST_URL}/api/threads" \
      -H "Content-Type: application/json" \
      -H "X-PB-Chatroom-Participant: ${PARTICIPANT}" \
      --data-binary @-
```

Output the result as: `thread opened: <id>`. If the curl exits non-zero,
surface the error along with the resolved `PB_CHATROOM_REST_URL` so the
operator can diagnose connectivity (typically: docker-compose stack not
running, or wrong host for the current context — override via the
`PB_CHATROOM_REST_HOST` env var).
