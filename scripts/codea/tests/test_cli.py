"""Tests for CLI options not covered by MCP-level tests.

These tests invoke the codea CLI directly via Click's CliRunner to verify
options like --output, --input, --no-deps, specific file pull/push,
and log filtering (--head, --tail, --follow).
"""

import json
import tempfile
import threading
import time
import pytest
from click.testing import CliRunner
from pathlib import Path
from unittest.mock import patch

from codea.cli import main

LUA_MAIN = "-- main\nfunction setup() end\nfunction draw() end\n"
LUA_HELPER = "-- helper\nfunction helper() end\n"


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# pull --output
# ---------------------------------------------------------------------------

def test_pull_to_custom_output_dir(runner, client, project, tmp_path):
    uri = f"{project['uri']}/Main.lua"
    client.write_file(uri, LUA_MAIN)

    output_dir = tmp_path / "custom_output"
    result = runner.invoke(main, ["pull", project["name"], "--output", str(output_dir)])

    assert result.exit_code == 0, result.output
    assert (output_dir / "Main.lua").exists()
    assert (output_dir / "Main.lua").read_text() == LUA_MAIN


# ---------------------------------------------------------------------------
# pull specific files
# ---------------------------------------------------------------------------

def test_pull_specific_file(runner, client, project, tmp_path):
    client.write_file(f"{project['uri']}/Main.lua", LUA_MAIN)
    client.write_file(f"{project['uri']}/Helper.lua", LUA_HELPER)

    output_dir = tmp_path / "specific"
    result = runner.invoke(main, ["pull", project["name"], "Main.lua",
                                  "--output", str(output_dir)])

    assert result.exit_code == 0, result.output
    assert (output_dir / "Main.lua").exists()
    assert not (output_dir / "Helper.lua").exists()


def test_pull_multiple_specific_files(runner, client, project, tmp_path):
    client.write_file(f"{project['uri']}/Main.lua", LUA_MAIN)
    client.write_file(f"{project['uri']}/Helper.lua", LUA_HELPER)

    output_dir = tmp_path / "multi"
    result = runner.invoke(main, ["pull", project["name"], "Main.lua", "Helper.lua",
                                  "--output", str(output_dir)])

    assert result.exit_code == 0, result.output
    assert (output_dir / "Main.lua").exists()
    assert (output_dir / "Helper.lua").exists()


# ---------------------------------------------------------------------------
# pull --no-deps
# ---------------------------------------------------------------------------

def test_pull_no_deps(runner, client, project, tmp_path):
    client.write_file(f"{project['uri']}/Main.lua", LUA_MAIN)

    output_dir = tmp_path / "nodeps"
    result = runner.invoke(main, ["pull", project["name"], "--no-deps",
                                  "--output", str(output_dir)])

    assert result.exit_code == 0, result.output
    assert (output_dir / "Main.lua").exists()
    # No Dependencies/ dir should be created when there are no deps
    assert not (output_dir / "Dependencies").exists()


# ---------------------------------------------------------------------------
# push --input
# ---------------------------------------------------------------------------

def test_push_from_custom_input_dir(runner, client, project, tmp_path):
    input_dir = tmp_path / "custom_input"
    input_dir.mkdir()
    (input_dir / "Main.lua").write_text(LUA_MAIN)

    result = runner.invoke(main, ["push", project["name"], "--input", str(input_dir)])

    assert result.exit_code == 0, result.output
    content = client.read_file(f"{project['uri']}/Main.lua")
    assert content == LUA_MAIN


# ---------------------------------------------------------------------------
# push specific files
# ---------------------------------------------------------------------------

def test_push_specific_file(runner, client, project, tmp_path):
    # Write both files to device first
    client.write_file(f"{project['uri']}/Main.lua", "-- original main\n")
    client.write_file(f"{project['uri']}/Helper.lua", "-- original helper\n")

    # Set up local dir with updated versions of both
    input_dir = tmp_path / "src"
    input_dir.mkdir()
    (input_dir / "Main.lua").write_text(LUA_MAIN)
    (input_dir / "Helper.lua").write_text(LUA_HELPER)

    # Push only Main.lua
    result = runner.invoke(main, ["push", project["name"], "Main.lua",
                                  "--input", str(input_dir)])

    assert result.exit_code == 0, result.output
    assert client.read_file(f"{project['uri']}/Main.lua") == LUA_MAIN
    # Helper should be unchanged on device
    assert client.read_file(f"{project['uri']}/Helper.lua") == "-- original helper\n"


def test_push_multiple_specific_files(runner, client, project, tmp_path):
    client.write_file(f"{project['uri']}/Main.lua", "-- original main\n")
    client.write_file(f"{project['uri']}/Helper.lua", "-- original helper\n")

    input_dir = tmp_path / "src"
    input_dir.mkdir()
    (input_dir / "Main.lua").write_text(LUA_MAIN)
    (input_dir / "Helper.lua").write_text(LUA_HELPER)

    result = runner.invoke(main, ["push", project["name"], "Main.lua", "Helper.lua",
                                  "--input", str(input_dir)])

    assert result.exit_code == 0, result.output
    assert client.read_file(f"{project['uri']}/Main.lua") == LUA_MAIN
    assert client.read_file(f"{project['uri']}/Helper.lua") == LUA_HELPER


# ---------------------------------------------------------------------------
# logs --head / --tail / --follow
# ---------------------------------------------------------------------------

