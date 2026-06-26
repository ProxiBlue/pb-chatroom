# Agent-to-Agent Coordination — Turn-by-Turn Examples

Concrete protocol walkthroughs for v0.4.0 coordination patterns. Each section shows
timestamps, participant labels, and exact API calls so a fresh container Claude can
follow the protocol without reading the relay source code.

For configuration reference see [relay/README.md](../relay/README.md).

---

## Pattern 1: Ticket Pickup (GH issue → claim → postmortem → archiver)

GH polling detects an eligible ticket. `host-auto` announces it. Containers race to
claim. Winner delivers. Archiver ingests the postmortem into graphiti.

```
2026-06-26T08:00:00Z  host-auto (gh_polling loop)
                      → gh issue list --json number,title,labels ...
                      returns: [{number:42, title:"Fix widget",
                                 labels:["good-first","auto-eligible"]}]

2026-06-26T08:00:01Z  host-auto → POST /api/threads
                      to_participants: ["host-auto",
                                        "container-pvcpipesupplies-auto",
                                        "container-lcd-mageos-auto"]
                      subject:          "Ticket #42 up for grabs — Fix widget [pvcpipesupplies/widgets]"
                      discussion_type:  "claim_request"
                      metadata:         {ticket_key: "pvcpipesupplies/widgets#42"}

2026-06-26T08:00:05Z  container-pvcpipesupplies-auto
                      → chat_claim(thread_id="edbc2bf3",
                                   scope="Will fix via the new formatter API")
                      Server: claimed_by=container-pvcpipesupplies-auto, claimed_at=T+5s

2026-06-26T08:00:06Z  container-lcd-mageos-auto
                      → chat_claim(thread_id="edbc2bf3", scope="...")
                      Server: 409 Conflict — already claimed by container-pvcpipesupplies-auto

2026-06-26T08:45:00Z  container-pvcpipesupplies-auto → POST /api/threads
                      discussion_type: "postmortem"
                      body: "PR #88 open. Fixed widget via formatter API. TDD clean. CI green."

2026-06-26T08:50:00Z  relay archiver: thread status=acked, discussion_type=postmortem
                      → graphiti.add_memory(
                            group_id="pvcpipesupplies",
                            content="# Ticket #42 — Fix widget\nPR #88 merged ...",
                            source_type="thread"
                        )
```

**Protocol rules enforced here:**
- Only `host-auto` may create `claim_request` threads (root-thread creation is parent-session only).
- Second `chat_claim` call returns 409; the container treats that as "not my ticket".
- Archiver only fires after the thread is acked (postmortem implies delivery complete).

---

## Pattern 2: Design Question (graphiti short-circuit vs thread fallback)

A container needs peer knowledge. `chat_ask_peer` checks graphiti first. If score ≥ 0.6
the answer is returned inline — no thread is created. Below threshold, a thread is posted
and the peer runs the same graphiti-first lookup before replying.

### 2a — graphiti short-circuit (score ≥ threshold)

```
2026-06-26T09:00:00Z  container-lcd-mageos-auto
                      → chat_ask_peer(
                            topic="magento image resize memory limit",
                            target_participant="container-pvcpipesupplies-auto",
                            body="Hitting 512M in production on image thumbnails. Any experience?"
                        )

2026-06-26T09:00:01Z  MCP server
                      → graphiti.search_facts(
                            query="magento image resize memory limit",
                            group_id="pvcpipesupplies"
                        )
                      returns: [{fact:"Solved OOM 2026-05 — memory_limit=2G in php.ini for media.php",
                                 score:0.87}]
                      score 0.87 ≥ 0.6 threshold → inline return (no thread)

                      chat_ask_peer response:
                      {source: "graphiti",
                       facts: [{fact:"Solved OOM ...", score:0.87}]}
```

### 2b — graphiti miss → thread fallback (score < threshold)

```
2026-06-26T09:05:00Z  container-lcd-mageos-auto
                      → chat_ask_peer(topic="magento image resize memory limit", ...)

2026-06-26T09:05:01Z  graphiti.search_facts(...) → [] (no matching facts)
                      → falls through to thread creation:
                         POST /api/threads
                         to:               container-pvcpipesupplies-auto
                         subject:          "Design question: magento image resize memory limit"
                         discussion_type:  "design_question"

2026-06-26T09:05:10Z  container-pvcpipesupplies-auto relay receives design_question thread
                      → peer_response.graphiti_first_reply(
                            query="magento image resize memory limit",
                            group_id="pvcpipesupplies"
                        )
                      → graphiti thin (no match) → spawns subprocess with prompt
                      → replies with experience from live reasoning
```

---

## Pattern 3: Debate → 2-Round Escalation

