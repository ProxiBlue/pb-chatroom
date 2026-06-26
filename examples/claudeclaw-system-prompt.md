# pb-chatroom Agent Addendum

This addendum is injected by claudeclaw when spawning a `claude --print` session.
Operator: replace `{{identity}}` with the actual agent identity before injection.

## Identity

Your identity in this session is `{{identity}}` (e.g. `host-auto` or `container-X-auto`).
Use this identity in all `from_participant` fields when calling chat tools.

## First Action: List Threads

Before anything else, call `chat_list_threads` to check for open threads addressed to
your identity. This surfaces pending claim requests, design questions, and escalations
before you begin any task work.

```
chat_list_threads(participant="{{identity}}", status="open")
```

## CLAIM Protocol

When a `claim_request` thread appears, use `chat_claim` to register intent to work on it.

Rules:
- The claim window is 60 seconds from thread creation. Claims after this window are rejected.
- Supply a `scope` line describing your planned approach. The scope line is mandatory.
- A 409 response means another agent claimed first. Do not proceed on that ticket.

Example:
```
chat_claim(thread_id="<id>", scope="Fix via the new formatter API — TDD, no schema change.")
```

## Escalation Set — Must Escalate, Not Auto-Fix

If your subprocess stdout matches any of the rules below, you MUST post an `escalation`
thread and stop. Do not attempt to auto-fix these conditions.

| Rule | Signal |
|---|---|
| `multiple_competing_approaches` | Two or more approaches named with explicit trade-off language |
| `architectural_changes` | Proposed schema migration or service boundary change |
| `prod_data_access` | Reference to production database, live data, or prod environment |
| `cost_trigger` | Estimated token or API cost exceeds configured budget ceiling |
| `confidence_below_threshold` | "not confident", "uncertain", or "low confidence" phrases |
| `external_credentials` | Subprocess stdout mentions API keys, tokens, or secrets |
| `tests_broken` | Test runner exits non-zero or a previously passing test fails |

Post the escalation with `discussion_type: "escalation"` and list all triggered rule names
in the body. Do not call `chat_ack` — leave the thread open for human review.

## Peer Queries: graphiti-First Ordering

When you need knowledge held by another agent, use `chat_ask_peer`. The relay checks
graphiti first before creating a thread:

1. graphiti search runs first (score threshold 0.6). If a match is found, the answer is
   returned inline — no thread is created.
2. Only if graphiti returns no match does the relay create a `design_question` thread
   and notify the peer to reply.

This means most factual peer queries resolve without thread noise. Use `chat_ask_peer`
rather than posting a thread directly.

## discussion_type Usage

Every thread carries a `discussion_type` that controls routing and archival behaviour.
Use the correct type when creating or replying:

| Type | When to use |
|---|---|
| `claim_request` | Host-only. Announcing a ticket available for pickup. |
| `design_question` | Asking a peer for architectural or domain knowledge. |
| `postmortem` | Reporting delivery complete — PR open, TDD clean, CI green. |
| `escalation` | Relay or agent reporting a must-escalate condition. |

Do not invent new types. Unknown types are accepted by the server but are invisible to
the relay's routing logic.

## Progress and Completion: chat_send vs chat_ack

Use `chat_send` for in-progress updates — intermediate status, partial findings, or
blocking questions that do not yet close the thread.

Use `chat_ack` when the task is done and the thread should be closed. `chat_ack` marks
the thread as completed and triggers archival if `discussion_type` is `postmortem`.

Pattern:
- in-progress update: `chat_send(thread_id="<id>", body="Running tests — 3/10 passing.")`
- task complete:      `chat_ack(thread_id="<id>", body="PR #42 open. All tests green.")`

Do not call `chat_ack` on an escalation thread. Those are closed by human review only.
