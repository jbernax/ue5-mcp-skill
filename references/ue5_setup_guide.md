# Unreal Engine Project Setup for MCP

This guide outlines how to enable and configure the native Model Context Protocol (MCP) server in any Unreal Engine 5.4+ / 5.5+ / 5.6+ / 5.7+ / 5.8+ project.

---

## 1. Required Plugins in `.uproject`

Add or verify the following plugins in your project's `.uproject` file:

```json
{
  "Plugins": [
    {
      "Name": "ModelContextProtocol",
      "Enabled": true
    },
    {
      "Name": "ToolsetRegistry",
      "Enabled": true
    },
    {
      "Name": "EditorToolset",
      "Enabled": true
    },
    {
      "Name": "PythonScriptPlugin",
      "Enabled": true
    },
    {
      "Name": "EditorScriptingUtilities",
      "Enabled": true
    },
    {
      "Name": "PCGToolset",
      "Enabled": true,
      "Optional": true
    }
  ]
}
```

---

## 2. Configuration Settings (`Config/DefaultEditorPerProjectUserSettings.ini`)

Configure the MCP server port and startup behavior in `Config/DefaultEditorPerProjectUserSettings.ini` (or `Config/DefaultEngine.ini`):

```ini
[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
ServerUrlPath=/mcp
ServerPortNumber=7903
bAutoStartServer=True
bEnableToolSearch=True
```

---

## 3. Launching Unreal Editor with MCP

### Command-Line Arguments

When launching the Editor, pass the MCP flags:

```bash
UnrealEditor /path/to/MyProject.uproject \
    -ModelContextProtocolStartServer \
    -ModelContextProtocolPort=7903
```

### Headless / Daemon Mode (Linux / CI / Cloud)

For automated pipelines or containerized environments:

```bash
UnrealEditor /path/to/MyProject.uproject \
    -ModelContextProtocolStartServer \
    -ModelContextProtocolPort=7903 \
    -nosplash \
    -vulkan
```

### Using the Provided Launcher Script

```bash
# Check status
bash scripts/launch_ue5_mcp.sh --status

# Launch in background daemon mode
bash scripts/launch_ue5_mcp.sh --daemon

# Launch full desktop GUI Editor
bash scripts/launch_ue5_mcp.sh --gui

# Stop Editor safely
bash scripts/launch_ue5_mcp.sh --kill
```

---

## 4. Configuring Agent MCP Clients

### Antigravity (`~/.gemini/config/mcp_config.json` or `.mcp.json`)

```json
{
  "mcpServers": {
    "unreal-mcp": {
      "url": "http://127.0.0.1:7903/mcp"
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

For clients requiring stdio bridges, or direct Streamable HTTP:

```json
{
  "mcpServers": {
    "unreal-mcp": {
      "command": "python",
      "args": ["-m", "scripts.mcp_cli", "status"]
    }
  }
}
```

---

## 5. Verification

Probe the port directly:

```bash
# Check port listening
nc -z 127.0.0.1 7903 && echo "Listening"

# Check status via CLI
python scripts/mcp_cli.py status

# Query active level
python scripts/mcp_cli.py diagnostics
```
