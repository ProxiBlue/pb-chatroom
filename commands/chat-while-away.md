---
description: Show threads needing attention since your last session
argument-hint: "[--since <ISO datetime>]"
---

Query the chatroom for open escalation and postmortem threads from the last 24 hours.

Uses `GET /api/threads?discussion_types=escalation,postmortem&status=open&since=<24h-ago>` against the pb-chatroom server.

Calculate `<24h-ago>` as the current UTC time minus 24 hours in ISO 8601 format. If `--since` is provided, use that value instead.

Format the result as a compact list:
- "N escalation(s) waiting" — link each thread to `/threads/<id>` with its subject
- "N postmortem(s) ready for review" — link each thread to `/threads/<id>` with its subject

If nothing matches, output: "All clear — no escalations or open postmortems in the last 24 hours."
