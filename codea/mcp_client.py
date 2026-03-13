import itertools
import json
import base64
from typing import Optional

import requests

PROTOCOL_VERSION = "2024-11-05"


class MCPError(Exception):
    pass


class MCPClient:
    def __init__(self, host: str, port: int, timeout: int = 30):
        self.url = f"http://{host}:{port}/mcp"
        self.timeout = timeout
        self._id = itertools.count(1)
        self._initialized = False

    def _next_id(self) -> int:
        return next(self._id)

    def _post(self, payload: dict) -> dict:
        response = requests.post(
            self.url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def _notify(self, method: str, params: dict | None = None):
        """Send a notification (no id, no response expected)."""
        self._post({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def initialize(self):
        result = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "codea", "version": "0.1.0"},
            },
        })
        self._notify("notifications/initialized")
        self._initialized = True
        return result

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        if not self._initialized:
            self.initialize()

        response = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })

        if "error" in response:
            raise MCPError(f"MCP error: {response['error']}")

        result = response.get("result", {})
        if result.get("isError"):
            content = result.get("content", [])
            text = content[0].get("text", "Unknown error") if content else "Unknown error"
            raise MCPError(f"Tool error: {text}")

        return result

    def text(self, result: dict) -> str:
        for item in result.get("content", []):
            if item.get("type") == "text":
                return item["text"]
        return ""

    def json_result(self, result: dict) -> object:
        return json.loads(self.text(result))

    def image_bytes(self, result: dict) -> Optional[bytes]:
        for item in result.get("content", []):
            if item.get("type") == "image":
                return base64.b64decode(item["data"])
        return None

    # --- Convenience wrappers ---

    def list_projects(self) -> list[str]:
        return self.json_result(self.call_tool("listProjects"))

    def list_files(self, project_uri: str) -> list[str]:
        return self.json_result(self.call_tool("listFiles", {"path": project_uri}))

    def list_dependencies(self, project_uri: str) -> list[str]:
        return self.json_result(self.call_tool("listDependencies", {"path": project_uri}))

    def read_file(self, file_uri: str) -> str:
        return self.text(self.call_tool("readFile", {"path": file_uri}))

    def write_file(self, file_uri: str, content: str):
        self.call_tool("writeFile", {"path": file_uri, "content": content})

    def run_project(self, project_uri: str) -> str:
        return self.text(self.call_tool("runProject", {"path": project_uri}))

    def stop_project(self) -> str:
        return self.text(self.call_tool("stopProject"))

    def execute_lua(self, code: str) -> str:
        return self.text(self.call_tool("executeLua", {"code": code}))

    def capture_screenshot(self) -> Optional[bytes]:
        return self.image_bytes(self.call_tool("captureScreenshot"))

    def find_in_files(self, project_uri: str, text: str,
                      case_sensitive: bool = False,
                      whole_word: bool = False,
                      is_regex: bool = False) -> dict:
        return self.json_result(self.call_tool("findInFiles", {
            "path": project_uri,
            "text": text,
            "caseSensitive": case_sensitive,
            "wholeWord": whole_word,
            "isRegex": is_regex,
        }))
