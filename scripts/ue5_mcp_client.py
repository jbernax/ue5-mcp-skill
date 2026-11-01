#!/usr/bin/env python3
"""
Unreal Engine 5 Model Context Protocol (MCP) Client Library.

Provides a standalone, zero-dependency Python client for interacting with Unreal Engine
5.4+ / 5.5+ / 5.6+ / 5.7+ / 5.8+ editors running the native ModelContextProtocol plugin
over Streamable HTTP / JSON-RPC 2.0 (default port 7903).
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from typing import Any
import urllib.error
import urllib.request


DEFAULT_MCP_URL = "http://127.0.0.1:7903/mcp"
DEFAULT_MCP_PORT = 7903


@dataclass(frozen=True)
class CoordinateAnchor:
    """
    Geodetic or world-space reference anchor for converting external coordinates
    (e.g., UTM Zone meters or GIS elevations) into Unreal Engine world centimeters.
    """
    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0
    scale_to_cm: float = 100.0
    invert_y: bool = True  # Invert Y if source is North=+Y (UE5 is left-handed where North is -Y)

    def to_ue5_cm(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        dx = (x - self.origin_x) * self.scale_to_cm
        dy = (y - self.origin_y) * self.scale_to_cm
        dz = (z - self.origin_z) * self.scale_to_cm
        return (round(dx, 2), round(-dy if self.invert_y else dy, 2), round(dz, 2))


class UE5MCPClient:
    """
    Stateful JSON-RPC 2.0 client for the Unreal Engine Model Context Protocol plugin.

    Handles Mcp-Session-Id negotiation, toolset discovery, actor querying/spawning,
    material parameter adjustment, camera teleportation, viewport screenshot capture,
    and in-Editor Python script execution.
    """

    def __init__(
        self,
        mcp_url: str = DEFAULT_MCP_URL,
        port: int = DEFAULT_MCP_PORT,
        timeout_s: float = 30.0,
    ) -> None:
        self.mcp_url = mcp_url
        self.port = port
        self.timeout_s = timeout_s
        self._session_id: str | None = None
        self._req_id: int = 0

    def is_server_listening(self) -> bool:
        """Checks whether the Unreal Editor MCP port is listening on localhost."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            return sock.connect_ex(("127.0.0.1", self.port)) == 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    @staticmethod
    def _parse_json_or_sse(raw_body: str) -> dict[str, Any]:
        text = raw_body.strip()
        if not text:
            return {}
        if text.startswith("{"):
            return json.loads(text)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("data:"):
                payload = stripped[len("data:") :].strip()
                if payload.startswith("{"):
                    return json.loads(payload)
        return {"raw": text}

    def _send_rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        is_notification: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if not is_notification:
            payload["id"] = self._next_id()
        if params is not None:
            payload["params"] = params

        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        req = urllib.request.Request(self.mcp_url, data=data_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            for k, v in resp.headers.items():
                if k.lower() == "mcp-session-id" and v:
                    self._session_id = v.strip()
            body = resp.read().decode("utf-8", errors="replace")
            return self._parse_json_or_sse(body)

    def initialize_session(self) -> str:
        """Negotiates an MCP 2025-11-25 session and caches the Mcp-Session-Id."""
        if self._session_id:
            return self._session_id
        self._send_rpc(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "UE5MCPClient", "version": "1.0.0"},
            },
        )
        try:
            self._send_rpc("notifications/initialized", {}, is_notification=True)
        except Exception:
            pass
        return self._session_id or ""

    def call_meta_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Invokes one of the 3 top-level UE5 MCP meta-tools: list_toolsets, describe_toolset, or call_tool."""
        if not self._session_id:
            self.initialize_session()
        try:
            return self._send_rpc("tools/call", {"name": name, "arguments": arguments or {}})
        except urllib.error.HTTPError:
            self._session_id = None
            self.initialize_session()
            return self._send_rpc("tools/call", {"name": name, "arguments": arguments or {}})

    @staticmethod
    def _unwrap_tool_result(rpc_response: dict[str, Any]) -> Any:
        result = rpc_response.get("result", rpc_response)
        if isinstance(result, dict) and "content" in result:
            contents = result["content"]
            texts = []
            images = []
            for item in contents:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and "text" in item:
                    txt = item["text"]
                    try:
                        texts.append(json.loads(txt))
                    except Exception:
                        texts.append(txt)
                elif item.get("type") == "image" and "data" in item:
                    images.append(item["data"])
            if images and not texts:
                return {"images_base64": images}
            if images and texts:
                return {"data": texts[0] if len(texts) == 1 else texts, "images_base64": images}
            if len(texts) == 1:
                return texts[0]
            return texts
        return result

    def list_toolsets(self) -> Any:
        """Returns all registered toolsets from the Unreal Editor MCP server."""
        resp = self.call_meta_tool("list_toolsets", {})
        return self._unwrap_tool_result(resp)

    def describe_toolset(self, toolset_name: str) -> Any:
        """Retrieves tool names, descriptions, and schemas for a specified toolset."""
        resp = self.call_meta_tool("describe_toolset", {"toolset_name": toolset_name})
        return self._unwrap_tool_result(resp)

    def call_tool(
        self,
        tool_name: str,
        toolset_name: str | None = None,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Executes a tool within a toolset on the running Unreal Editor."""
        payload: dict[str, Any] = {
            "tool_name": tool_name,
            "arguments": arguments or {},
        }
        if toolset_name:
            payload["toolset_name"] = toolset_name
        resp = self.call_meta_tool("call_tool", payload)
        return self._unwrap_tool_result(resp)

    # -------------------------------------------------------------------------
    # Viewport & Camera Operations
    # -------------------------------------------------------------------------

    def set_camera_transform(
        self,
        location: tuple[float, float, float] | dict[str, float],
        rotation: tuple[float, float, float] | dict[str, float],
        scale: tuple[float, float, float] | dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """
        Sets the active Editor viewport camera location (cm) and rotation (pitch, yaw, roll in degrees).
        """
        loc_dict = location if isinstance(location, dict) else {"x": location[0], "y": location[1], "z": location[2]}
        rot_dict = (
            rotation
            if isinstance(rotation, dict)
            else {"pitch": rotation[0], "yaw": rotation[1], "roll": rotation[2]}
        )
        scl_dict = (
            (scale if isinstance(scale, dict) else {"x": scale[0], "y": scale[1], "z": scale[2]})
            if scale
            else {"x": 1.0, "y": 1.0, "z": 1.0}
        )

        res = self.call_tool(
            tool_name="SetCameraTransform",
            toolset_name="EditorToolset.EditorAppToolset",
            arguments={"transform": {"location": loc_dict, "rotation": rot_dict, "scale": scl_dict}},
        )
        return {"location": loc_dict, "rotation": rot_dict, "mcp_response": res}

    def get_camera_transform(self) -> dict[str, Any]:
        """Queries the current active Editor viewport camera transform."""
        res = self.call_tool(
            tool_name="GetCameraTransform",
            toolset_name="EditorToolset.EditorAppToolset",
            arguments={},
        )
        if isinstance(res, dict) and "returnValue" in res:
            return res["returnValue"]
        return res if isinstance(res, dict) else {}

    def capture_viewport(self, output_path: Path | str, b_show_ui: bool = False) -> Path | None:
        """
        Captures the active Unreal Editor viewport and saves it as a PNG image to output_path.
        Attempts CaptureViewport first, falling back to CaptureEditorImage.
        """
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        cam_xform = self.get_camera_transform() or {
            "location": {"x": 0.0, "y": 0.0, "z": 1000.0},
            "rotation": {"pitch": -10.0, "yaw": 0.0, "roll": 0.0},
            "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
        }

        candidates = [
            (
                "CaptureViewport",
                {
                    "captureTransform": cam_xform,
                    "annotations": {
                        "gridSpacing": 0.0,
                        "gridExtent": 0.0,
                        "gridHeight": 0.0,
                        "maxLabelDistance": 0.0,
                        "classFilter": {"refPath": ""},
                        "maxLabels": 0,
                    },
                    "bShowUI": b_show_ui,
                },
            ),
            ("CaptureEditorImage", {}),
        ]

        for tool_name, tool_args in candidates:
            try:
                res = self.call_tool(
                    tool_name=tool_name,
                    toolset_name="EditorToolset.EditorAppToolset",
                    arguments=tool_args,
                )
                if isinstance(res, dict):
                    if "images_base64" in res and res["images_base64"]:
                        out_p.write_bytes(base64.b64decode(res["images_base64"][0]))
                        return out_p
                    ret_val = res.get("returnValue", res.get("data", res))
                    if isinstance(ret_val, dict):
                        img_obj = ret_val.get("image", ret_val)
                        if isinstance(img_obj, dict) and isinstance(img_obj.get("data"), str):
                            out_p.write_bytes(base64.b64decode(img_obj["data"]))
                            return out_p
                        for key in ("FilePath", "file_path", "ImagePath", "Path", "ReturnValue"):
                            val = ret_val.get(key)
                            if isinstance(val, str) and Path(val).exists():
                                shutil.copyfile(val, out_p)
                                return out_p
                    elif isinstance(ret_val, str) and Path(ret_val).exists():
                        shutil.copyfile(ret_val, out_p)
                        return out_p
            except Exception:
                continue
        return None

    # -------------------------------------------------------------------------
    # Scene & Level Operations
    # -------------------------------------------------------------------------

    def get_current_level(self) -> dict[str, Any]:
        """Queries the active level name and package path."""
        res = self.call_tool(
            tool_name="get_current_level",
            toolset_name="editor_toolset.toolsets.scene.SceneTools",
            arguments={},
        )
        return res if isinstance(res, dict) else {"returnValue": res}

    def find_actors(
        self,
        name: str = "",
        tag: str = "",
        collision_channels: list[str] | None = None,
    ) -> list[Any]:
        """Finds actors matching name or tag."""
        res = self.call_tool(
            tool_name="find_actors",
            toolset_name="editor_toolset.toolsets.scene.SceneTools",
            arguments={
                "name": name,
                "tag": tag,
                "collision_channels": collision_channels or [],
            },
        )
        if isinstance(res, dict) and "returnValue" in res:
            return res["returnValue"] if isinstance(res["returnValue"], list) else [res["returnValue"]]
        return res if isinstance(res, list) else []

    def add_actor_from_class(
        self,
        class_path: str,
        actor_name: str,
        location: tuple[float, float, float] | dict[str, float] = (0.0, 0.0, 0.0),
        rotation: tuple[float, float, float] | dict[str, float] = (0.0, 0.0, 0.0),
        scale: tuple[float, float, float] | dict[str, float] = (1.0, 1.0, 1.0),
    ) -> Any:
        """Spawns an actor into the active scene by its UClass reference path."""
        loc = location if isinstance(location, dict) else {"x": location[0], "y": location[1], "z": location[2]}
        rot = rotation if isinstance(rotation, dict) else {"pitch": rotation[0], "yaw": rotation[1], "roll": rotation[2]}
        scl = scale if isinstance(scale, dict) else {"x": scale[0], "y": scale[1], "z": scale[2]}
        return self.call_tool(
            tool_name="add_to_scene_from_class",
            toolset_name="editor_toolset.toolsets.scene.SceneTools",
            arguments={
                "actor_type": {"refPath": class_path},
                "name": actor_name,
                "xform": {"location": loc, "rotation": rot, "scale": scl},
            },
        )

    def add_actor_from_asset(
        self,
        asset_path: str,
        actor_name: str,
        location: tuple[float, float, float] | dict[str, float] = (0.0, 0.0, 0.0),
        rotation: tuple[float, float, float] | dict[str, float] = (0.0, 0.0, 0.0),
        scale: tuple[float, float, float] | dict[str, float] = (1.0, 1.0, 1.0),
    ) -> Any:
        """Spawns an actor into the active scene referencing a StaticMesh or Blueprint asset."""
        loc = location if isinstance(location, dict) else {"x": location[0], "y": location[1], "z": location[2]}
        rot = rotation if isinstance(rotation, dict) else {"pitch": rotation[0], "yaw": rotation[1], "roll": rotation[2]}
        scl = scale if isinstance(scale, dict) else {"x": scale[0], "y": scale[1], "z": scale[2]}
        return self.call_tool(
            tool_name="add_to_scene_from_asset",
            toolset_name="editor_toolset.toolsets.scene.SceneTools",
            arguments={
                "asset_path": asset_path,
                "name": actor_name,
                "xform": {"location": loc, "rotation": rot, "scale": scl},
            },
        )

    def get_actor_transform(self, actor_ref: Any) -> dict[str, Any]:
        """Gets world transform for an actor reference."""
        res = self.call_tool(
            tool_name="get_actor_transform",
            toolset_name="editor_toolset.toolsets.actor.ActorTools",
            arguments={"actor": actor_ref},
        )
        if isinstance(res, dict) and "returnValue" in res:
            return res["returnValue"]
        return res if isinstance(res, dict) else {}

    def set_actor_transform(
        self,
        actor_ref: Any,
        location: tuple[float, float, float] | dict[str, float] | None = None,
        rotation: tuple[float, float, float] | dict[str, float] | None = None,
        scale: tuple[float, float, float] | dict[str, float] | None = None,
    ) -> Any:
        """Updates world transform for an actor."""
        xform: dict[str, Any] = {}
        if location is not None:
            xform["location"] = location if isinstance(location, dict) else {"x": location[0], "y": location[1], "z": location[2]}
        if rotation is not None:
            xform["rotation"] = rotation if isinstance(rotation, dict) else {"pitch": rotation[0], "yaw": rotation[1], "roll": rotation[2]}
        if scale is not None:
            xform["scale"] = scale if isinstance(scale, dict) else {"x": scale[0], "y": scale[1], "z": scale[2]}
        return self.call_tool(
            tool_name="set_actor_transform",
            toolset_name="editor_toolset.toolsets.actor.ActorTools",
            arguments={"actor": actor_ref, "xform": xform},
        )

    def destroy_actor(self, actor_ref: Any) -> Any:
        """Destroys an actor in the active scene."""
        return self.call_tool(
            tool_name="destroy_actor",
            toolset_name="editor_toolset.toolsets.actor.ActorTools",
            arguments={"actor": actor_ref},
        )

    # -------------------------------------------------------------------------
    # Material Instance Parameter Operations
    # -------------------------------------------------------------------------

    def set_scalar_parameter(self, material_instance_ref: str, name: str, value: float) -> Any:
        """Sets a scalar parameter on a UMaterialInstanceConstant."""
        return self.call_tool(
            tool_name="set_scalar_parameter",
            toolset_name="editor_toolset.toolsets.material_instance.MaterialInstanceTools",
            arguments={
                "instance": {"refPath": material_instance_ref},
                "name": name,
                "value": float(value),
            },
        )

    def set_vector_parameter(
        self,
        material_instance_ref: str,
        name: str,
        r: float,
        g: float,
        b: float,
        a: float = 1.0,
    ) -> Any:
        """Sets a 4-channel vector/color parameter on a UMaterialInstanceConstant."""
        return self.call_tool(
            tool_name="set_vector_parameter",
            toolset_name="editor_toolset.toolsets.material_instance.MaterialInstanceTools",
            arguments={
                "instance": {"refPath": material_instance_ref},
                "name": name,
                "value": {"r": float(r), "g": float(g), "b": float(b), "a": float(a)},
            },
        )

    # -------------------------------------------------------------------------
    # In-Editor Python Execution
    # -------------------------------------------------------------------------

    def execute_python_script(self, script_code: str) -> Any:
        """Executes Python code directly inside Unreal Editor via ProgrammaticToolset."""
        return self.call_tool(
            tool_name="execute_python_script",
            toolset_name="editor_toolset.toolsets.programmatic.ProgrammaticToolset",
            arguments={"script": script_code},
        )

    # -------------------------------------------------------------------------
    # Console Commands & CVars
    # -------------------------------------------------------------------------

    def execute_console_command(self, command: str) -> Any:
        """Executes an Unreal Editor console command."""
        return self.call_tool(
            tool_name="ExecuteConsoleCommand",
            toolset_name="EditorToolset.EditorAppToolset",
            arguments={"command": command},
        )

    def get_cvar(self, cvar_name: str) -> Any:
        """Gets value of a console variable."""
        return self.call_tool(
            tool_name="GetCVar",
            toolset_name="EditorToolset.EditorAppToolset",
            arguments={"name": cvar_name},
        )

    def set_cvar(self, cvar_name: str, value: Any) -> Any:
        """Sets value of a console variable."""
        return self.call_tool(
            tool_name="SetCVar",
            toolset_name="EditorToolset.EditorAppToolset",
            arguments={"name": cvar_name, "value": str(value)},
        )
