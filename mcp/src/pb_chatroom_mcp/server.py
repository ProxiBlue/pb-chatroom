"""MCP server entry point for pb-chatroom."""

from __future__ import annotations

import asyncio

import httpx
from mcp.server import Server
from pydantic_settings import BaseSettings

from pb_chatroom_mcp.identity import resolve_participant_id


class Settings(BaseSettings):
    server_url: str = 'http://127.0.0.1:7476'
    mcp_host: str = '127.0.0.1'
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

    from pb_chatroom_mcp.tools.chat_read_thread import chat_read_thread
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
        raise ValueError(f'Unknown tool: {name}')

    return server


async def serve() -> None:
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    settings = Settings()
    mcp_server = build_mcp_server()

    manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,
        json_response=False,
        stateless=False,
    )

    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount

    starlette_app = Starlette(
        routes=[Mount('/', app=manager.handle_request)],
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
