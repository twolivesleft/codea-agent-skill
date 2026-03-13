"""Tests for collection management."""

import pytest
import time
from codea.mcp_client import MCPError


def test_list_collections_includes_temp(client, temp_collection):
    result = client.call_tool("listCollections")
    collections = client.json_result(result)
    assert temp_collection in collections


def test_create_and_delete_collection(client):
    name = f"_test_col_{int(time.time())}"
    try:
        client.call_tool("createCollection", {"name": name})
        result = client.call_tool("listCollections")
        assert name in client.json_result(result)
    finally:
        client.call_tool("deleteCollection", {"name": name})

    result = client.call_tool("listCollections")
    assert name not in client.json_result(result)
