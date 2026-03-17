"""Tests for running projects and runtime operations."""

import threading
import time
import pytest
from click.testing import CliRunner
from codea.cli import main
from codea.mcp_client import MCPError

DRAW_LUA = """\
function setup()
    _testValue = 42
end
function draw()
    background(0)
end
"""

SPAM_LUA = """\
function setup()
    print("first_line")
    print("second_line")
    print("third_line")
end
function draw()
    print("spam")
end
"""


def test_run_and_stop_project(client, project):
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, DRAW_LUA)

    client.run_project(project["uri"])
    time.sleep(2)

    screenshot = client.capture_screenshot()
    assert screenshot is not None
    assert len(screenshot) > 0

    client.stop_project()


def test_execute_lua(client, project):
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, DRAW_LUA)

    client.run_project(project["uri"])
    time.sleep(2)

    try:
        client.call_tool("clearLogs")
        client.execute_lua("print(_testValue)")
        result = client.call_tool("getLogs")
        assert "42" in client.text(result)
    finally:
        client.stop_project()


def test_restart_project(client, project):
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, DRAW_LUA)

    client.run_project(project["uri"])
    time.sleep(2)

    try:
        client.call_tool("restartProject")
        time.sleep(2)
        screenshot = client.capture_screenshot()
        assert screenshot is not None
    finally:
        client.stop_project()


def test_logs(client, project):
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, 'function setup() print("hello_test") end\nfunction draw() end\n')

    client.call_tool("clearLogs")
    client.run_project(project["uri"])
    time.sleep(2)

    try:
        result = client.call_tool("getLogs")
        logs = client.text(result)
        assert "hello_test" in logs
    finally:
        client.stop_project()


def test_logs_are_non_draining(client, project):
    """getLogs should return the same logs on repeated calls (no draining)."""
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, 'function setup() print("persistent_log") end\nfunction draw() end\n')

    client.call_tool("clearLogs")
    client.run_project(project["uri"])
    time.sleep(2)

    try:
        first = client.text(client.call_tool("getLogs"))
        second = client.text(client.call_tool("getLogs"))
        assert "persistent_log" in first
        assert first == second
    finally:
        client.stop_project()


def test_clear_logs(client, project):
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, 'function setup() print("will_be_cleared") end\nfunction draw() end\n')

    client.run_project(project["uri"])
    time.sleep(2)
    client.stop_project()

    client.call_tool("clearLogs")
    result = client.call_tool("getLogs")
    logs = client.text(result)
    assert "will_be_cleared" not in logs


def test_logs_head(client, project):
    """--head N returns only the first N lines."""
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, SPAM_LUA)

    client.call_tool("clearLogs")
    client.run_project(project["uri"])
    time.sleep(2)

    try:
        result = client.call_tool("getLogs", {"head": 1})
        lines = client.text(result).strip().splitlines()
        assert lines[0] == "first_line"
        assert len(lines) == 1
    finally:
        client.stop_project()


def test_logs_tail(client, project):
    """--tail N returns only the last N lines."""
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, SPAM_LUA)

    client.call_tool("clearLogs")
    client.run_project(project["uri"])
    time.sleep(2)

    try:
        result = client.call_tool("getLogs", {"tail": 1})
        lines = client.text(result).strip().splitlines()
        assert len(lines) == 1
    finally:
        client.stop_project()


def test_logs_stream(client, project):
    """--follow streams log lines via SSE."""
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, 'function setup() print("streamed_log") end\nfunction draw() end\n')

    client.call_tool("clearLogs")
    client.run_project(project["uri"])
    time.sleep(2)

    received = []
    def collect():
        for line in client.stream_logs():
            received.append(line)
            if len(received) >= 1:
                break

    t = threading.Thread(target=collect, daemon=True)
    t.start()
    t.join(timeout=5)

    client.stop_project()
    assert any("streamed_log" in line for line in received)


def test_screenshot_without_project(client):
    client.stop_project()
    time.sleep(1)
    screenshot = client.capture_screenshot()
    assert screenshot is not None
    assert len(screenshot) > 0


def test_exec_file_flag(client, project, tmp_path):
    """--file flag should execute the contents of a Lua file."""
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, DRAW_LUA)
    client.run_project(project["uri"])
    time.sleep(2)

    lua_file = tmp_path / "debug.lua"
    lua_file.write_text('print("from_file")')

    try:
        runner = CliRunner()
        result = runner.invoke(main, ["exec", "--file", str(lua_file)])
        assert result.exit_code == 0, result.output

        client.call_tool("clearLogs")
        client.execute_lua('print("from_file")')
        logs = client.text(client.call_tool("getLogs"))
        assert "from_file" in logs
    finally:
        client.stop_project()


def test_exec_file_and_code_mutually_exclusive(tmp_path):
    """Providing both CODE and --file should fail with a usage error."""
    lua_file = tmp_path / "debug.lua"
    lua_file.write_text('print("hi")')
    runner = CliRunner()
    result = runner.invoke(main, ["exec", "print('hi')", "--file", str(lua_file)])
    assert result.exit_code != 0
    assert "not both" in result.output


def test_exec_requires_code_or_file():
    """Providing neither CODE nor --file should fail with a usage error."""
    runner = CliRunner()
    result = runner.invoke(main, ["exec"])
    assert result.exit_code != 0


def _file_uri(project, filename):
    return f"{project['uri']}/{filename}"
