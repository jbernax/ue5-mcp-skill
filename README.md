# Unreal Engine 5 Model Context Protocol (MCP) Operator

A reusable Model Context Protocol (MCP) skill, client library, and command-line operator for **Unreal Engine 5 (5.4 / 5.5 / 5.6 / 5.7 / 5.8+)**.

Enables AI coding assistants (such as Antigravity, Claude Desktop, Cursor) and automated CI/CD pipelines to interact with running Unreal Editor instances over Streamable HTTP and JSON-RPC 2.0 (default port `7903`).

---

## Capabilities

- **Server Lifecycle Management**: Headless daemon and GUI launcher with automated health checks and memory watchdogs.
- **Viewport Teleportation**: Precise coordinate-based camera positioning with pitch, yaw, and roll controls.
- **Viewport Screenshot Capture**: Base64 and filesystem image extraction directly from the active Editor viewport.
- **Scene & Actor Manipulation**: Query, spawn, inspect, and transform actors and components.
- **Material Parameter Adjustments**: Real-time modification of scalar, vector, and texture parameters on Material Instance Constant assets.
- **In-Editor Python Execution**: Execute arbitrary Python scripts inside the live Unreal Editor environment.
- **Console & CVars**: Read, query, and modify Editor console variables and execute console commands.
- **Zero Third-Party Runtime Dependencies**: The client and CLI are implemented using pure Python standard library modules (`urllib`, `json`, `socket`, `base64`, `dataclasses`, `pathlib`).

---

## Architecture

```
+-------------------------------------------------------------+
| AI Agent / Developer Script / CLI (mcp_cli.py)              |
+-------------------------------------------------------------+
                              |
                     JSON-RPC 2.0 / HTTP
                    (Port 7903, /mcp)
                              v
+-------------------------------------------------------------+
| Unreal Engine Editor (Linux / Windows / macOS)              |
|   +-------------------------------------------------------+ |
|   | ModelContextProtocol Engine Plugin                    | |
|   +-------------------------------------------------------+ |
|   | ToolsetRegistry & EditorToolset                       | |
|   | - EditorAppToolset (Camera, Viewport, Console, CVars) | |
|   | - SceneTools & ActorTools (Levels, Actors, Spawning)  | |
|   | - MaterialInstanceTools (Shader Parameter Edits)      | |
|   | - ProgrammaticToolset (In-Editor Python Execution)     | |
|   | - PCGToolset (Procedural Content Generation)          | |
|   +-------------------------------------------------------+ |
+-------------------------------------------------------------+
```

---

## Quickstart

### 1. Enable Plugins in Your Unreal Project

In your `<ProjectName>.uproject`:

```json
{
  "Plugins": [
    { "Name": "ModelContextProtocol", "Enabled": true },
    { "Name": "ToolsetRegistry", "Enabled": true },
    { "Name": "EditorToolset", "Enabled": true },
    { "Name": "PythonScriptPlugin", "Enabled": true },
    { "Name": "EditorScriptingUtilities", "Enabled": true }
  ]
}
```

Add port configuration to `Config/DefaultEditorPerProjectUserSettings.ini`:

```ini
[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
ServerUrlPath=/mcp
ServerPortNumber=7903
bAutoStartServer=True
bEnableToolSearch=True
```

### 2. Launch Unreal Editor with MCP

Using the launcher script:

```bash
# Check status
bash scripts/launch_ue5_mcp.sh --status

# Launch in background daemon mode (headless / Vulkan)
bash scripts/launch_ue5_mcp.sh --daemon

# Or launch with full desktop GUI
bash scripts/launch_ue5_mcp.sh --gui
```

Direct binary command:

```bash
UnrealEditor /path/to/MyProject.uproject \
    -ModelContextProtocolStartServer \
    -ModelContextProtocolPort=7903
```

### 3. Operate via CLI

