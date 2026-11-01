"""
Unit tests for Unreal Engine 5 MCP Stdio Bridge for Claude (scripts/stdio_bridge.py).
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from stdio_bridge import StdioMCPBridge


def test_stdio_bridge_initialize():
    bridge = StdioMCPBridge()
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "claude-desktop", "version": "1.0"},
        },
    }
    resp = bridge.handle_request(req)
    assert resp is not None
    assert resp["id"] == 1
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert "tools" in resp["result"]["capabilities"]


def test_stdio_bridge_ping():
    bridge = StdioMCPBridge()
    resp = bridge.handle_request({"jsonrpc": "2.0", "id": 42, "method": "ping"})
    assert resp == {"jsonrpc": "2.0", "id": 42, "result": {}}


def test_stdio_bridge_tools_list_includes_convenience_tools():
    bridge = StdioMCPBridge()
    with patch.object(bridge.client, "is_server_listening", return_value=False):
        resp = bridge.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert resp is not None
        tool_names = [t["name"] for t in resp["result"]["tools"]]
        assert "list_toolsets" in tool_names
        assert "describe_toolset" in tool_names
        assert "call_tool" in tool_names
        assert "ue5_get_camera" in tool_names
        assert "ue5_set_camera" in tool_names
        assert "ue5_capture_viewport" in tool_names
        assert "ue5_diagnostics" in tool_names
        assert "ue5_find_actors" in tool_names
        assert "ue5_execute_python" in tool_names


def test_stdio_bridge_tools_call_offline_error():
    bridge = StdioMCPBridge()
    with patch.object(bridge.client, "is_server_listening", return_value=False):
        resp = bridge.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "ue5_get_camera", "arguments": {}},
        })
        assert resp is not None
        assert resp["result"]["isError"] is True
        assert "not listening" in resp["result"]["content"][0]["text"]


def test_stdio_bridge_tools_call_camera_success():
    bridge = StdioMCPBridge()
    with patch.object(bridge.client, "is_server_listening", return_value=True), \
         patch.object(bridge.client, "get_camera_transform", return_value={"location": {"x": 10.0, "y": 20.0, "z": 30.0}}):
        resp = bridge.handle_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "ue5_get_camera", "arguments": {}},
        })
        assert resp is not None
        assert "isError" not in resp.get("result", {})
        content_text = resp["result"]["content"][0]["text"]
        data = json.loads(content_text)
        assert data["location"]["x"] == 10.0


def test_stdio_bridge_tools_call_set_camera():
    bridge = StdioMCPBridge()
    with patch.object(bridge.client, "is_server_listening", return_value=True), \
         patch.object(bridge.client, "set_camera_transform", return_value={"status": "ok"}):
        resp = bridge.handle_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "ue5_set_camera",
                "arguments": {"x": 100.0, "y": 200.0, "z": 300.0, "pitch": -10.0},
            },
        })
        assert resp is not None
        assert "status" in resp["result"]["content"][0]["text"]


def test_stdio_bridge_tools_call_capture_viewport(tmp_path: Path):
    bridge = StdioMCPBridge()
    test_img = tmp_path / "test.png"
    test_img.write_bytes(b"\x89PNGfake")

    with patch.object(bridge.client, "is_server_listening", return_value=True), \
         patch.object(bridge.client, "capture_viewport", return_value=test_img):
        resp = bridge.handle_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "ue5_capture_viewport", "arguments": {}},
        })
        assert resp is not None
        content = resp["result"]["content"][0]
        assert content["type"] == "image"
        assert content["mimeType"] == "image/png"
        assert base64.b64decode(content["data"]) == b"\x89PNGfake"
