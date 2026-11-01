#!/usr/bin/env python3
"""
Unreal Engine 5 MCP Stdio-to-HTTP Bridge for Claude Desktop and Claude Code.

Enables Claude Desktop (which communicates over standard input/output via the Model
Context Protocol stdio transport) to interact seamlessly with Unreal Engine 5's
Streamable HTTP MCP server on port 7903.
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
from pathlib import Path
import sys
from typing import Any

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ue5_mcp_client import DEFAULT_MCP_PORT, DEFAULT_MCP_URL, UE5MCPClient


logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[UE5-MCP-Bridge] %(levelname)s: %(message)s",
)
logger = logging.getLogger("ue5_mcp_bridge")


# Direct convenience tools exposed alongside native meta-tools to optimize Claude tool-calling
CONVENIENCE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "ue5_get_camera",
        "description": "Gets current Editor viewport camera location (cm), rotation (pitch, yaw, roll in deg), and scale.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "ue5_set_camera",
        "description": "Sets the Unreal Editor active viewport camera location and rotation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate in centimeters"},
                "y": {"type": "number", "description": "Y coordinate in centimeters"},
                "z": {"type": "number", "description": "Z coordinate in centimeters"},
                "pitch": {"type": "number", "description": "Camera pitch in degrees (-90 looking down, 0 level)", "default": 0.0},
                "yaw": {"type": "number", "description": "Camera yaw in degrees", "default": 0.0},
                "roll": {"type": "number", "description": "Camera roll in degrees", "default": 0.0},
            },
            "required": ["x", "y", "z"],
        },
    },
    {
        "name": "ue5_capture_viewport",
        "description": "Captures a screenshot of the active Unreal Editor viewport and returns the image data or saves to file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "description": "Optional file path to save PNG image. If omitted, image is returned directly as base64."},
                "show_ui": {"type": "boolean", "description": "Whether to include Editor UI overlays in capture.", "default": False},
            },
        },
    },
    {
        "name": "ue5_diagnostics",
        "description": "Queries the active level name, package path, total actor count, and sample actors.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "ue5_find_actors",
        "description": "Searches scene actors in the current level by name substring or tag.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Actor name filter substring", "default": ""},
                "tag": {"type": "string", "description": "Actor tag filter", "default": ""},
            },
        },
    },
    {
        "name": "ue5_execute_python",
        "description": "Executes arbitrary Python code inside the live Unreal Editor process with full access to the 'unreal' API module.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "Python script code to execute"},
            },
            "required": ["script"],
        },
    },
    {
        "name": "ue5_console_command",
        "description": "Executes an Unreal Editor console command (e.g. 'stat fps', 'r.Nanite 1').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Console command string"},
            },
            "required": ["command"],
        },
    },
]


class StdioMCPBridge:
    """
    Stdio-to-HTTP JSON-RPC 2.0 bridge between Claude Desktop and Unreal Engine 5 MCP server.
    """

    def __init__(self, mcp_url: str = DEFAULT_MCP_URL, port: int = DEFAULT_MCP_PORT) -> None:
        self.client = UE5MCPClient(mcp_url=mcp_url, port=port)
        self.protocol_version = "2024-11-05"

    def handle_request(self, req: dict[str, Any]) -> dict[str, Any] | None:
        method = req.get("method")
        msg_id = req.get("id")
        params = req.get("params", {})

        if method == "initialize":
            self.protocol_version = params.get("protocolVersion", "2024-11-05")
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": self.protocol_version,
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                    "serverInfo": {
                        "name": "unreal-engine-mcp-claude-bridge",
                        "version": "1.0.0",
                    },
                },
            }

        if method == "notifications/initialized":
            logger.info("Claude initialized MCP session.")
            return None

        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        if method == "tools/list":
            return self._handle_tools_list(msg_id)

        if method == "tools/call":
            return self._handle_tools_call(msg_id, params)

        # Fallback for unrecognized RPC method
        if msg_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found",
                },
            }
        return None

    def _handle_tools_list(self, msg_id: Any) -> dict[str, Any]:
        tools: list[dict[str, Any]] = []

        # 1. Query native UE5 meta-tools if UE5 is running
        if self.client.is_server_listening():
            try:
                rpc_resp = self.client._send_rpc("tools/list", {})
                ue_tools = rpc_resp.get("result", {}).get("tools", [])
                if isinstance(ue_tools, list):
                    tools.extend(ue_tools)
            except Exception as exc:
                logger.warning("Could not fetch remote tools/list: %s", exc)

        # Fallback meta-tools schemas if UE5 not yet ready
        if not tools:
            tools.extend([
                {
                    "name": "list_toolsets",
                    "description": "List all available toolsets in Unreal Engine Editor with names and descriptions.",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "describe_toolset",
                    "description": "Get detailed tool names and input schemas for an Unreal Engine toolset.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "toolset_name": {"type": "string", "description": "Full name of the toolset"},
                        },
                        "required": ["toolset_name"],
                    },
                },
                {
                    "name": "call_tool",
                    "description": "Call an Unreal Engine tool by name and arguments.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "tool_name": {"type": "string", "description": "Name of tool"},
                            "toolset_name": {"type": "string", "description": "Optional toolset name"},
                            "arguments": {"type": "object", "description": "Tool arguments object"},
                        },
                        "required": ["tool_name"],
                    },
                },
            ])

        # 2. Add convenience tools
        tool_names = {t["name"] for t in tools}
        for c_tool in CONVENIENCE_TOOLS:
            if c_tool["name"] not in tool_names:
                tools.append(c_tool)

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": tools},
        }

    def _handle_tools_call(self, msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name", "")
        args = params.get("arguments", {})

        if not self.client.is_server_listening():
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: Unreal Editor MCP server is not listening on port {self.client.port}. Ensure Unreal Editor is running with -ModelContextProtocolStartServer -ModelContextProtocolPort={self.client.port}.",
                        }
                    ],
                    "isError": True,
                },
            }

        try:
            # Convenience tools handling
            if name == "ue5_get_camera":
                xform = self.client.get_camera_transform()
                return self._wrap_text_result(msg_id, json.dumps(xform, indent=2))

            if name == "ue5_set_camera":
                res = self.client.set_camera_transform(
                    location=(args["x"], args["y"], args["z"]),
                    rotation=(args.get("pitch", 0.0), args.get("yaw", 0.0), args.get("roll", 0.0)),
                )
                return self._wrap_text_result(msg_id, json.dumps(res, indent=2))

            if name == "ue5_capture_viewport":
                out_path = args.get("output_path")
                if out_path:
                    saved = self.client.capture_viewport(out_path, b_show_ui=args.get("show_ui", False))
                    if saved:
                        return self._wrap_text_result(msg_id, f"Screenshot successfully saved to: {saved}")
                    return self._wrap_error_result(msg_id, "Failed to capture viewport screenshot")
                
                # In-memory capture returned to Claude as base64 image
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                saved = self.client.capture_viewport(tmp_path, b_show_ui=args.get("show_ui", False))
                if saved and saved.exists():
                    img_bytes = saved.read_bytes()
                    tmp_path.unlink(missing_ok=True)
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [
                                {
                                    "type": "image",
                                    "data": base64.b64encode(img_bytes).decode("ascii"),
                                    "mimeType": "image/png",
                                }
                            ]
                        },
                    }
                return self._wrap_error_result(msg_id, "Failed to capture viewport image")

            if name == "ue5_diagnostics":
                level = self.client.get_current_level()
                actors = self.client.find_actors()
                diag = {
                    "current_level": level,
                    "total_actors": len(actors),
                    "sample_actors": actors[:10],
                }
                return self._wrap_text_result(msg_id, json.dumps(diag, indent=2))

            if name == "ue5_find_actors":
                actors = self.client.find_actors(name=args.get("name", ""), tag=args.get("tag", ""))
                return self._wrap_text_result(msg_id, json.dumps({"count": len(actors), "actors": actors}, indent=2))

            if name == "ue5_execute_python":
                out = self.client.execute_python_script(args["script"])
                return self._wrap_text_result(msg_id, json.dumps(out, indent=2) if isinstance(out, (dict, list)) else str(out))

            if name == "ue5_console_command":
                out = self.client.execute_console_command(args["command"])
                return self._wrap_text_result(msg_id, json.dumps(out, indent=2) if isinstance(out, (dict, list)) else str(out))

            # Native UE5 meta-tools forwarding
            raw_res = self.client.call_meta_tool(name, args)
            unwrapped = self.client._unwrap_tool_result(raw_res)

            if isinstance(unwrapped, dict) and "images_base64" in unwrapped and unwrapped["images_base64"]:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "image",
                                "data": unwrapped["images_base64"][0],
                                "mimeType": "image/png",
                            }
                        ]
                    },
                }

            text_output = json.dumps(unwrapped, indent=2) if isinstance(unwrapped, (dict, list)) else str(unwrapped)
            return self._wrap_text_result(msg_id, text_output)

        except Exception as exc:
            logger.exception("Error executing tool %s: %s", name, exc)
            return self._wrap_error_result(msg_id, f"Execution error in {name}: {exc}")

    @staticmethod
    def _wrap_text_result(msg_id: Any, text: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": text}],
            },
        }

    @staticmethod
    def _wrap_error_result(msg_id: Any, error_message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": error_message}],
                "isError": True,
            },
        }

    def run_stdio(self) -> None:
        """Runs the main stdio event loop processing line-delimited JSON-RPC from sys.stdin."""
        logger.info("Starting UE5 MCP Stdio Bridge for Claude on stdin/stdout...")
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                req = json.loads(line_str)
                resp = self.handle_request(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except Exception as exc:
                logger.error("Error processing line: %s", exc)
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Unreal Engine 5 MCP Stdio Bridge for Claude Desktop")
    parser.add_argument("--url", type=str, default=DEFAULT_MCP_URL, help="UE5 MCP server URL")
    parser.add_argument("--port", type=int, default=DEFAULT_MCP_PORT, help="UE5 MCP server port")
    args = parser.parse_args()

    bridge = StdioMCPBridge(mcp_url=args.url, port=args.port)
    bridge.run_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