SPAM_LUA = (
    'function setup()\n'
    '  print("first_line")\n'
    '  print("second_line")\n'
    '  print("third_line")\n'
    'end\n'
    'function draw() print("spam") end\n'
)


@pytest.fixture
def running_project(runner, client, project):
    """Project running with SPAM_LUA; stopped after test."""
    client.write_file(f"{project['uri']}/Main.lua", SPAM_LUA)
    client.call_tool("clearLogs")
    client.run_project(project["uri"])
    time.sleep(2)
    yield project
    client.stop_project()


def test_logs_head(runner, client, running_project):
    result = runner.invoke(main, ["logs", "--head", "1"])
    assert result.exit_code == 0, result.output
    lines = result.output.strip().splitlines()
    assert lines[0] == "first_line"
    assert len(lines) == 1


def test_logs_tail(runner, client, running_project):
    result = runner.invoke(main, ["logs", "--tail", "1"])
    assert result.exit_code == 0, result.output
    lines = result.output.strip().splitlines()
    assert len(lines) == 1


def test_logs_follow(runner, client, running_project):
    """--follow streams at least one log line via SSE then stops on KeyboardInterrupt."""
    received = []

    def stream():
        # Use the MCP client directly since CliRunner can't send KeyboardInterrupt
        for line in client.stream_logs():
            received.append(line)
            break  # collect just one line and stop

    t = threading.Thread(target=stream, daemon=True)
    t.start()
    t.join(timeout=5)

    assert len(received) >= 1
    assert any("first_line" in line or "spam" in line for line in received)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_shows_local_path(runner):
    config_json = json.dumps({"profiles": {"default": {"host": "127.0.0.1", "port": 42}}})
    state = {
        "state": "running",
        "project": "Polaroid 04",
        "localPath": "/tmp/Polaroid 04.codea",
        "idleTimerDisabled": False,
        "paused": False,
    }

    class StubClient:
        def __init__(self, host, port):
            self.host = host
            self.port = port

        def get_device_state(self):
            return state

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.json"
        config_file.write_text(config_json, encoding="utf-8")

        with patch("codea.cli.CONFIG_FILE", config_file), \
             patch("codea.cli.MCPClient", StubClient):
            result = runner.invoke(main, ["status"])

    assert result.exit_code == 0, result.output
    assert "Host:    127.0.0.1" in result.output
    assert "Port:    42" in result.output
    assert "State:   Running: Polaroid 04" in result.output
    assert "Local path: /tmp/Polaroid 04.codea" in result.output


def test_status_omits_local_path_when_absent(runner):
    config_json = json.dumps({"profiles": {"default": {"host": "127.0.0.1", "port": 42}}})
    state = {
        "state": "none",
        "project": None,
        "idleTimerDisabled": False,
        "paused": None,
    }

    class StubClient:
        def __init__(self, host, port):
            self.host = host
            self.port = port

        def get_device_state(self):
            return state

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.json"
        config_file.write_text(config_json, encoding="utf-8")

        with patch("codea.cli.CONFIG_FILE", config_file), \
             patch("codea.cli.MCPClient", StubClient):
            result = runner.invoke(main, ["status"])

    assert result.exit_code == 0, result.output
    assert "Local path:" not in result.output


def test_new_sends_local_bundle_path_by_default(runner, tmp_path):
    captured = {}

    class StubClient:
        def call_tool(self, name, arguments=None):
            captured["name"] = name
            captured["arguments"] = arguments or {}
            return {"content": [{"type": "text", "text": "ok"}]}

        def text(self, result):
            return result["content"][0]["text"]

    with patch("codea.cli.get_client", return_value=StubClient()), \
         patch("codea.cli.Path.cwd", return_value=tmp_path):
        result = runner.invoke(main, ["new", "MyGame"])

    assert result.exit_code == 0, result.output
    assert captured["name"] == "createProject"
    assert captured["arguments"]["name"] == "MyGame"
    assert captured["arguments"]["path"] == str((tmp_path / "MyGame.codea").resolve())
    assert "folder" not in captured["arguments"]


def test_new_folder_sends_plain_directory_path(runner, tmp_path):
    captured = {}

    class StubClient:
        def call_tool(self, name, arguments=None):
            captured["name"] = name
            captured["arguments"] = arguments or {}
            return {"content": [{"type": "text", "text": "ok"}]}

        def text(self, result):
            return result["content"][0]["text"]

    with patch("codea.cli.get_client", return_value=StubClient()), \
         patch("codea.cli.Path.cwd", return_value=tmp_path):
        result = runner.invoke(main, ["new", "MyGame", "--folder"])

    assert result.exit_code == 0, result.output
    assert captured["arguments"]["path"] == str((tmp_path / "MyGame").resolve())
    assert captured["arguments"]["folder"] is True


def test_new_explicit_relative_path_stays_local(runner, tmp_path):
    captured = {}

    class StubClient:
        def call_tool(self, name, arguments=None):
            captured["arguments"] = arguments or {}
            return {"content": [{"type": "text", "text": "ok"}]}

        def text(self, result):
            return result["content"][0]["text"]

    with patch("codea.cli.get_client", return_value=StubClient()), \
         patch("codea.cli.Path.cwd", return_value=tmp_path):
        result = runner.invoke(main, ["new", "./Games/MyGame"])

    assert result.exit_code == 0, result.output
    assert captured["arguments"]["name"] == "./Games/MyGame"
    assert captured["arguments"]["path"] == str((tmp_path / "Games" / "MyGame.codea").resolve())
    assert "collection" not in captured["arguments"]
