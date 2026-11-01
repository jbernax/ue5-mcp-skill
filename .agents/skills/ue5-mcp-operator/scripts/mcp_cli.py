#!/usr/bin/env python3
"""
Command-line Interface (CLI) Operator for Unreal Engine 5 Model Context Protocol (MCP).
Used by AI coding agents and developers to inspect toolsets, teleport viewport cameras,
capture screenshots, query and manipulate scene actors, and execute in-Editor Python scripts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure local scripts directory is importable
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ue5_mcp_client import DEFAULT_MCP_PORT, DEFAULT_MCP_URL, UE5MCPClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unreal Engine 5 Model Context Protocol (MCP) CLI Operator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_MCP_URL,
        help="MCP server Streamable HTTP URL",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_MCP_PORT,
        help="MCP server port number",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # Status
    sub.add_parser("status", help="Check if UE5 MCP server is listening and responding")

    # Meta tools
    sub.add_parser("list-toolsets", help="List all registered toolsets from Unreal Editor")

    p_desc = sub.add_parser("describe-toolset", help="Describe tools and schemas in a toolset")
    p_desc.add_argument("toolset_name", type=str, help="Full toolset name")

    p_call = sub.add_parser("call-tool", help="Call any UE5 tool with JSON arguments")
    p_call.add_argument("--tool", type=str, required=True, help="Tool name")
    p_call.add_argument("--toolset", type=str, default=None, help="Optional toolset name")
    p_call.add_argument("--args", type=str, default="{}", help="Tool arguments as JSON string")

    # Diagnostics
    sub.add_parser("diagnostics", help="Query active level and scene actor summary")

    # Viewport & Camera
    sub.add_parser("get-camera", help="Get current Editor viewport camera transform")

    p_cam = sub.add_parser("set-camera", help="Set Editor viewport camera transform")
    p_cam.add_argument("--x", type=float, required=True, help="X location (cm)")
    p_cam.add_argument("--y", type=float, required=True, help="Y location (cm)")
    p_cam.add_argument("--z", type=float, required=True, help="Z location (cm)")
    p_cam.add_argument("--pitch", type=float, default=0.0, help="Camera pitch in degrees")
    p_cam.add_argument("--yaw", type=float, default=0.0, help="Camera yaw in degrees")
    p_cam.add_argument("--roll", type=float, default=0.0, help="Camera roll in degrees")

    p_cap = sub.add_parser("capture-viewport", help="Capture screenshot of active Editor viewport")
    p_cap.add_argument("--out", type=str, required=True, help="Output PNG file path")
    p_cap.add_argument("--show-ui", action="store_true", help="Include Editor UI in capture")

    # Scene & Actors
    p_find = sub.add_parser("find-actors", help="Find actors in current level")
    p_find.add_argument("--name", type=str, default="", help="Actor name filter")
    p_find.add_argument("--tag", type=str, default="", help="Actor tag filter")

    # Python Execution
    p_py = sub.add_parser("exec-python", help="Execute Python script in Unreal Editor")
    group = p_py.add_mutually_exclusive_group(required=True)
    group.add_argument("--script", type=str, help="Python code string to execute")
    group.add_argument("--file", type=str, help="Path to Python file to execute")

    # Console Command
    p_cmd = sub.add_parser("console", help="Execute Editor console command")
    p_cmd.add_argument("--cmd", type=str, required=True, help="Console command string")

    # CVars
    p_cvar = sub.add_parser("cvar", help="Get or set a console variable")
    cvar_sub = p_cvar.add_subparsers(dest="cvar_action", required=True)
    p_cget = cvar_sub.add_parser("get", help="Get CVar value")
    p_cget.add_argument("name", type=str, help="CVar name")
    p_cset = cvar_sub.add_parser("set", help="Set CVar value")
    p_cset.add_argument("name", type=str, help="CVar name")
    p_cset.add_argument("value", type=str, help="New CVar value")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    client = UE5MCPClient(mcp_url=args.url, port=args.port, timeout_s=args.timeout)

    if args.command == "status":
        listening = client.is_server_listening()
        status_info = {
            "url": client.mcp_url,
            "port": client.port,
            "listening": listening,
        }
        if listening:
            try:
                session_id = client.initialize_session()
                status_info["mcp_session_id"] = session_id
                status_info["status"] = "connected"
            except Exception as exc:
                status_info["status"] = f"connection_error: {exc}"
        else:
            status_info["status"] = "port_closed"
        print(json.dumps(status_info, indent=2))
        return 0 if listening else 1

    # For commands other than status, check socket first
    if not client.is_server_listening():
        print(
            json.dumps({
                "error": f"Unreal Editor MCP server is not listening on {args.url}:{args.port}.",
                "hint": "Launch Unreal Editor with -ModelContextProtocolStartServer -ModelContextProtocolPort=7903",
            }),
            file=sys.stderr,
        )
        return 1

    try:
        if args.command == "list-toolsets":
            res = client.list_toolsets()
            print(json.dumps(res, indent=2))
        elif args.command == "describe-toolset":
            res = client.describe_toolset(args.toolset_name)
            print(json.dumps(res, indent=2))
        elif args.command == "call-tool":
            raw_args = json.loads(args.args)
            res = client.call_tool(args.tool, toolset_name=args.toolset, arguments=raw_args)
            print(json.dumps(res, indent=2))
        elif args.command == "diagnostics":
            level = client.get_current_level()
            actors = client.find_actors()
            print(
                json.dumps(
                    {
                        "current_level": level,
                        "total_actors": len(actors),
                        "sample_actors": actors[:10],
                    },
                    indent=2,
                )
            )
        elif args.command == "get-camera":
            res = client.get_camera_transform()
            print(json.dumps(res, indent=2))
        elif args.command == "set-camera":
            res = client.set_camera_transform(
                location=(args.x, args.y, args.z),
                rotation=(args.pitch, args.yaw, args.roll),
            )
            print(json.dumps(res, indent=2))
        elif args.command == "capture-viewport":
            saved = client.capture_viewport(args.out, b_show_ui=args.show_ui)
            if saved:
                print(json.dumps({"status": "success", "file": str(saved)}, indent=2))
            else:
                print(json.dumps({"status": "error", "message": "Failed to capture viewport screenshot"}, indent=2))
                return 1
        elif args.command == "find-actors":
            res = client.find_actors(name=args.name, tag=args.tag)
            print(json.dumps({"count": len(res), "actors": res}, indent=2))
        elif args.command == "exec-python":
            script_code = Path(args.file).read_text(encoding="utf-8") if args.file else args.script
            res = client.execute_python_script(script_code)
            print(json.dumps(res, indent=2))
        elif args.command == "console":
            res = client.execute_console_command(args.cmd)
            print(json.dumps(res, indent=2))
        elif args.command == "cvar":
            if args.cvar_action == "get":
                res = client.get_cvar(args.name)
                print(json.dumps(res, indent=2))
            elif args.cvar_action == "set":
                res = client.set_cvar(args.name, args.value)
                print(json.dumps(res, indent=2))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
