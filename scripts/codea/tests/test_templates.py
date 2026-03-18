"""Tests for template management and --template flag on codea new.

Requires a connected Codea device running Air Code.
"""

import time
import pytest
from click.testing import CliRunner

from codea.cli import main
from codea.mcp_client import MCPError


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def template_project(client, temp_collection):
    """A fresh project to use as a template source; cleaned up after the test."""
    name = f"tmplsrc_{int(time.time() * 1000) % 1_000_000}"
    result = client.call_tool("createProject", {"name": name, "collection": temp_collection})
    text = client.text(result)
    words = text.split()
    path = next(words[i + 1] for i, w in enumerate(words) if w == "Path:" and i + 1 < len(words))
    yield {"name": name, "uri": path, "collection": temp_collection}
    try:
        client.call_tool("deleteProject", {"path": path})
    except MCPError:
        pass


# ---------------------------------------------------------------------------
# templates ls
# ---------------------------------------------------------------------------

def test_templates_ls_returns_results(runner, client):
    """templates ls should return at least the built-in templates."""
    result = runner.invoke(main, ["templates", "ls"])
    assert result.exit_code == 0, result.output
    assert len(result.output.strip()) > 0


def test_templates_ls_includes_builtin(runner, client):
    """templates ls should include the built-in Default template."""
    result = runner.invoke(main, ["templates", "ls"])
    assert result.exit_code == 0, result.output
    assert "Default" in result.output


def test_templates_ls_labels_builtin(runner, client):
    """templates ls should label built-in templates as built-in."""
    result = runner.invoke(main, ["templates", "ls"])
    assert result.exit_code == 0, result.output
    assert "built-in" in result.output


# ---------------------------------------------------------------------------
# codea new --template
# ---------------------------------------------------------------------------

def test_new_with_builtin_template(runner, client, temp_collection):
    """Creating a project with a built-in template name should succeed."""
    name = f"tmpltest_{int(time.time() * 1000) % 1_000_000}"
    result = runner.invoke(main, ["new", f"{temp_collection}/{name}", "--template", "Default"])
    try:
        assert result.exit_code == 0, result.output
        assert "Created" in result.output
    finally:
        try:
            projects = client.list_projects()
            uri = next((p for p in projects if p.endswith(name)), None)
            if uri:
                client.call_tool("deleteProject", {"path": uri})
        except Exception:
            pass


def test_new_with_invalid_template_fails(runner, client, temp_collection):
    """Creating a project with a non-existent template should fail with an error."""
    name = f"tmpltest_{int(time.time() * 1000) % 1_000_000}"
    result = runner.invoke(main, ["new", f"{temp_collection}/{name}", "--template", "DoesNotExist_zzz"])
    assert result.exit_code != 0 or "Error" in result.output
    assert "DoesNotExist_zzz" in result.output or "not found" in result.output.lower()


def test_new_default_template_differs_from_modern(runner, client, temp_collection):
    """Default and Modern templates should produce different Main.lua content."""
    import os, shutil

    name_default = f"tmpl_def_{int(time.time() * 1000) % 1_000_000}"
    name_modern = f"tmpl_mod_{int(time.time() * 1000) % 1_000_000}"

    try:
        runner.invoke(main, ["new", f"{temp_collection}/{name_default}", "--template", "Default"])
        runner.invoke(main, ["new", f"{temp_collection}/{name_modern}", "--template", "Modern"])

        runner.invoke(main, ["pull", f"{temp_collection}/{name_default}"])
        runner.invoke(main, ["pull", f"{temp_collection}/{name_modern}"])

        with open(f"{name_default}/Main.lua") as f:
            default_content = f.read()
        with open(f"{name_modern}/Main.lua") as f:
            modern_content = f.read()

        assert default_content != modern_content
    finally:
        for name in (name_default, name_modern):
            try:
                projects = client.list_projects()
                uri = next((p for p in projects if p.endswith(name)), None)
                if uri:
                    client.call_tool("deleteProject", {"path": uri})
            except Exception:
                pass
            shutil.rmtree(name, ignore_errors=True)


# ---------------------------------------------------------------------------
# templates add / remove
# ---------------------------------------------------------------------------

def test_templates_add_appears_in_ls(runner, client, template_project):
    """Adding a project as a template should make it appear in templates ls."""
    template_name = f"tmpl_{int(time.time() * 1000) % 1_000_000}"
    try:
        result = runner.invoke(main, ["templates", "add", template_project["name"], "--name", template_name])
        assert result.exit_code == 0, result.output

        result = runner.invoke(main, ["templates", "ls"])
        assert result.exit_code == 0, result.output
        assert template_name in result.output
    finally:
        try:
            client.call_tool("removeTemplate", {"name": template_name})
        except MCPError:
            pass


def test_templates_add_labeled_as_custom(runner, client, template_project):
    """A newly added template should be labeled as custom in templates ls."""
    template_name = f"tmpl_{int(time.time() * 1000) % 1_000_000}"
    try:
        runner.invoke(main, ["templates", "add", template_project["name"], "--name", template_name])

        result = runner.invoke(main, ["templates", "ls"])
        assert result.exit_code == 0, result.output
        assert f"{template_name} (custom)" in result.output
    finally:
        try:
            client.call_tool("removeTemplate", {"name": template_name})
        except MCPError:
            pass


def test_templates_remove(runner, client, template_project):
    """Removing a custom template should remove it from templates ls."""
    template_name = f"tmpl_{int(time.time() * 1000) % 1_000_000}"
    runner.invoke(main, ["templates", "add", template_project["name"], "--name", template_name])

    result = runner.invoke(main, ["templates", "remove", template_name], input="y\n")
    assert result.exit_code == 0, result.output

    result = runner.invoke(main, ["templates", "ls"])
    assert template_name not in result.output


def test_templates_new_project_uses_custom_template(runner, client, temp_collection, template_project):
    """A project created from a custom template should use that template's Main.lua."""
    import shutil

    # Write a distinctive Main.lua to the source project and push it
    marker = f"-- custom_template_marker_{int(time.time())}"
    result = runner.invoke(main, ["pull", template_project["name"]])
    assert result.exit_code == 0, result.output

    src_dir = template_project["name"]
    with open(f"{src_dir}/Main.lua", "w") as f:
        f.write(f"{marker}\nfunction setup() end\nfunction draw() end\n")
    runner.invoke(main, ["push", template_project["name"]])

    template_name = f"tmpl_{int(time.time() * 1000) % 1_000_000}"
    new_project = f"tmpl_new_{int(time.time() * 1000) % 1_000_000}"

    try:
        runner.invoke(main, ["templates", "add", template_project["name"], "--name", template_name])

        result = runner.invoke(main, ["new", f"{temp_collection}/{new_project}", "--template", template_name])
        assert result.exit_code == 0, result.output

        runner.invoke(main, ["pull", f"{temp_collection}/{new_project}"])

        with open(f"{new_project}/Main.lua") as f:
            content = f.read()

        assert marker in content
    finally:
        try:
            projects = client.list_projects()
            uri = next((p for p in projects if p.endswith(new_project)), None)
            if uri:
                client.call_tool("deleteProject", {"path": uri})
        except Exception:
            pass
        try:
            client.call_tool("removeTemplate", {"name": template_name})
        except MCPError:
            pass
        shutil.rmtree(src_dir, ignore_errors=True)
        shutil.rmtree(new_project, ignore_errors=True)
