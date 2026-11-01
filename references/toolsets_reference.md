# Unreal Engine 5 MCP Toolsets Reference

The Unreal Engine Model Context Protocol (MCP) server exposes built-in toolsets through three top-level meta-tools: `list_toolsets`, `describe_toolset`, and `call_tool`.

---

## 1. Top-Level Meta-Tools

### `list_toolsets`
Lists all toolsets currently registered in the active Unreal Editor session.
- **Parameters**: None
- **Returns**: Array/dict of toolset identifiers and descriptions.

### `describe_toolset`
Returns tool definitions and input parameter JSON schemas for a specified toolset.
- **Parameters**:
  - `toolset_name` (string, required): e.g., `EditorToolset.EditorAppToolset` or `editor_toolset.toolsets.scene.SceneTools`

### `call_tool`
Executes a specific tool within a toolset.
- **Parameters**:
  - `tool_name` (string, required): Name of the tool without toolset prefix.
  - `toolset_name` (string, optional): Target toolset name.
  - `arguments` (object, optional): Input parameters adhering to the tool schema.

---

## 2. Standard Registered Toolsets

### Viewport & Application (`EditorToolset.EditorAppToolset`)

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `SetCameraTransform` | `transform: {location: {x, y, z}, rotation: {pitch, yaw, roll}, scale: {x, y, z}}` | Teleports the active Editor viewport camera. |
| `GetCameraTransform` | `{}` | Returns the current viewport camera location, rotation, and scale. |
| `CaptureViewport` | `captureTransform: {...}, annotations: {...}, bShowUI: bool` | Captures a screenshot from the viewport at the specified transform. |
| `CaptureEditorImage` | `{}` | Captures an unannotated image of the active viewport. |
| `CaptureAssetImage` | `assetPath: string` | Captures a thumbnail image of a content asset. |
| `ExecuteConsoleCommand` | `command: string` | Runs an Editor console command (e.g., `stat fps`, `r.Nanite 1`). |
| `SearchCVars` | `pattern: string` | Searches console variables matching a pattern. |
| `GetCVar` | `name: string` | Queries current value of a console variable. |
| `SetCVar` | `name: string, value: string` | Sets the value of a console variable. |

---

### Scene & Level (`editor_toolset.toolsets.scene.SceneTools`)

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_current_level` | `{}` | Returns the active level name and package path. |
| `load_level` | `level_path: string` | Loads a level in the Editor. |
| `save_current_level` | `{}` | Saves dirty packages in the current level. |
| `find_actors` | `name: string, tag: string, collision_channels: string[]` | Searches active scene actors matching filters. |
| `add_to_scene_from_class` | `actor_type: {refPath: string}, name: string, xform: {...}` | Spawns a new actor instance by UClass reference. |
| `add_to_scene_from_asset` | `asset_path: string, name: string, xform: {...}` | Spawns an actor referencing a StaticMesh or Blueprint asset. |
| `trace_world` | `start: {x, y, z}, end: {x, y, z}` | Performs a world line trace and returns distance to first hit surface. |

---

### Actors (`editor_toolset.toolsets.actor.ActorTools`)

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_actor_transform` | `actor: string \| object` | Returns world transform for the given actor reference. |
| `set_actor_transform` | `actor: string \| object, xform: {location?, rotation?, scale?}` | Updates world location, rotation, or scale. |
| `destroy_actor` | `actor: string \| object` | Removes an actor from the active level. |
| `get_actor_components` | `actor: string \| object` | Lists components attached to the actor. |

---

### Assets (`editor_toolset.toolsets.asset.AssetTools`)

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `find_assets` | `directory_path: string, recursive: bool` | Searches content browser assets. |
| `save_assets` | `assets: string[]` | Saves modified assets to disk. |
| `import_assets` | `source_files: string[], destination_path: string` | Imports external files into content packages. |
| `duplicate_asset` | `source_path: string, destination_path: string` | Clones an existing asset. |
| `delete_asset` | `asset_path: string` | Deletes an asset from the project. |

---

### Materials & Instances (`editor_toolset.toolsets.material_instance.MaterialInstanceTools`)

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `set_scalar_parameter` | `instance: {refPath: string}, name: string, value: float` | Updates a scalar parameter (e.g. `Roughness`, `Metallic`). |
| `set_vector_parameter` | `instance: {refPath: string}, name: string, value: {r, g, b, a}` | Updates a 4-channel vector/color parameter (e.g. `BaseColorFactor`). |
| `set_texture_parameter` | `instance: {refPath: string}, name: string, texture: {refPath: string}` | Updates a texture parameter. |

---

### In-Editor Scripting (`editor_toolset.toolsets.programmatic.ProgrammaticToolset`)

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `execute_python_script` | `script: string` | Executes arbitrary Python code inside the Unreal Editor process with full access to `unreal` module. |
| `get_execution_environment` | `{}` | Returns Python interpreter state and engine version. |

---

### Procedural Content Generation (`PCGToolset.PCGToolset`)

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `execute_graph` | `graph_path: string, target_actor: string` | Executes or triggers generation on a PCG graph. |
| `inspect_graph` | `graph_path: string` | Queries nodes, parameters, and inputs of a PCG graph. |
