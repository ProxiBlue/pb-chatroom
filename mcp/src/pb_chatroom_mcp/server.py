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
                    'List chatroom threads addressed to a participant. '
                    "Defaults to the caller's own resolved identity."
                ),
                inputSchema={
                    'type': 'object',
                    'properties': {
                        'to': {
                            'type': 'string',
                            'description': 'Recipient participant ID (default: caller identity).',
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
