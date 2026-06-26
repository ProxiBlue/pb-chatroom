"""ResponderReplyPoster — turns a DispatchResult into a chatroom REST call."""

from __future__ import annotations

from pb_chatroom_relay.client import ChatroomClient
from pb_chatroom_relay.dispatcher import DispatchResult, DispatchStatus


class ResponderReplyPoster:
    def __init__(self, client: ChatroomClient) -> None:
        self._client = client

    async def post(self, thread_id: str, dispatch_result: DispatchResult) -> None:
        status = dispatch_result.status

        if status in (DispatchStatus.REFUSED_BUDGET, DispatchStatus.SKIPPED):
            return

        if status == DispatchStatus.TIMED_OUT:
            await self._client.post_message(thread_id, '[relay] dispatch timed out')
            return

        if status == DispatchStatus.FAILED:
            await self._client.post_message(
                thread_id,
                f'[relay] dispatch failed (rc={dispatch_result.returncode})',
            )
            return

        # SUCCESS
        body = dispatch_result.stdout.decode('utf-8').rstrip()
        lines = body.splitlines()

        # Find last non-empty line
        last_nonempty = ''
        for line in reversed(lines):
            if line.strip():
                last_nonempty = line
                break

        if last_nonempty == 'DONE':
            # Strip the DONE marker line
            done_idx = len(lines) - 1
            while done_idx >= 0 and not lines[done_idx].strip():
                done_idx -= 1
            # done_idx now points to the DONE line
            cleaned_lines = lines[:done_idx]
            cleaned_body = '\n'.join(cleaned_lines).rstrip()
            await self._client.ack_thread(thread_id, body=cleaned_body)
        else:
            await self._client.post_message(thread_id, body)
