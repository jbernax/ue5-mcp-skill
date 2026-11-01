"""
Offline unit tests for Unreal Engine 5 MCP Client (scripts/ue5_mcp_client.py).
Mocks HTTP and socket interactions to verify protocol conformance, JSON-RPC handling,
base64 screenshot decoding, and error recovery.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

# Add scripts directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ue5_mcp_client import CoordinateAnchor, UE5MCPClient


class MockHTTPResponse:
    def __init__(self, body_dict: dict, headers: dict | None = None, status: int = 200) -> None:
        self.body_bytes = json.dumps(body_dict).encode("utf-8")
        self.headers = headers or {}
        self.status = status

    def read(self) -> bytes:
        return self.body_bytes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_coordinate_anchor_conversion():
    anchor = CoordinateAnchor(origin_x=100.0, origin_y=200.0, origin_z=50.0, scale_to_cm=100.0, invert_y=True)
    x_cm, y_cm, z_cm = anchor.to_ue5_cm(105.0, 210.0, 60.0)
    assert x_cm == 500.0
    assert y_cm == -1000.0  # Inverted Y for UE5 left-handed coords
    assert z_cm == 1000.0


def test_client_initialization():
    client = UE5MCPClient(mcp_url="http://127.0.0.1:7903/mcp", port=7903, timeout_s=15.0)
    assert client.mcp_url == "http://127.0.0.1:7903/mcp"
    assert client.port == 7903
    assert client.timeout_s == 15.0


def test_socket_probe_listening():
    client = UE5MCPClient()
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        mock_sock.connect_ex.return_value = 0
        assert client.is_server_listening() is True

        mock_sock.connect_ex.return_value = 111  # Connection refused
        assert client.is_server_listening() is False


def test_initialize_session_negotiation():
    client = UE5MCPClient()
    mock_resp = MockHTTPResponse(
        {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-11-25"}},
        headers={"Mcp-Session-Id": "test-session-uuid-1234"},
    )

    with patch("urllib.request.urlopen", return_value=mock_resp):
        session_id = client.initialize_session()
        assert session_id == "test-session-uuid-1234"
        assert client._session_id == "test-session-uuid-1234"


def test_list_toolsets():
    client = UE5MCPClient()
    client._session_id = "cached-session"

    mock_resp = MockHTTPResponse({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"toolsets": ["EditorAppToolset", "SceneTools"]}),
                }
            ]
        },
    })

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = client.list_toolsets()
        assert "toolsets" in res
        assert "EditorAppToolset" in res["toolsets"]


def test_set_and_get_camera_transform():
    client = UE5MCPClient()
    client._session_id = "cached-session"

    # Mock SetCameraTransform response
    mock_set_resp = MockHTTPResponse({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": '{"returnValue": true}'}]},
    })

    with patch("urllib.request.urlopen", return_value=mock_set_resp):
        res = client.set_camera_transform(
            location=(100.0, 200.0, 300.0),
            rotation=(-15.0, 90.0, 0.0),
        )
        assert res["location"] == {"x": 100.0, "y": 200.0, "z": 300.0}
        assert res["rotation"] == {"pitch": -15.0, "yaw": 90.0, "roll": 0.0}


def test_capture_viewport_base64_decode(tmp_path: Path):
    client = UE5MCPClient()
    client._session_id = "cached-session"

    fake_png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtest"
    fake_b64 = base64.b64encode(fake_png_data).decode("ascii")

    mock_resp = MockHTTPResponse({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [
                {
                    "type": "image",
                    "data": fake_b64,
                    "mimeType": "image/png",
                }
            ]
        },
    })

    out_file = tmp_path / "test_screen.png"
    with patch("urllib.request.urlopen", return_value=mock_resp):
        saved = client.capture_viewport(out_file)
        assert saved is not None
        assert saved.exists()
        assert saved.read_bytes() == fake_png_data


def test_scene_actors_and_python_exec():
    client = UE5MCPClient()
    client._session_id = "cached-session"

    mock_actors = MockHTTPResponse({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(["DirectionalLight_0", "SkyLight_0"]),
                }
            ]
        },
    })

    with patch("urllib.request.urlopen", return_value=mock_actors):
        actors = client.find_actors(name="Light")
        assert len(actors) == 2
        assert "DirectionalLight_0" in actors

    mock_py = MockHTTPResponse({
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"output": "42"}),
                }
            ]
        },
    })

    with patch("urllib.request.urlopen", return_value=mock_py):
        res = client.execute_python_script("print(42)")
        assert res == {"output": "42"}
