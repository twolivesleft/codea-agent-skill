"""Tests for status, runtime, doc, search-doc, and autocomplete commands.

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


def test_doc_see_also_for_namespaced_function(runner):
    """doc for a namespaced function should show a See also: section with siblings."""
    result = runner.invoke(main, ["doc", "storage.has"])
    assert result.exit_code == 0, result.output
    assert "See also:" in result.output
    # Should suggest other storage.* functions
    assert "storage" in result.output


def test_doc_see_also_for_namespace_root(runner):
    """doc for a namespace root (e.g. 'storage') should show See also: with members."""
    result = runner.invoke(main, ["doc", "storage"])
    assert result.exit_code == 0, result.output
    assert "See also:" in result.output


def test_doc_no_see_also_for_isolated_function(runner):
    """doc for a function with no siblings should not crash (See also may be absent)."""
    result = runner.invoke(main, ["doc", "background"])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# search-doc
# ---------------------------------------------------------------------------

def test_search_doc_returns_results(runner):
    """search-doc should return results for a known keyword."""
    result = runner.invoke(main, ["search-doc", "storage"])
    assert result.exit_code == 0, result.output
    assert len(result.output.strip()) > 0
    assert "storage" in result.output.lower()


def test_search_doc_shows_runtime_tag(runner):
    """search-doc results should include [modern], [legacy], or [both] tags."""
    result = runner.invoke(main, ["search-doc", "background"])
    assert result.exit_code == 0, result.output
    assert "[modern]" in result.output or "[legacy]" in result.output or "[both]" in result.output


def test_search_doc_no_results_message(runner):
    """search-doc with no matches should print a helpful message."""
    result = runner.invoke(main, ["search-doc", "zzz_no_such_thing_xyz"])
    assert result.exit_code == 0, result.output
    assert "No documentation" in result.output


def test_search_doc_matches_helptext(runner):
    """search-doc should match against help text, not just function names."""
    # "fill the screen" is the helpText for background
    result = runner.invoke(main, ["search-doc", "fill the screen"])
    assert result.exit_code == 0, result.output
    assert "background" in result.output.lower()


def test_search_doc_modern_filter(runner):
    """--modern flag should exclude legacy-only results."""
    result = runner.invoke(main, ["search-doc", "storage", "--modern"])
    assert result.exit_code == 0, result.output
    assert "[legacy]" not in result.output
    assert "storage" in result.output.lower()


def test_search_doc_legacy_filter(runner):
    """--legacy flag should exclude modern-only results."""
    result = runner.invoke(main, ["search-doc", "background", "--legacy"])
    assert result.exit_code == 0, result.output
    assert "[modern]" not in result.output
    assert "background" in result.output.lower()


def test_search_doc_filter_no_results_message(runner):
    """Filtered search with no matches should include the runtime in the message."""
    result = runner.invoke(main, ["search-doc", "zzz_no_such_thing_xyz", "--modern"])
    assert result.exit_code == 0, result.output
    assert "modern" in result.output.lower()


def test_search_doc_project_filter(runner, project):
    """--project flag should auto-select runtime and filter results."""
    runner.invoke(main, ["runtime", project["name"], "legacy"])
    result = runner.invoke(main, ["search-doc", "background", "--project", project["name"]])
    assert result.exit_code == 0, result.output
    assert "[modern]" not in result.output
    assert "background" in result.output.lower()


# ---------------------------------------------------------------------------
# autocomplete
# ---------------------------------------------------------------------------

def test_autocomplete_returns_results(runner, project):
    """autocomplete should return completions for a known prefix."""
    # sprite( triggers asset completions — reliable across both runtimes
    result = runner.invoke(main, ["autocomplete", project["name"], "sprite("])
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
