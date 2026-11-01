# Advanced Unreal Engine 5 MCP Configuration Guide

This guide covers advanced engine integration, headless cloud execution, performance considerations, and networking for the Unreal Engine Model Context Protocol (MCP) server.

For basic project setup and quickstart, refer to the [README.md](../README.md).

---

## 1. Headless Linux, Containers & Cloud Workstations

### Offscreen Rendering vs NullRHI

When running in automated CI/CD pipelines, container environments (Docker), or remote servers:

- **Do NOT use `-nullrhi` if screenshot capture is required**: `-nullrhi` completely disables the rendering hardware interface. While the MCP server will listen and actor/level tools will execute, `CaptureViewport` will fail or produce black images.
- **Use Vulkan offscreen**:
  ```bash
  UnrealEditor /path/to/project.uproject \
      -ModelContextProtocolStartServer \
      -ModelContextProtocolPort=7903 \
      -nosplash \
      -vulkan
  ```
- **Virtual Display (Xvfb)**: If running on a Linux host without a physical X server:
  ```bash
  Xvfb :99 -screen 0 1920x1080x24 &
  export DISPLAY=:99
  ```

---

## 2. Memory Watchdogs & Long-Running Sessions

The Unreal Editor process accumulates cache and memory over long-running sessions, especially when loading multiple levels or procedural content.

The provided [`launch_ue5_mcp.sh`](../scripts/launch_ue5_mcp.sh) script includes an automated RSS watchdog:
- Monitored via `/proc/<pid>/statm` (Linux).
- Default threshold: `MAX_RSS_GB=14` (configurable via environment variable).
- Safely terminates runaway Editor instances before kernel OOM killer triggers.

---

## 3. Extending Toolsets in Custom C++

Projects can register their own custom tools with the MCP server by implementing the `IToolset` interface or decorating UFunctions:

1. Add `ModelContextProtocol` and `ToolsetRegistry` to your module's `Build.cs`:
   ```csharp
   PublicDependencyModuleNames.AddRange(new string[] {
       "Core",
       "CoreUObject",
       "Engine",
       "ModelContextProtocol",
       "ToolsetRegistry",
       "EditorToolset"
   });
   ```
2. Any `UFUNCTION` exposed via the toolset registry will automatically become discoverable under `list_toolsets` and invokable via `call_tool`.

---

## 4. Remote Networking & Port Forwarding

By default, the MCP server binds to `127.0.0.1:7903`. To connect from a remote workstation or agent container:

### SSH Port Forwarding

Forward the remote port to your local machine:

```bash
ssh -N -L 7903:127.0.0.1:7903 user@remote-unreal-host
```

Once forwarded, local clients (`mcp_cli.py`, Antigravity, Claude Desktop) connect to `http://127.0.0.1:7903/mcp` without modifying firewall rules or exposing unauthenticated HTTP endpoints to public networks.

---

## 5. Troubleshooting Matrix

| Issue | Cause | Resolution |
| :--- | :--- | :--- |
| `Connection refused` on port 7903 | MCP server not started or port blocked | Check `launch_ue5_mcp.sh --status`. Verify `-ModelContextProtocolStartServer` is in launch flags. |
| Viewport screenshot is black | GPU rendering not active (e.g. `-nullrhi`) | Run with `-vulkan` and ensure Vulkan driver is loaded (`vulkaninfo`). |
| Session ID expires | Long inactivity period | Handled automatically by `UE5MCPClient`, which renegotiates sessions on HTTP 400. |
| Python script tool not found | `PythonScriptPlugin` disabled | Enable `PythonScriptPlugin` and `EditorScriptingUtilities` in `.uproject`. |
