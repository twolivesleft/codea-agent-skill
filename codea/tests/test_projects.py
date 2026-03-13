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
    uri = next(w for w in text.split() if w.startswith("codea://"))

    try:
        uris = client.list_projects()
        assert uri in uris
    finally:
        client.call_tool("deleteProject", {"path": uri})


def test_delete_project_removes_from_list(client, temp_collection):
    name = f"test_del_{int(time.time() * 1000) % 1_000_000}"
    result = client.call_tool("createProject", {"name": name, "collection": temp_collection})
    text = client.text(result)
    uri = next(w for w in text.split() if w.startswith("codea://"))

    client.call_tool("deleteProject", {"path": uri})

    uris = client.list_projects()
    assert uri not in uris


def test_rename_project(client, project):
    new_name = project["name"] + "_renamed"
    client.call_tool("renameProject", {"path": project["uri"], "newName": new_name})

    uris = client.list_projects()
    logical_paths = [u.split("/Codea/")[-1] for u in uris]
    assert any(lp.endswith(new_name) for lp in logical_paths)

    # Rename back so fixture cleanup can find it by original URI (best-effort)
    try:
        renamed_uri = next(u for u in uris if u.endswith(new_name))
        client.call_tool("renameProject", {"path": renamed_uri, "newName": project["name"]})
    except (StopIteration, Exception):
        pass
