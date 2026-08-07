---
description: Ask a peer a design question — graphiti-first short-circuit, falls back to a REST thread
argument-hint: "<target_participant> <topic> -- <body>"
---

Ask a peer participant a design question, graphiti-first — do NOT use the
`chat_ask_peer` MCP tool. (The MCP server is a single shared host process;
identity resolution there is broken for every non-host caller — every
MCP-routed chatroom write attributes as `host` regardless of who actually
called it. See docs/ddev-cron-executor.md.) This command reproduces the same
graphiti-first / thread-fallback logic (see
`mcp/src/pb_chatroom_mcp/tools/chat_ask_peer.py` and
`docs/agent-to-agent.md` pattern 2) using tools that carry correct identity.

## Step 1 — derive the peer's graphiti group_id

Strip the `container-` prefix and any trailing `-auto` from
`$ARG_TARGET_PARTICIPANT`; a `host*` participant maps to group `host`.

```
container-pvcpipesupplies-auto -> pvcpipesupplies
container-lcd-mageos           -> lcd-mageos
host-auto                      -> host
```

## Step 2 — graphiti-first lookup

Call the graphiti MCP tool directly (this call is not chatroom-identity-scoped,
so the MCP-vs-REST bug does not apply here):

```
mcp__plugin_pb-graphiti_graphiti__search_memory_facts(
  query: "$ARG_TOPIC",
  group_ids: ["<derived-group-id>"]
)
```

If the top-scoring fact has `score >= 0.6`, STOP here and report it inline —
do not create a thread. Output format:

```
answered from graphiti (score <score>): <fact>
```

## Step 3 — fallback: post a design_question thread via REST

Only reached if graphiti returned nothing, or the top score was below 0.6,
or the search errored (fail-open, same as the original tool).

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

Then post the thread:

```sh
curl -s -X POST "${PB_CHATROOM_REST_URL}/api/threads" \
  -H "Content-Type: application/json" \
  -H "X-PB-Chatroom-Participant: ${PARTICIPANT}" \
  -d "$(python3 -c 'import json,sys; print(json.dumps({
        "to": sys.argv[1],
        "subject": f"Design question: {sys.argv[2]}",
        "body": sys.argv[3],
        "discussion_type": "design_question",
      }))' "$ARG_TARGET_PARTICIPANT" "$ARG_TOPIC" "$ARG_BODY")"
```

Output the result as: `design question posted: <id>`. If the curl exits
non-zero, surface the error along with the resolved `PB_CHATROOM_REST_URL`.

## Replying to a design_question thread you receive

The peer side of pattern 2 is not a separate command — a container that
receives a `design_question` thread just runs its own graphiti-first check
(same Step 1/2 above, scoped to its own project's group_id) before replying
via `/chat send`.
