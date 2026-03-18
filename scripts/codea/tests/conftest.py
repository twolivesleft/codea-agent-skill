"""
Shared fixtures for Codea integration tests.

Requires a connected Codea device running Air Code. Configure via:
  codea configure --host <ip>
or:
  export CODEA_HOST=<ip>

All tests run inside a temporary collection that is always cleaned up,
even on failure.
"""

import time
import pytest
import requests

from codea.config import load_config, DEFAULT_PORT
from codea.mcp_client import MCPClient, MCPError


def pytest_addoption(parser):
    parser.addoption("--profile", default="default", help="Codea device profile to use.")


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires a connected Codea device")


# ---------------------------------------------------------------------------
# Session-scoped: one client, one temp collection for the entire test run
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def profile(request):
    return request.config.getoption("--profile")


@pytest.fixture(scope="session")
def client(profile):
    """MCPClient connected to the configured device. Skips if unreachable."""
    cfg = load_config(profile)
    host = cfg.get("host")
    port = cfg.get("port", DEFAULT_PORT)

    if not host:
        pytest.skip("No Codea device configured. Run 'codea configure' first.")

    c = MCPClient(host, port, timeout=10)
    try:
        c.initialize()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pytest.skip(f"Codea device at {host}:{port} is not reachable.")

    return c


@pytest.fixture(scope="session")
def temp_collection(client):
    """Create a temporary collection for the test session; always delete it at the end."""
    name = f"_test_{int(time.time())}"
    client.call_tool("createCollection", {"name": name})
    yield name
    # Cleanup — runs even if tests fail
    try:
        client.call_tool("deleteCollection", {"name": name})
    except MCPError:
        pass  # best-effort


# ---------------------------------------------------------------------------
# Function-scoped: a fresh project per test, cleaned up after each test
# ---------------------------------------------------------------------------

@pytest.fixture
def project(client, temp_collection):
    """Create a fresh project in the temp collection; delete it after the test."""
    name = f"test_{int(time.time() * 1000) % 1_000_000}"
    result = client.call_tool("createProject", {"name": name, "collection": temp_collection})
    path = _extract_path(client.text(result))

    yield {"name": name, "uri": path, "collection": temp_collection}

    try:
        client.call_tool("deleteProject", {"path": path})
    except MCPError:
        pass  # best-effort


def _extract_path(text: str) -> str:
    """Pull the project path out of a createProject response string.

    Handles 'Path: Collection/Project' format.
    """
    words = text.split()
    for i, word in enumerate(words):
        if word == "Path:" and i + 1 < len(words):
            return words[i + 1]
    raise ValueError(f"No path found in: {text!r}")
