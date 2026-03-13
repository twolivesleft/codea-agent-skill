"""Tests for pause/resume and getProjectPaused across legacy and modern runtimes."""

import time
import pytest
from codea.mcp_client import MCPError

DRAW_LUA = """\
function setup() end
function draw()
    background(0)
end
"""

# Runtime variants to test
RUNTIMES = ["legacy", "modern"]


def _file_uri(project, filename):
    return f"{project['uri']}/{filename}"


def _run_project_with_runtime(client, project, runtime):
    """Set the project runtime, push Main.lua, and run it."""
    client.call_tool("setRuntime", {"path": project["uri"], "runtime": runtime})
    client.write_file(_file_uri(project, "Main.lua"), DRAW_LUA)
    client.run_project(project["uri"])
    time.sleep(2)


# ---------------------------------------------------------------------------
# getProjectPaused
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("runtime", RUNTIMES)
def test_get_paused_initially_not_paused(client, project, runtime):
    """Project should report not paused immediately after launch."""
    _run_project_with_runtime(client, project, runtime)
    try:
        result = client.text(client.call_tool("getProjectPaused"))
        assert result.strip() == "not paused"
    finally:
        client.stop_project()


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_pause_and_resume(client, project, runtime):
    """Pausing then resuming should be reflected by getProjectPaused."""
    _run_project_with_runtime(client, project, runtime)
    try:
        client.execute_lua("viewer.paused = true")
        time.sleep(0.5)
        result = client.text(client.call_tool("getProjectPaused"))
        assert result.strip() == "paused"

        client.execute_lua("viewer.paused = false")
        time.sleep(0.5)
        result = client.text(client.call_tool("getProjectPaused"))
        assert result.strip() == "not paused"
    finally:
        client.stop_project()


# ---------------------------------------------------------------------------
# getIdleTimerDisabled
# ---------------------------------------------------------------------------

def test_idle_timer_get_after_set(client):
    """getIdleTimerDisabled should reflect the value set by setIdleTimerDisabled."""
    client.call_tool("setIdleTimerDisabled", {"disabled": True})
    result = client.text(client.call_tool("getIdleTimerDisabled"))
    assert "off" in result  # idle timer off → screen stays on

    client.call_tool("setIdleTimerDisabled", {"disabled": False})
    result = client.text(client.call_tool("getIdleTimerDisabled"))
    assert "on" in result  # idle timer on → screen may sleep


def test_get_paused_no_project(client):
    """getProjectPaused should return an error when no project is running."""
    client.stop_project()
    time.sleep(1)
    try:
        client.call_tool("getProjectPaused")
        pytest.fail("Expected MCPError")
    except MCPError:
        pass
