---
description: List chat threads, optionally filtered by recipient or status
argument-hint: "[--to <id>] [--status open|acked]"
---

List chat threads using the `chat_list_threads` MCP tool.

Optional filters:
- `--to <participant_id>`: filter by recipient
- `--status open|acked`: filter by thread status

Uses MCP tool `chat_list_threads` with optional `to` and `status` parameters.

Output formatted as a table with columns: thread_id, from, subject, status, updated_at.
