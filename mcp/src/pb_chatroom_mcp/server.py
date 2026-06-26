"""MCP server entry point for pb-chatroom."""

from __future__ import annotations

import asyncio

import httpx
from mcp.server import Server
from pydantic_settings import BaseSettings

from pb_chatroom_mcp.identity import resolve_participant_id


class Settings(BaseSettings):
    server_url: str = 'http://127.0.0.1:7476'
    # Bind 0.0.0.0 inside the container so Docker's host:7477 → container:7477
    # port-forward actually reaches the listener. docker-compose binds the
    # host-side port to 127.0.0.1 — external isolation lives at that layer,
    # not at uvicorn's listener.
    mcp_host: str = '0.0.0.0'
    mcp_port: int = 7477
    ask_peer_relevance_threshold: float = 0.6
    graphiti_url: str = 'http://localhost:7478'  # graphiti MCP HTTP endpoint

    model_config = {'env_prefix': 'PB_CHATROOM_', 'extra': 'ignore'}


def build_http_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.server_url,
        headers={'X-PB-Chatroom-Participant': resolve_participant_id()},
    )


def build_mcp_server() -> Server:
    import json

    from mcp.types import TextContent, Tool

    from pb_chatroom_mcp.tools.chat_ack import chat_ack
    from pb_chatroom_mcp.tools.chat_ask_peer import chat_ask_peer
    from pb_chatroom_mcp.tools.chat_claim import chat_claim
    from pb_chatroom_mcp.tools.chat_read_thread import chat_read_thread
    from pb_chatroom_mcp.tools.chat_send import chat_send
    from pb_chatroom_mcp.tools.list_threads import chat_list_threads

    server = Server(name='pb-chatroom-mcp')

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name='chat_list_threads',
                description=(
                    'List chatroom threads. By default returns threads addressed to the '
                    "caller's own resolved identity (their inbox). Pass to='' (empty string) "
                    'to list ALL threads regardless of recipient — useful for cross-container '
                    'observability and debugging.'
                ),
                inputSchema={
                    'type': 'object',
                    'properties': {
                        'to': {
                            'type': 'string',
                            'description': (
                                'Recipient participant ID. Omit (or null) to default to the '
                                "caller's own identity (inbox view). Pass an empty string ('') "
                                'to disable the filter and list ALL threads.'
                            ),
                        },
                        'status': {
                            'type': 'string',
                            'enum': ['open', 'acked'],
                            'description': 'Optional status filter.',
                        },
                    },
                },
            ),
            Tool(
                name='chat_read_thread',
                description='Fetch a thread and its messages from the pb-chatroom server.',
                inputSchema={
                    'type': 'object',
                    'properties': {
                        'thread_id': {
                            'type': 'string',
                            'description': 'The ID of the thread to fetch.',
                        },
                    },
                    'required': ['thread_id'],
                },
            ),
            Tool(
                name='chat_send',
                description=(
                    'Post a reply message to an existing thread. Subagent writes are '
                    'restricted to existing threads — root-thread creation is parent-only '
                    'via the /chat threads-open slash command.'
                ),
                inputSchema={
                    'type': 'object',
                    'properties': {
                        'thread_id': {
                            'type': 'string',
                            'description': 'The ID of the thread to reply to.',
                        },
                        'body': {
                            'type': 'string',
                            'description': 'Message body (plain text or markdown).',
                        },
                    },
                    'required': ['thread_id', 'body'],
                },
            ),
            Tool(
                name='chat_ack',
                description=(
                    'Mark a thread as acknowledged / done. Optionally post a closing '
                    'reply body in the same call.'
                ),
                inputSchema={
                    'type': 'object',
                    'properties': {
                        'thread_id': {
                            'type': 'string',
                            'description': 'The ID of the thread to ack.',
                        },
                        'body': {
                            'type': 'string',
                            'description': 'Optional closing reply body.',
                        },
                    },
                    'required': ['thread_id'],
                },
            ),
            Tool(
                name='chat_claim',
                description=(
                    'Claim a ticket-pickup thread (claim_request discussion_type). '
                    'First valid claim wins; idempotent for the same agent.'
                ),
                inputSchema={
                    'type': 'object',
                    'properties': {
                        'thread_id': {
                            'type': 'string',
                            'description': 'ID of the claim_request thread.',
                        },
                        'scope': {
                            'type': 'string',
                            'description': 'One-line description of your intended approach/scope.',
                        },
                    },
                    'required': ['thread_id', 'scope'],
                },
            ),
            Tool(
                name='chat_ask_peer',
                description=(
                    'Ask another Claude participant a design question. '
                    'Searches graphiti first — if relevant facts exist, returns them inline '
                    'without posting a thread. Falls through to posting a design_question thread '
                    'if graphiti is thin.'
                ),
                inputSchema={
                    'type': 'object',
                    'properties': {
                        'topic': {
                            'type': 'string',
                            'description': 'Short search term for graphiti.',
                        },
                        'target_participant': {
                            'type': 'string',
                            'description': 'Participant ID to ask.',
                        },
                        'body': {
                            'type': 'string',
                            'description': 'Full question body if a thread is created.',
                        },
                    },
                    'required': ['topic', 'target_participant', 'body'],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        settings = Settings()
        if name == 'chat_list_threads':
            async with build_http_client(settings) as client:
                result = await chat_list_threads(
                    client=client,
                    to=arguments.get('to'),
                    status=arguments.get('status'),
                )
            text = result if isinstance(result, str) else json.dumps(result)
            return [TextContent(type='text', text=text)]
        if name == 'chat_read_thread':
            async with build_http_client(settings) as client:
                result = await chat_read_thread(arguments.get('thread_id'), client)
            text = str(result)
            return [TextContent(type='text', text=text)]
        if name == 'chat_send':
            async with build_http_client(settings) as client:
                result = await chat_send(
                    thread_id=arguments.get('thread_id', ''),
                    body=arguments.get('body', ''),
                    client=client,
                )
            text = result if isinstance(result, str) else json.dumps(result)
            return [TextContent(type='text', text=text)]
        if name == 'chat_ack':
            async with build_http_client(settings) as client:
                result = await chat_ack(
                    thread_id=arguments.get('thread_id', ''),
                    body=arguments.get('body'),
                    client=client,
                )
            text = result if isinstance(result, str) else json.dumps(result)
            return [TextContent(type='text', text=text)]
        if name == 'chat_claim':
            async with build_http_client(settings) as client:
                result = await chat_claim(
                    thread_id=arguments.get('thread_id', ''),
                    scope=arguments.get('scope', ''),
                    client=client,
                )
            text = result if isinstance(result, str) else json.dumps(result)
            return [TextContent(type='text', text=text)]
        if name == 'chat_ask_peer':
            from pb_chatroom_mcp.tools.chat_ask_peer import GraphitiSearchClient

            class _HttpGraphitiClient:
                """Thin wrapper: calls graphiti MCP via HTTP."""

                def __init__(self, base_url: str) -> None:
                    self._base_url = base_url

                async def search_facts(self, query: str, group_id: str) -> list[dict]:
                    async with httpx.AsyncClient(base_url=self._base_url) as gc:
                        r = await gc.post(
                            '/search_memory_facts',
                            json={'query': query, 'group_id': group_id},
                        )
                        return r.json()

            graphiti_client: GraphitiSearchClient = _HttpGraphitiClient(settings.graphiti_url)
            async with build_http_client(settings) as client:
                result = await chat_ask_peer(
                    topic=arguments.get('topic', ''),
                    target_participant=arguments.get('target_participant', ''),
                    body=arguments.get('body', ''),
                    chatroom_client=client,
                    graphiti_client=graphiti_client,
                    relevance_threshold=settings.ask_peer_relevance_threshold,
                    caller_participant=resolve_participant_id(),
                )
            text = result if isinstance(result, str) else json.dumps(result)
            return [TextContent(type='text', text=text)]
        raise ValueError(f'Unknown tool: {name}')

    return server


async def serve() -> None:
    from contextlib import asynccontextmanager

    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    settings = Settings()
    mcp_server = build_mcp_server()

    manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,
        # Stateless + JSON response = the simplest deployment mode. Each request
        # is self-contained (no session lifecycle to manage across calls) and
        # responses come back as plain JSON rather than SSE streams.
        json_response=True,
        stateless=True,
    )

    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount

    @asynccontextmanager
    async def lifespan(app):
        # StreamableHTTPSessionManager.run() initialises the task group that
        # backs every request — without entering this context, every incoming
        # request raises 'Task group is not initialized'.
        async with manager.run():
            yield

    starlette_app = Starlette(
        routes=[Mount('/', app=manager.handle_request)],
        lifespan=lifespan,
    )

    config = uvicorn.Config(
        starlette_app,
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level='info',
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    asyncio.run(serve())


if __name__ == '__main__':
    main()
