"""Tests for MCP tool: chat_ask_peer (graphiti-first short-circuit)."""

from __future__ import annotations

import httpx


class FakeGraphitiSearchClient:
    """Configurable fake for GraphitiSearchClient protocol."""

    def __init__(
        self,
        facts: list[dict] | None = None,
        raise_on_search: bool = False,
    ) -> None:
        self._facts = facts or []
        self._raise = raise_on_search
        self.last_query: str | None = None
        self.last_group_id: str | None = None

    async def search_facts(self, query: str, group_id: str) -> list[dict]:
        self.last_query = query
        self.last_group_id = group_id
        if self._raise:
            raise RuntimeError('graphiti unreachable')
        return self._facts


def make_chatroom_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url='http://127.0.0.1:7476',
        transport=httpx.MockTransport(handler),
    )


def thread_created_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        201,
        json={
            'id': 'thread-new',
            'subject': 'Design question: auth flow',
            'discussion_type': 'design_question',
        },
    )


async def test_it_returns_inline_graphiti_results_when_relevance_is_above_threshold():
    from pb_chatroom_mcp.tools.chat_ask_peer import chat_ask_peer

    facts = [{'fact': 'JWT uses RS256', 'score': 0.9, 'uuid': 'abc-1'}]
    graphiti = FakeGraphitiSearchClient(facts=facts)

    async with make_chatroom_client(thread_created_handler) as client:
        result = await chat_ask_peer(
            topic='auth flow',
            target_participant='container-worker',
            body='How does auth work?',
            chatroom_client=client,
            graphiti_client=graphiti,
            relevance_threshold=0.6,
        )

    assert result == {'source': 'graphiti', 'facts': facts}


async def test_it_does_not_post_a_thread_when_graphiti_results_suffice():
    from pb_chatroom_mcp.tools.chat_ask_peer import chat_ask_peer

    post_calls = []

    def tracking_handler(request: httpx.Request) -> httpx.Response:
        post_calls.append(request)
        return httpx.Response(201, json={'id': 'thread-new'})

    facts = [{'fact': 'JWT uses RS256', 'score': 0.9, 'uuid': 'abc-1'}]
    graphiti = FakeGraphitiSearchClient(facts=facts)

    async with make_chatroom_client(tracking_handler) as client:
        await chat_ask_peer(
            topic='auth flow',
            target_participant='container-worker',
            body='How does auth work?',
            chatroom_client=client,
            graphiti_client=graphiti,
            relevance_threshold=0.6,
        )

    assert len(post_calls) == 0


async def test_it_posts_a_design_question_thread_when_graphiti_returns_no_facts():
    from pb_chatroom_mcp.tools.chat_ask_peer import chat_ask_peer

    posted_payloads = []

    def capture_handler(request: httpx.Request) -> httpx.Response:
        import json

        posted_payloads.append(json.loads(request.content))
        return httpx.Response(201, json={'id': 'thread-new', 'discussion_type': 'design_question'})

    graphiti = FakeGraphitiSearchClient(facts=[])

    async with make_chatroom_client(capture_handler) as client:
        result = await chat_ask_peer(
            topic='auth flow',
            target_participant='container-worker',
            body='How does auth work?',
            chatroom_client=client,
            graphiti_client=graphiti,
            relevance_threshold=0.6,
        )

    assert len(posted_payloads) == 1
    assert posted_payloads[0]['discussion_type'] == 'design_question'
    assert result == {'id': 'thread-new', 'discussion_type': 'design_question'}


async def test_it_posts_a_design_question_thread_when_graphiti_results_are_below_threshold():
    from pb_chatroom_mcp.tools.chat_ask_peer import chat_ask_peer

    posted_payloads = []

    def capture_handler(request: httpx.Request) -> httpx.Response:
        import json

        posted_payloads.append(json.loads(request.content))
        return httpx.Response(201, json={'id': 'thread-new', 'discussion_type': 'design_question'})

    facts = [{'fact': 'vaguely related', 'score': 0.3, 'uuid': 'abc-2'}]
    graphiti = FakeGraphitiSearchClient(facts=facts)

    async with make_chatroom_client(capture_handler) as client:
        result = await chat_ask_peer(
            topic='auth flow',
            target_participant='container-worker',
            body='How does auth work?',
            chatroom_client=client,
            graphiti_client=graphiti,
            relevance_threshold=0.6,
        )

    assert len(posted_payloads) == 1
    assert posted_payloads[0]['discussion_type'] == 'design_question'


async def test_it_derives_group_id_from_target_participant_using_the_archiver_pattern():
    from pb_chatroom_mcp.tools.chat_ask_peer import chat_ask_peer

    facts = [{'fact': 'some fact', 'score': 0.9, 'uuid': 'abc-3'}]
    graphiti = FakeGraphitiSearchClient(facts=facts)

    async with make_chatroom_client(thread_created_handler) as client:
        # container-worker-auto → worker
        await chat_ask_peer(
            topic='deploy',
            target_participant='container-worker-auto',
            body='Q?',
            chatroom_client=client,
            graphiti_client=graphiti,
        )

    assert graphiti.last_group_id == 'worker'

    # host-session-42 → host
    graphiti2 = FakeGraphitiSearchClient(facts=facts)
    async with make_chatroom_client(thread_created_handler) as client:
        await chat_ask_peer(
            topic='deploy',
            target_participant='host-session-42',
            body='Q?',
            chatroom_client=client,
            graphiti_client=graphiti2,
        )
    assert graphiti2.last_group_id == 'host'

    # container-db → db
    graphiti3 = FakeGraphitiSearchClient(facts=facts)
    async with make_chatroom_client(thread_created_handler) as client:
        await chat_ask_peer(
            topic='deploy',
            target_participant='container-db',
            body='Q?',
            chatroom_client=client,
            graphiti_client=graphiti3,
        )
    assert graphiti3.last_group_id == 'db'


async def test_it_falls_through_to_thread_creation_when_graphiti_is_unreachable_fail_open():
    from pb_chatroom_mcp.tools.chat_ask_peer import chat_ask_peer

    posted_payloads = []

    def capture_handler(request: httpx.Request) -> httpx.Response:
        import json

        posted_payloads.append(json.loads(request.content))
        return httpx.Response(201, json={'id': 'thread-new', 'discussion_type': 'design_question'})

    graphiti = FakeGraphitiSearchClient(raise_on_search=True)

    async with make_chatroom_client(capture_handler) as client:
        result = await chat_ask_peer(
            topic='auth flow',
            target_participant='container-worker',
            body='How does auth work?',
            chatroom_client=client,
            graphiti_client=graphiti,
            relevance_threshold=0.6,
        )

    assert len(posted_payloads) == 1
    assert posted_payloads[0]['discussion_type'] == 'design_question'
    assert result == {'id': 'thread-new', 'discussion_type': 'design_question'}
