# CLAUDE.md — Unreal Engine 5 MCP Operator Guide for Claude

This document provides system instructions, operational runbooks, and command references for Anthropic's **Claude Code** and **Claude Desktop** when interacting with Unreal Engine 5 projects via the Model Context Protocol (MCP).

---

## 1. Overview & Setup

Unreal Engine 5 (versions 5.4 through 5.8+) exposes an in-Editor Model Context Protocol server over HTTP at `http://127.0.0.1:7903/mcp`.

### Claude Desktop Integration

Claude Desktop requires stdio transport. Use the provided Python bridge in your `claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "unreal-engine": {
      "command": "python3",
      "args": [
        "/absolute/path/to/ue5-mcp-skill/scripts/stdio_bridge.py"
      ],
      "env": {
        "UE_MCP_URL": "http://127.0.0.1:7903/mcp"
      }
    }
  }
}
```

### Available Tools for Claude

When connected via the stdio bridge, Claude receives both direct high-level tools and native Unreal meta-tools:

| Tool Name | Key Parameters | Description |
| :--- | :--- | :--- |
| `ue5_capture_viewport` | `output_path?`, `show_ui?` | Captures the active Editor viewport and returns image data directly to Claude. |
| `ue5_get_camera` | None | Returns active viewport camera location (cm) and rotation (deg). |
| `ue5_set_camera` | `x, y, z`, `pitch?`, `yaw?`, `roll?` | Teleports the Editor camera to exact 3D coordinates. |
| `ue5_diagnostics` | None | Returns active level name, actor counts, and sample actor list. |
| `ue5_find_actors` | `name?`, `tag?` | Searches actors by name substring or tag. |
| `ue5_execute_python` | `script` | Runs Python code inside Unreal with full access to the `unreal` module. |
| `ue5_console_command` | `command` | Executes an Editor console command (e.g., `stat fps`, `r.Nanite 1`). |
| `list_toolsets` | None | Lists all 21 registered Unreal Engine toolsets. |
| `describe_toolset` | `toolset_name` | Retrieves tool definitions and schemas for any toolset. |
| `call_tool` | `tool_name`, `toolset_name?`, `arguments?` | Deep access to any tool across all registered toolsets. |

---

## 2. Command-Line Runbooks (for Claude Code)

When operating via bash in Claude Code, use the CLI scripts:

### Health & Server Lifecycle

```bash
# Verify Editor MCP server is active
bash scripts/launch_ue5_mcp.sh --status

# Launch background daemon if not running
bash scripts/launch_ue5_mcp.sh --daemon

# Launch full desktop GUI Editor
bash scripts/launch_ue5_mcp.sh --gui
```

### Viewport Teleportation & Visual Inspection

```bash
# Check camera position
python scripts/mcp_cli.py get-camera

# Position camera (centimeters, degrees)
python scripts/mcp_cli.py set-camera --x 0 --y 0 --z 1500 --pitch -15 --yaw 45

# Capture screenshot for visual inspection
python scripts/mcp_cli.py capture-viewport --out /tmp/viewport.png
```

### Scene Inspection & Python Scripting

```bash
# Check level summary
python scripts/mcp_cli.py diagnostics

# Find actors
python scripts/mcp_cli.py find-actors --name "DirectionalLight"

# Execute in-Editor Python script
python scripts/mcp_cli.py exec-python --script "import unreal; print(unreal.EditorLevelLibrary.get_all_level_actors())"
```

---

## 3. Best Practices for Claude

1. **Verify Before Acting**: Always run `python scripts/mcp_cli.py status` or check `ue5_diagnostics` before attempting scene manipulations.
2. **Units & Coordinate System**: Unreal Engine uses **centimeters** for location and **degrees** for rotation. Positive Z is Up. Default Unreal coordinates are left-handed (X=Forward, Y=Right, Z=Up).
3. **Visual Verification**: After spawning actors or adjusting materials, call `ue5_capture_viewport` to verify visual results rather than assuming success.
4. **Error Recovery**: If the MCP port is closed, check `Saved/Logs/mcp_server.log` and verify the `ModelContextProtocol` plugin is enabled in `<Project>.uproject`.
