"""Tests for running projects and runtime operations."""

import time
import pytest
from codea.mcp_client import MCPError

DRAW_LUA = """\
function setup()
    _testValue = 42
end
function draw()
    background(0)
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


def test_screenshot_without_project(client):
    client.stop_project()
    time.sleep(1)
    screenshot = client.capture_screenshot()
    assert screenshot is not None
    assert len(screenshot) > 0


def _file_uri(project, filename):
    return f"{project['uri']}/{filename}"
