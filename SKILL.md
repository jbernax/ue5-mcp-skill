---
name: ue5-mcp-operator
description: >-
  Operate Unreal Engine 5 directly via the Model Context Protocol (MCP) server
  (default port 7903). Use when inspecting or launching the Unreal Editor MCP server,
  querying registered toolsets, inspecting or spawning actors, adjusting transforms,
  manipulating materials, executing in-Editor Python scripts, setting camera viewpoints,
  and capturing viewport screenshots.
---

# Unreal Engine 5 MCP Operator Guide

This skill provides procedures for interacting with live Unreal Engine 5.x Editor instances over the native `ModelContextProtocol` plugin on port `7903` (Streamable HTTP / JSON-RPC 2.0).

---

## 1. Server Lifecycle & Health Check

Always verify the Unreal Editor MCP server is listening before making tool calls:

```bash
bash scripts/launch_ue5_mcp.sh --status
```

### Launch Modes

- **Start Background Daemon (Headless / Vulkan)**:
  ```bash
  bash scripts/launch_ue5_mcp.sh --daemon
  ```
- **Start Desktop GUI Editor (`DISPLAY=:0`)**:
  ```bash
  bash scripts/launch_ue5_mcp.sh --gui
  ```
- **Stop Server Safely**:
  ```bash
  bash scripts/launch_ue5_mcp.sh --kill
  ```

---

## 2. Calling MCP Meta-Tools

The Unreal Engine MCP server registers three top-level meta-tools:

1. **`list_toolsets`**: Returns all registered toolsets in the active Editor.
2. **`describe_toolset`**: Takes `{"toolset_name": "<name>"}` and returns tool schemas.
3. **`call_tool`**: Takes `{"toolset_name": "<toolset>", "tool_name": "<tool>", "arguments": {...}}`.

See [toolsets_reference.md](./references/toolsets_reference.md) for the full catalog of available toolsets and methods.

---

## 3. Command-Line Operator (`mcp_cli.py`)

The companion CLI provides high-level commands for common agent workflows:

### Viewport Teleportation & Screenshot Capture

```bash
# Teleport camera to world coordinates (cm) and orientation (deg)
python scripts/mcp_cli.py set-camera --x 0.0 --y 0.0 --z 1500.0 --pitch -15.0 --yaw 0.0

# Capture high-resolution viewport screenshot
python scripts/mcp_cli.py capture-viewport --out /tmp/ue5_screenshot.png
```

### Scene Inspection & Actors

```bash
# Query active level and actor summary
python scripts/mcp_cli.py diagnostics

# Search scene actors by name
python scripts/mcp_cli.py find-actors --name "DirectionalLight"
```

### In-Editor Python Scripting

```bash
# Execute Python code directly inside Unreal Editor
python scripts/mcp_cli.py exec-python --script "import unreal; print(unreal.EditorLevelLibrary.get_all_level_actors())"
```

### Console Commands & CVars

```bash
# Run Editor console command
python scripts/mcp_cli.py console --cmd "stat fps"

# Read or modify console variables
python scripts/mcp_cli.py cvar get r.Nanite
python scripts/mcp_cli.py cvar set r.Nanite 1
```

---

## 4. Python Client Library Integration

For programmatic control in Python scripts or test harnesses:

```python
from scripts.ue5_mcp_client import UE5MCPClient

client = UE5MCPClient(mcp_url="http://127.0.0.1:7903/mcp")

# Check status
if client.is_server_listening():
    client.initialize_session()
    
    # Teleport camera and capture image
    client.set_camera_transform(location=(0.0, 0.0, 1200.0), rotation=(-10.0, 45.0, 0.0))
    screenshot_path = client.capture_viewport("/tmp/output.png")
    
    # Query actors
    actors = client.find_actors(name="StaticMeshActor")
```

---

## 5. Claude Desktop & Claude Code Integration

For Claude Desktop (stdio transport) and Claude Code:
- Use `scripts/stdio_bridge.py` in `claude_desktop_config.json` to bridge stdio to the running Editor.
- See [`CLAUDE.md`](./CLAUDE.md) for full operational runbooks and available tools (`ue5_capture_viewport`, `ue5_get_camera`, `ue5_set_camera`, `ue5_diagnostics`, etc.).

---

## 6. Validation Checklist

- Verify `bash scripts/launch_ue5_mcp.sh --status` reports `Port 7903 : LISTENING`.
- Verify `python scripts/mcp_cli.py status` connects and returns an active `mcp_session_id`.
- Verify captured viewport images are non-empty and valid PNG files.
