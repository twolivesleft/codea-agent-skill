"""Tests for file operations."""

import pytest
from codea.mcp_client import MCPError

LUA_CONTENT = "-- test\nfunction setup() end\nfunction draw() end\n"
LUA_UPDATED = "-- updated\nfunction setup() end\nfunction draw() background(0) end\n"


def _file_uri(project, filename):
    return f"{project['uri']}/{filename}"


def test_list_files_returns_files(client, project):
    files = client.list_files(project["uri"])
    assert isinstance(files, list)
    assert len(files) > 0  # new project has at least Main.lua from template


def test_write_and_read_file(client, project):
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, LUA_CONTENT)
    content = client.read_file(uri)
    assert content == LUA_CONTENT


def test_overwrite_file(client, project):
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, LUA_CONTENT)
    client.write_file(uri, LUA_UPDATED)
    content = client.read_file(uri)
    assert content == LUA_UPDATED


def test_write_new_file(client, project):
    uri = _file_uri(project, "Helper.lua")
    client.write_file(uri, LUA_CONTENT)
    files = client.list_files(project["uri"])
    filenames = [f.split("/")[-1] for f in files]
    assert "Helper.lua" in filenames


def test_delete_file(client, project):
    uri = _file_uri(project, "Helper.lua")
    client.write_file(uri, LUA_CONTENT)
    client.call_tool("deleteFile", {"path": uri})
    files = client.list_files(project["uri"])
    filenames = [f.split("/")[-1] for f in files]
    assert "Helper.lua" not in filenames


def test_rename_file(client, project):
    uri = _file_uri(project, "Helper.lua")
    client.write_file(uri, LUA_CONTENT)
    client.call_tool("renameFile", {"path": uri, "newName": "Renamed.lua"})
    files = client.list_files(project["uri"])
    filenames = [f.split("/")[-1] for f in files]
    assert "Helper.lua" not in filenames
    assert "Renamed.lua" in filenames


def test_copy_file(client, project):
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, LUA_CONTENT)
    client.call_tool("copyFile", {"path": uri, "newName": "MainCopy.lua"})
    files = client.list_files(project["uri"])
    filenames = [f.split("/")[-1] for f in files]
    assert "MainCopy.lua" in filenames
    copy_uri = _file_uri(project, "MainCopy.lua")
    assert client.read_file(copy_uri) == LUA_CONTENT


def test_find_in_files(client, project):
    uri = _file_uri(project, "Main.lua")
    client.write_file(uri, "function setup()\n  local x = 42\nend\n")
    results = client.find_in_files(project["uri"], "x = 42")
    assert len(results) > 0
