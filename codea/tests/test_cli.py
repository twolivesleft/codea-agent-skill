"""Tests for CLI options not covered by MCP-level tests.

These tests invoke the codea CLI directly via Click's CliRunner to verify
options like --output, --input, --no-deps, and specific file pull/push.
"""

import pytest
from click.testing import CliRunner
from pathlib import Path

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
