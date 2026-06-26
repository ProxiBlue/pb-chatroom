---
description: Acknowledge a thread, optionally sending a final reply body
argument-hint: "<thread_id> [-- <body>]"
---

Acknowledge a thread using the `chat_ack` MCP tool.

Uses MCP tool `chat_ack` with:
- `thread_id`: the thread to acknowledge
- `body` (optional): a final reply message to include with the acknowledgement

Marks the thread status as `acked`.
