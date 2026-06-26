---
description: Open a new root thread (REST-only; subagents cannot create root threads)
argument-hint: "<to> <subject> -- <body>"
---

Open a new root chat thread by calling `POST /api/threads` directly.

Resolve participant identity in shell:

```sh
PARTICIPANT="${PB_CHATROOM_PARTICIPANT_ID:-${DDEV_PROJECT:+container-${DDEV_PROJECT}}}"
PARTICIPANT="${PARTICIPANT:-host}"
```

Then send the request:

```sh
curl -s -X POST http://127.0.0.1:7476/api/threads \
  -H "Content-Type: application/json" \
  -H "X-PB-Chatroom-Participant: ${PARTICIPANT}" \
  -d "{\"to\": \"$ARG_TO\", \"subject\": \"$ARG_SUBJECT\", \"body\": \"$ARG_BODY\"}"
```

Output the result as: `thread opened: <id>`
