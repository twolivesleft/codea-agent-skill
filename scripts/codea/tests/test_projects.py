"""Tests for project management."""

import pytest
import time
from codea.mcp_client import MCPError


def test_create_project_appears_in_list(client, project):
    uris = client.list_projects()
    assert project["uri"] in uris


def test_create_project_in_specific_collection(client, temp_collection):
    name = f"test_col_{int(time.time() * 1000) % 1_000_000}"
    result = client.call_tool("createProject", {"name": name, "collection": temp_collection})
    text = client.text(result)
    assert name in text
    words = text.split()
    path = next(words[i + 1] for i, w in enumerate(words) if w == "Path:" and i + 1 < len(words))

    try:
        paths = client.list_projects()
        assert path in paths
    finally:
        client.call_tool("deleteProject", {"path": path})


def test_delete_project_removes_from_list(client, temp_collection):
    name = f"test_del_{int(time.time() * 1000) % 1_000_000}"
    result = client.call_tool("createProject", {"name": name, "collection": temp_collection})
    text = client.text(result)
    words = text.split()
    path = next(words[i + 1] for i, w in enumerate(words) if w == "Path:" and i + 1 < len(words))

    client.call_tool("deleteProject", {"path": path})

    paths = client.list_projects()
    assert path not in paths


def test_rename_project(client, project):
    new_name = project["name"] + "_renamed"
    client.call_tool("renameProject", {"path": project["uri"], "newName": new_name})

    paths = client.list_projects()
    assert any(p.endswith(new_name) for p in paths)

    # Rename back so fixture cleanup can find it by original path (best-effort)
    try:
        renamed_path = next(p for p in paths if p.endswith(new_name))
        client.call_tool("renameProject", {"path": renamed_path, "newName": project["name"]})
    except (StopIteration, Exception):
        pass


def test_move_project_to_different_collection(client, project, temp_collection):
    """Moving a project should make it appear in the destination collection."""
    import time as _time
    dest = f"_test_dest_{int(_time.time())}"
    client.call_tool("createCollection", {"name": dest})
    try:
        result = client.call_tool("moveProject", {"path": project["uri"], "collection": dest})
        text = client.text(result)
        assert "Moved" in text or dest in text

        _time.sleep(2)  # allow directory monitoring to update
        paths = client.list_projects()
        assert any(p.startswith(dest + "/") and p.endswith(project["name"]) for p in paths)
        assert not any(p == project["uri"] for p in paths)

        # Move back so fixture cleanup works
        moved_path = next(p for p in paths if p.endswith(project["name"]) and p.startswith(dest + "/"))
        client.call_tool("moveProject", {"path": moved_path, "collection": temp_collection})
    finally:
        try:
            client.call_tool("deleteCollection", {"name": dest})
        except MCPError:
            pass


def test_move_project_fails_for_nonexistent_collection(client, project):
    """Moving to a non-existent collection should return an error."""
    with pytest.raises(MCPError, match="not found"):
        client.call_tool("moveProject", {"path": project["uri"], "collection": "_no_such_collection_zzz"})


def test_move_project_same_collection_is_noop(client, project):
    """Moving to the same collection should succeed gracefully."""
    result = client.call_tool("moveProject", {"path": project["uri"], "collection": project["collection"]})
    assert result is not None  # no exception; project still accessible
    paths = client.list_projects()
    assert any(p.endswith(project["name"]) for p in paths)
