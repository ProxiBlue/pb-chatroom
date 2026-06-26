"""Tests for MCP scaffold: httpx client, identity stamping, MCP server instance."""

from __future__ import annotations


def test_it_builds_an_httpx_client_with_the_server_base_url_from_settings():
    from pb_chatroom_mcp.server import Settings, build_http_client

    settings = Settings(server_url='http://127.0.0.1:9999')
    client = build_http_client(settings)
    assert str(client.base_url) == 'http://127.0.0.1:9999'


def test_it_stamps_the_x_pb_chatroom_participant_header_from_the_resolved_identity(
    monkeypatch,
):
    monkeypatch.setenv('PB_CHATROOM_PARTICIPANT_ID', 'test-agent')
    monkeypatch.delenv('DDEV_PROJECT', raising=False)

    from pb_chatroom_mcp.server import Settings, build_http_client

    settings = Settings(server_url='http://127.0.0.1:7476')
    client = build_http_client(settings)
    assert client.headers['x-pb-chatroom-participant'] == 'test-agent'


def test_it_falls_back_to_the_host_identity_when_no_env_vars_are_set(monkeypatch):
    monkeypatch.delenv('PB_CHATROOM_PARTICIPANT_ID', raising=False)
    monkeypatch.delenv('DDEV_PROJECT', raising=False)

    from pb_chatroom_mcp.server import Settings, build_http_client

    settings = Settings(server_url='http://127.0.0.1:7476')
    client = build_http_client(settings)
    assert client.headers['x-pb-chatroom-participant'] == 'host'


def test_it_builds_an_mcp_server_instance_with_no_tools_registered_by_default():
    from pb_chatroom_mcp.server import build_mcp_server

    server = build_mcp_server()
    assert server.name == 'pb-chatroom-mcp'
    assert server._tool_cache == {}


def test_it_reads_pb_chatroom_server_url_from_the_environment_when_set(monkeypatch):
    monkeypatch.setenv('PB_CHATROOM_SERVER_URL', 'http://192.168.1.100:8080')

    from pb_chatroom_mcp.server import Settings

    settings = Settings()
    assert settings.server_url == 'http://192.168.1.100:8080'
