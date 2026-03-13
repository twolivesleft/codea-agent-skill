"""Tests for dependency management."""

import pytest
from codea.mcp_client import MCPError


def test_list_dependencies_empty(client, project):
    deps = client.list_dependencies(project["uri"])
    assert isinstance(deps, list)


def test_list_available_dependencies(client, project):
    result = client.call_tool("listAvailableDependencies", {"path": project["uri"]})
    available = client.json_result(result)
    assert isinstance(available, list)


def test_add_and_remove_dependency(client, project):
    available = client.json_result(client.call_tool("listAvailableDependencies", {"path": project["uri"]}))
    if not available:
        pytest.skip("No dependencies available on this device")

    dep_name = available[0]

    client.call_tool("addDependency", {"path": project["uri"], "dependency": dep_name})
    deps = client.list_dependencies(project["uri"])
    assert dep_name in deps

    client.call_tool("removeDependency", {"path": project["uri"], "dependency": dep_name})
    deps = client.list_dependencies(project["uri"])
    assert dep_name not in deps


def test_add_dependency_twice_is_idempotent(client, project):
    available = client.json_result(client.call_tool("listAvailableDependencies", {"path": project["uri"]}))
    if not available:
        pytest.skip("No dependencies available on this device")

    dep_name = available[0]

    client.call_tool("addDependency", {"path": project["uri"], "dependency": dep_name})
    client.call_tool("addDependency", {"path": project["uri"], "dependency": dep_name})
    deps = client.list_dependencies(project["uri"])
    assert deps.count(dep_name) == 1

    client.call_tool("removeDependency", {"path": project["uri"], "dependency": dep_name})
