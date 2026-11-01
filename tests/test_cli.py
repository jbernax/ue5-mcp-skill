"""
Unit tests for Unreal Engine 5 MCP CLI operator (scripts/mcp_cli.py).
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mcp_cli import build_parser, main


def test_cli_argument_parsing():
    parser = build_parser()

    # status
    args = parser.parse_args(["status"])
    assert args.command == "status"
    assert args.port == 7903

    # set-camera
    args = parser.parse_args(["set-camera", "--x", "100.5", "--y", "-200.0", "--z", "500", "--pitch", "-10"])
    assert args.command == "set-camera"
    assert args.x == 100.5
    assert args.y == -200.0
    assert args.z == 500.0
    assert args.pitch == -10.0

    # capture-viewport
    args = parser.parse_args(["capture-viewport", "--out", "/tmp/shot.png"])
    assert args.command == "capture-viewport"
    assert args.out == "/tmp/shot.png"

    # exec-python
    args = parser.parse_args(["exec-python", "--script", "print('hello')"])
    assert args.command == "exec-python"
    assert args.script == "print('hello')"

    # cvar
    args = parser.parse_args(["cvar", "get", "r.Nanite"])
    assert args.command == "cvar"
    assert args.cvar_action == "get"
    assert args.name == "r.Nanite"


def test_cli_status_command(capsys):
    with patch("ue5_mcp_client.UE5MCPClient.is_server_listening", return_value=True), \
         patch("ue5_mcp_client.UE5MCPClient.initialize_session", return_value="sess-abc"):
        ret = main(["status"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["listening"] is True
        assert data["status"] == "connected"
        assert data["mcp_session_id"] == "sess-abc"


def test_cli_server_not_listening_exits_1(capsys):
    with patch("ue5_mcp_client.UE5MCPClient.is_server_listening", return_value=False):
        ret = main(["diagnostics"])
        assert ret == 1
        captured = capsys.readouterr()
        assert "not listening" in captured.err


def test_launch_script_verification():
    script_path = REPO_ROOT / "scripts" / "launch_ue5_mcp.sh"
    assert script_path.exists()
    assert (script_path.stat().st_mode & 0o111) != 0

    res = subprocess.run(["bash", str(script_path), "--test"], capture_output=True, text=True, check=True)
    assert "Verification OK" in res.stdout
    assert "MCP Port: 7903" in res.stdout
