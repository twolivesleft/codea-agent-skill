"""Tests for status, runtime, doc, and autocomplete commands.

These tests use CliRunner for CLI-level validation and the MCP client for
device interaction where needed.
"""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from codea.cli import main
from codea.config import DEFAULT_PORT


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_shows_host_and_port(runner, client):
    """status should print Host and Port lines."""
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0, result.output
    assert "Host:" in result.output
    assert "Port:" in result.output


def test_status_shows_device_state(runner, client):
    """status should show a State: line (idle when nothing is running)."""
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0, result.output
    assert "State:" in result.output


def test_status_idle_when_nothing_running(runner, client):
    """status should show 'Idle' when no project is running."""
    # Make sure nothing is running
    try:
        client.stop_project()
    except Exception:
        pass

    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0, result.output
    assert "Idle" in result.output


def test_status_running_shows_project_name(runner, client, project):
    """status should show the running project name."""
    client.run_project(project["uri"])
    import time; time.sleep(2)
    try:
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0, result.output
        assert "Running" in result.output
        assert project["name"] in result.output
    finally:
        client.stop_project()


def test_status_shows_idle_timer(runner, client):
    """status should show the idle timer state."""
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0, result.output
    assert "Idle timer:" in result.output


def test_status_not_configured(runner, tmp_path):
    """status shows helpful message when not configured."""
    fake_config = tmp_path / "config.json"
    with patch("codea.cli.CONFIG_FILE", fake_config), \
         patch.dict("os.environ", {}, clear=True):
        import os
        env = {k: v for k, v in os.environ.items()
               if k not in ("CODEA_HOST", "CODEA_PORT")}
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "Not configured" in result.output


# ---------------------------------------------------------------------------
# runtime
# ---------------------------------------------------------------------------

def test_runtime_get_returns_valid_value(runner, project):
    """runtime get should return 'legacy' or 'modern'."""
    result = runner.invoke(main, ["runtime", project["name"]])
    assert result.exit_code == 0, result.output
    assert result.output.strip() in ("legacy", "modern")


def test_runtime_set_and_get_roundtrip(runner, project):
    """Setting and then getting runtime should return the new value."""
    result = runner.invoke(main, ["runtime", project["name"], "modern"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(main, ["runtime", project["name"]])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "modern"

    # Restore to legacy
    runner.invoke(main, ["runtime", project["name"], "legacy"])


def test_runtime_set_legacy(runner, project):
    """Setting runtime to legacy should succeed."""
    result = runner.invoke(main, ["runtime", project["name"], "legacy"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(main, ["runtime", project["name"]])
    assert result.output.strip() == "legacy"


def test_runtime_invalid_type_fails(runner, project):
    """Setting an invalid runtime type should fail with a non-zero exit code."""
    result = runner.invoke(main, ["runtime", project["name"], "carbide"])
    assert result.exit_code != 0
    assert "legacy" in result.output or "modern" in result.output


def test_runtime_new_project_defaults_to_legacy(runner, project):
    """A freshly created project should default to legacy runtime."""
    result = runner.invoke(main, ["runtime", project["name"]])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "legacy"


# ---------------------------------------------------------------------------
# doc
# ---------------------------------------------------------------------------

def test_doc_both_runtimes_shows_sections(runner):
    """doc for a function with both runtimes should show Modern and Legacy sections."""
    result = runner.invoke(main, ["doc", "background"])
    assert result.exit_code == 0, result.output
    assert "Modern" in result.output
    assert "Legacy" in result.output


def test_doc_modern_only(runner):
    """--modern flag should omit the Legacy section."""
    result = runner.invoke(main, ["doc", "background", "--modern"])
    assert result.exit_code == 0, result.output
    assert "Modern" not in result.output  # no section headers when filtering
    assert "Legacy" not in result.output
    assert "background" in result.output.lower()


def test_doc_legacy_only(runner):
    """--legacy flag should omit the Modern section."""
    result = runner.invoke(main, ["doc", "background", "--legacy"])
    assert result.exit_code == 0, result.output
    assert "Modern" not in result.output
    assert "Legacy" not in result.output
    assert "background" in result.output.lower()


def test_doc_unknown_function_fails(runner):
    """doc for an unknown function should exit with a non-zero code."""
    result = runner.invoke(main, ["doc", "zzz_does_not_exist_zzz"])
    assert result.exit_code != 0
    assert "No documentation" in result.output or "Error" in result.output


def test_doc_unknown_function_with_filter_fails(runner):
    """doc --modern for an unknown function should exit with a non-zero code."""
    result = runner.invoke(main, ["doc", "zzz_does_not_exist_zzz", "--modern"])
    assert result.exit_code != 0


def test_doc_shows_function_name(runner):
    """doc output should include the function name as a header."""
    result = runner.invoke(main, ["doc", "background"])
    assert result.exit_code == 0, result.output
    assert "background" in result.output


def test_doc_with_project_runtime(runner, project):
    """--project flag should auto-select docs for that project's runtime."""
    # Set project to legacy, then check that only legacy section appears
    runner.invoke(main, ["runtime", project["name"], "legacy"])
    result = runner.invoke(main, ["doc", "background", "--project", project["name"]])
    assert result.exit_code == 0, result.output
    # With a runtime filter from --project, no section headers appear
    assert "Modern" not in result.output
    assert "background" in result.output.lower()


# ---------------------------------------------------------------------------
# autocomplete
# ---------------------------------------------------------------------------

def test_autocomplete_returns_results(runner, project):
    """autocomplete should return completions for a known prefix."""
    result = runner.invoke(main, ["autocomplete", project["name"], "vec2"])
    assert result.exit_code == 0, result.output
    assert "(no completions)" not in result.output
    assert len(result.output.strip()) > 0


def test_autocomplete_asset_prefix(runner, project):
    """autocomplete with 'asset.' prefix should return asset-related completions."""
    result = runner.invoke(main, ["autocomplete", project["name"], "asset."])
    assert result.exit_code == 0, result.output
    # Should return something
    assert len(result.output.strip()) > 0


def test_autocomplete_no_results_message(runner, project):
    """autocomplete for a non-matching prefix should show '(no completions)'."""
    result = runner.invoke(main, ["autocomplete", project["name"], "zzz_no_such_prefix_zzz"])
    assert result.exit_code == 0, result.output
    assert "(no completions)" in result.output