```bash
# Check connection
python scripts/mcp_cli.py status

# Teleport camera and capture a screenshot
python scripts/mcp_cli.py set-camera --x 0 --y 0 --z 1200 --pitch -15 --yaw 45
python scripts/mcp_cli.py capture-viewport --out /tmp/viewport.png

# Query level actors
python scripts/mcp_cli.py diagnostics

# Execute Python script inside Unreal
python scripts/mcp_cli.py exec-python --script "import unreal; print(unreal.SystemLibrary.get_engine_version())"
```

---

## Agent Configuration

### Antigravity / Gemini

Add to `~/.gemini/config/mcp_config.json` or `.mcp.json`:

```json
{
  "mcpServers": {
    "unreal-mcp": {
      "url": "http://127.0.0.1:7903/mcp"
    }
  }
}
```

To install as a workspace skill:

```bash
git clone https://github.com/jbernax/ue5-mcp-skill.git .agents/skills/ue5-mcp-operator
```

### Claude Desktop

Claude Desktop communicates via stdio. Use the zero-dependency Python stdio bridge ([`scripts/stdio_bridge.py`](scripts/stdio_bridge.py)) in your `claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "unreal-engine": {
      "command": "python3",
      "args": [
        "/path/to/ue5-mcp-skill/scripts/stdio_bridge.py"
      ],
      "env": {
        "UE_MCP_URL": "http://127.0.0.1:7903/mcp"
      }
    }
  }
}
```

The bridge exposes both native UE5 meta-tools (`list_toolsets`, `describe_toolset`, `call_tool`) and direct high-level tools (`ue5_capture_viewport`, `ue5_get_camera`, `ue5_set_camera`, `ue5_diagnostics`, `ue5_find_actors`, `ue5_execute_python`, `ue5_console_command`).

### Claude Code

See [`CLAUDE.md`](CLAUDE.md) for runbooks, CLI command references, and best practices tailored for Claude Code.

---

## Python API Example

```python
from scripts.ue5_mcp_client import UE5MCPClient

client = UE5MCPClient(mcp_url="http://127.0.0.1:7903/mcp")

# Probe socket and initialize session
if client.is_server_listening():
    session_id = client.initialize_session()
    print(f"Connected with session: {session_id}")

    # Set viewport camera
    client.set_camera_transform(
        location=(500.0, -1000.0, 800.0),
        rotation=(-20.0, 135.0, 0.0),
    )

    # Capture screenshot
    client.capture_viewport("/tmp/render.png")
```

---

## Repository Structure

```
ue5-mcp-skill/
├── SKILL.md                          # Main skill documentation for AI agents
├── CLAUDE.md                         # Dedicated guide for Claude Code and Claude Desktop
├── scripts/
│   ├── ue5_mcp_client.py             # Standalone Python MCP client library
│   ├── mcp_cli.py                    # Command-line interface operator
│   ├── stdio_bridge.py               # Stdio MCP server bridge for Claude Desktop
│   └── launch_ue5_mcp.sh             # Reusable Editor launcher and watchdog
├── references/
│   ├── toolsets_reference.md         # Comprehensive catalog of UE5 toolsets
│   └── ue5_setup_guide.md            # Advanced engine setup (headless, watchdog, networking)
├── examples/
│   ├── mcp_config.json               # MCP client configuration example
│   ├── claude_desktop_config.json   # Claude Desktop stdio bridge config example
│   ├── DefaultEditorPerProjectUserSettings.ini
│   └── sample_editor_script.py       # In-Editor Python automation example
├── tests/
│   ├── test_client.py                # Unit tests for Python client
│   ├── test_cli.py                   # Unit tests for CLI and launcher
│   └── test_stdio_bridge.py          # Unit tests for Claude stdio bridge
├── .github/workflows/ci.yml          # GitHub Actions CI workflow
├── pyproject.toml                    # Package metadata and entry points
├── LICENSE                           # MIT License
└── README.md
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