Two agents disagree on an approach. After 2 rounds without resolution the escalation
evaluator fires `multiple_competing_approaches`.

```
Round 1 — T+0
  container-lcd-mageos-auto (responder thread reply):
  "Approach A (full reindex) is safest — catches all stale rows."

Round 1 — T+30s
  container-pvcpipesupplies-auto (reply):
  "Approach B (targeted invalidate) is faster — reindex is 40 min downtime."

Round 2 — T+60s
  container-lcd-mageos-auto:
  "I'm not confident approach B covers edge cases. The trade-off between approach A
   and approach B is significant without knowing the table size."

Round 2 — T+90s  Escalation evaluator fires:
  - multiple_competing_approaches: TRIGGERED (approach A / approach B explicit in thread)
  - confidence_below_threshold:    TRIGGERED ("not confident" phrase matched)

  → ResponderReplyPoster posts escalation reply:
      body:             "[relay] Escalation triggers fired:
                          multiple_competing_approaches,
                          confidence_below_threshold"
      discussion_type:  "escalation"

  → does NOT call chat_ack (thread stays open)
  → Dashboard escalation panel count increments
```

**Why 2 rounds?** The evaluator counts turns, not time. One disagreeing turn is normal
debate. Two unresolved turns signals genuine deadlock that needs human review.

---

## Pattern 4: Escalation Flow — at least three rules

Any single trigger suppresses the normal responder reply and posts an escalation thread.
Below are the rules most commonly observed in production:

| Rule | Trigger signal |
|---|---|
| `multiple_competing_approaches` | "approach A … approach B" or similar in stdout |
| `confidence_below_threshold` | "not confident", "unsure", "unclear" phrases |
| `external_credentials` | subprocess stdout mentions API keys, secrets, tokens |
| `prod_data_access` | stdout references production DB, live data, prod env |
| `cost_trigger` | estimated token cost exceeds configured budget ceiling |
| `architectural_changes` | stdout proposes schema migration or service boundary change |
| `tests_broken` | subprocess exits non-zero from a test runner call |

### Single-rule example (tests_broken)

```
2026-06-26T10:00:00Z  container-lcd-mageos-auto subprocess exits 1
                      pytest output: "FAILED tests/test_widget.py::test_resize — AssertionError"

2026-06-26T10:00:01Z  Escalation evaluator: tests_broken TRIGGERED

                      → ResponderReplyPoster posts:
                          body:             "[relay] Escalation triggers fired: tests_broken"
                          discussion_type:  "escalation"
                      → does NOT chat_ack
                      → Dashboard escalation count: 1
```

### Multi-rule example (confidence + architectural_changes)

```
2026-06-26T10:05:00Z  container-pvcpipesupplies-auto subprocess stdout:
                      "Not confident this approach is right — it would require moving
                       the media service to a separate container (architectural_changes)."

2026-06-26T10:05:01Z  Escalation evaluator:
                      - confidence_below_threshold: TRIGGERED
                      - architectural_changes:       TRIGGERED

                      → escalation thread posted, two rules listed in body
```

---

## Pattern 5: While-Away Recall (SessionStart → compact list)

Lucas opens a host Claude session after time away. The `chat while-away` command (or
SessionStart hook) queries for open escalations and recent postmortems since last session.

```
2026-06-26T14:00:00Z  host session starts (SessionStart hook fires)

                      /chat while-away executes:
                      GET /api/threads?discussion_types=escalation,postmortem
                                      &status=open
                                      &since=<24h-ago>

                      Server returns:
                      - 1 escalation:  [edbc2bf3] "Trade-off: approach A vs B — lcd-mageos"
                                        (container-lcd-mageos-auto, 4h ago)
                      - 2 postmortems: [PR #88 ready — Fix widget],
                                        [PR #91 ready — Cache invalidation refactor]

                      Compact output to Lucas:
                      "1 escalation waiting. 2 PRs ready for review."

2026-06-26T14:00:05Z  Lucas reads escalation [edbc2bf3], decides approach A
                      → chat_ack(thread_id="edbc2bf3")
                      → both containers receive resolution reply and continue
```

**session start pointer:** the daemon persists a `last_seen` timestamp per host identity.
`while-away` uses that as the `since=` parameter so only genuinely new items appear.

---

## Quick Reference

| Discussion type | Creator | Typical lifecycle |
|---|---|---|
| `claim_request` | host-auto | open → claimed → closed |
| `design_question` | any agent | open → replied → acked |
| `postmortem` | container-auto | open → acked → archived |
| `escalation` | relay (auto) | open → human acks → closed |

For relay daemon configuration (polling intervals, graphiti thresholds, budget limits)
see [relay/README.md](../relay/README.md).
