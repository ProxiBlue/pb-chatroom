"""Structural tests for slash command files under commands/."""

from pathlib import Path

COMMANDS_DIR = Path(__file__).parent.parent.parent / 'commands'


def read_command(name: str) -> str:
    return (COMMANDS_DIR / name).read_text()


def test_it_has_a_commands_chat_threads_open_md_file_referencing_post_api_threads() -> None:
    content = read_command('chat-threads-open.md')
    assert 'POST /api/threads' in content


def test_it_has_a_commands_chat_send_md_file_referencing_the_chat_send_mcp_tool() -> None:
    content = read_command('chat-send.md')
    assert 'chat_send' in content


def test_it_has_a_commands_chat_threads_md_file_referencing_the_chat_list_threads_mcp_tool() -> None:  # noqa: E501
    content = read_command('chat-threads.md')
    assert 'chat_list_threads' in content


def test_it_has_a_commands_chat_read_md_file_referencing_the_chat_read_thread_mcp_tool() -> None:
    content = read_command('chat-read.md')
    assert 'chat_read_thread' in content


def test_it_has_a_commands_chat_ack_md_file_referencing_the_chat_ack_mcp_tool() -> None:
    content = read_command('chat-ack.md')
    assert 'chat_ack' in content


def test_it_includes_a_description_and_argument_hint_in_each_command_frontmatter() -> None:
    for name in [
        'chat-threads-open.md',
        'chat-send.md',
        'chat-threads.md',
        'chat-read.md',
        'chat-ack.md',
    ]:
        content = read_command(name)
        assert 'description:' in content, f'{name} missing description'
        assert 'argument-hint:' in content, f'{name} missing argument-hint'


def test_it_stamps_the_x_pb_chatroom_participant_header_in_the_chat_threads_open_invocation() -> None:  # noqa: E501
    content = read_command('chat-threads-open.md')
    assert 'X-PB-Chatroom-Participant' in content
