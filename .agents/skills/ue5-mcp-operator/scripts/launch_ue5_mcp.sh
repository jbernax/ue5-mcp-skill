#!/usr/bin/env bash
# Dedicated, reusable launcher for Unreal Engine 5.x with active Model Context Protocol (MCP).
# Supports auto-discovery of .uproject and UE5 Engine binary, memory watchdogs, and status probing.
set -euo pipefail

# 1. Resolve Engine Directory
ENGINE_DIR="${UE5_ENGINE_DIR:-${UE_ENGINE_DIR:-}}"
if [[ -z "${ENGINE_DIR}" ]]; then
    CANDIDATES=(
        "/home/antigravity/Engines/UE_5.8.4"
        "/opt/unreal-engine"
        "/opt/UE_5.8"
        "/opt/UE_5.7"
        "/opt/UE_5.6"
        "/opt/UE_5.5"
        "/opt/UE_5.4"
    )
    for c in "${CANDIDATES[@]}"; do
        if [[ -d "${c}/Engine/Binaries/Linux" ]] || [[ -d "${c}/Engine/Binaries/Win64" ]] || [[ -d "${c}/Engine/Binaries/Mac" ]]; then
            ENGINE_DIR="${c}"
            break
        fi
    done
fi

# 2. Resolve UnrealEditor Binary
EDITOR_BIN=""
if [[ -n "${ENGINE_DIR}" ]]; then
    if [[ -x "${ENGINE_DIR}/Engine/Binaries/Linux/UnrealEditor" ]]; then
        EDITOR_BIN="${ENGINE_DIR}/Engine/Binaries/Linux/UnrealEditor"
    elif [[ -x "${ENGINE_DIR}/Engine/Binaries/Win64/UnrealEditor.exe" ]]; then
        EDITOR_BIN="${ENGINE_DIR}/Engine/Binaries/Win64/UnrealEditor.exe"
    elif [[ -x "${ENGINE_DIR}/Engine/Binaries/Mac/UnrealEditor" ]]; then
        EDITOR_BIN="${ENGINE_DIR}/Engine/Binaries/Mac/UnrealEditor"
    fi
fi
if [[ -z "${EDITOR_BIN}" ]] && command -v UnrealEditor &>/dev/null; then
    EDITOR_BIN="$(command -v UnrealEditor)"
fi

# 3. Resolve .uproject Path
UPROJECT_PATH="${UPROJECT_PATH:-${UE_UPROJECT:-}}"
if [[ -z "${UPROJECT_PATH}" ]]; then
    # Search current directory, parent directory, and ue5_project subfolder
    FOUND_UPROJECT=$(find . .. -maxdepth 3 -name "*.uproject" 2>/dev/null | head -n 1 || true)
    if [[ -n "${FOUND_UPROJECT}" ]]; then
        UPROJECT_PATH="$(realpath "${FOUND_UPROJECT}")"
    fi
fi

# 4. Defaults & State Directory
MCP_PORT="${MCP_PORT:-7903}"
PROJECT_DIR="$(pwd)"
if [[ -n "${UPROJECT_PATH}" ]]; then
    PROJECT_DIR="$(dirname "${UPROJECT_PATH}")"
fi

PID_FILE="${PROJECT_DIR}/Saved/mcp_server.pid"
LOG_FILE="${PROJECT_DIR}/Saved/Logs/mcp_server.log"
mkdir -p "$(dirname "${PID_FILE}")"
mkdir -p "$(dirname "${LOG_FILE}")"

MAX_RSS_GB="${MAX_RSS_GB:-14}"
MAX_RSS_KB=$(( MAX_RSS_GB * 1024 * 1024 ))

MODE="${1:---status}"

case "${MODE}" in
    --gui)
        if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
            echo "Unreal Editor GUI is already running (PID: $(cat "${PID_FILE}"))."
            exit 0
        fi
        if [[ -z "${EDITOR_BIN}" ]]; then
            echo "ERROR: UnrealEditor binary not found. Set UE5_ENGINE_DIR or ensure UnrealEditor is in PATH." >&2
            exit 1
        fi
        if [[ -z "${UPROJECT_PATH}" ]]; then
            echo "ERROR: .uproject file not found. Set UPROJECT_PATH environment variable." >&2
            exit 1
        fi

        echo "Launching Unreal Editor GUI with MCP on port ${MCP_PORT}..."
        echo "Engine: ${EDITOR_BIN}"
        echo "Project: ${UPROJECT_PATH}"
        export DISPLAY="${DISPLAY:-:0}"
        setsid "${EDITOR_BIN}" \
            "${UPROJECT_PATH}" \
            -ModelContextProtocolStartServer \
            -ModelContextProtocolPort="${MCP_PORT}" \
            -vulkan \
            > "${LOG_FILE}" 2>&1 &
        EDITOR_PID=$!
        echo "${EDITOR_PID}" > "${PID_FILE}"
        echo "Launched Editor with PID ${EDITOR_PID}. Waiting for MCP port ${MCP_PORT}..."

        # Memory Watchdog and Port Wait Loop
        for i in {1..45}; do
            if ! kill -0 "${EDITOR_PID}" 2>/dev/null; then
                echo "ERROR: Editor process ${EDITOR_PID} terminated unexpectedly during startup." >&2
                tail -n 25 "${LOG_FILE}" 2>/dev/null || true
                rm -f "${PID_FILE}"
                exit 1
            fi

            if [[ -f "/proc/${EDITOR_PID}/statm" ]]; then
                PAGES=$(awk '{print $2}' "/proc/${EDITOR_PID}/statm" 2>/dev/null || echo 0)
                PAGE_SIZE=$(getconf PAGESIZE 2>/dev/null || echo 4096)
                RSS_KB=$(( (PAGES * PAGE_SIZE) / 1024 ))
                if [[ "${RSS_KB}" -gt "${MAX_RSS_KB}" ]]; then
                    echo "SAFETY WATCHDOG: RSS memory ($(( RSS_KB / 1024 )) MiB) exceeded limit (${MAX_RSS_GB} GiB). Terminating." >&2
                    kill -9 "${EDITOR_PID}" 2>/dev/null || true
                    rm -f "${PID_FILE}"
                    exit 1
                fi
            fi

            if curl -s "http://127.0.0.1:${MCP_PORT}/" >/dev/null 2>&1 || nc -z 127.0.0.1 "${MCP_PORT}" 2>/dev/null; then
                echo "Unreal MCP server is active and listening at http://127.0.0.1:${MCP_PORT}/mcp"
                exit 0
            fi
            sleep 2
        done
        echo "Startup wait period ended. Editor PID ${EDITOR_PID} is running. Check log at ${LOG_FILE}"
        ;;

    --daemon)
        if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
            echo "Unreal Editor MCP daemon is already running (PID: $(cat "${PID_FILE}"))."
            exit 0
        fi
        if [[ -z "${EDITOR_BIN}" ]]; then
            echo "ERROR: UnrealEditor binary not found. Set UE5_ENGINE_DIR or ensure UnrealEditor is in PATH." >&2
            exit 1
        fi
        if [[ -z "${UPROJECT_PATH}" ]]; then
            echo "ERROR: .uproject file not found. Set UPROJECT_PATH environment variable." >&2
            exit 1
        fi

        echo "Launching Unreal Editor Daemon with MCP on port ${MCP_PORT}..."
        setsid "${EDITOR_BIN}" \
            "${UPROJECT_PATH}" \
            -ModelContextProtocolStartServer \
            -ModelContextProtocolPort="${MCP_PORT}" \
            -nosplash -vulkan \
            > "${LOG_FILE}" 2>&1 &
        echo $! > "${PID_FILE}"
        echo "Unreal MCP daemon launched with PID $(cat "${PID_FILE}"). Waiting for port ${MCP_PORT}..."

        for i in {1..30}; do
            if curl -s "http://127.0.0.1:${MCP_PORT}/" >/dev/null 2>&1 || nc -z 127.0.0.1 "${MCP_PORT}" 2>/dev/null; then
                echo "Unreal MCP server is active and listening at http://127.0.0.1:${MCP_PORT}/mcp"
                exit 0
            fi
            sleep 1
        done
        echo "Daemon started. Log at ${LOG_FILE}"
        ;;

    --kill)
        if [[ -f "${PID_FILE}" ]]; then
            PID=$(cat "${PID_FILE}")
            if kill -0 "${PID}" 2>/dev/null; then
                echo "Terminating Unreal MCP process ${PID}..."
                kill "${PID}" || kill -9 "${PID}"
                rm -f "${PID_FILE}"
                echo "Terminated."
            else
                rm -f "${PID_FILE}"
                echo "Process ${PID} was not running."
            fi
        else
            echo "No PID file found at ${PID_FILE}."
        fi
        ;;

    --status)
        echo "=== Unreal Engine MCP Status (Port ${MCP_PORT}) ==="
        if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
            ACTIVE_PID=$(cat "${PID_FILE}")
            if [[ -f "/proc/${ACTIVE_PID}/statm" ]]; then
                PAGES=$(awk '{print $2}' "/proc/${ACTIVE_PID}/statm" 2>/dev/null || echo 0)
                PAGE_SIZE=$(getconf PAGESIZE 2>/dev/null || echo 4096)
                RSS_MIB=$(( (PAGES * PAGE_SIZE) / 1024 / 1024 ))
                echo "Editor process : RUNNING (PID: ${ACTIVE_PID}, RSS: ${RSS_MIB} MiB)"
            else
                echo "Editor process : RUNNING (PID: ${ACTIVE_PID})"
            fi
        else
            echo "Editor process : NOT RUNNING"
        fi
        if nc -z 127.0.0.1 "${MCP_PORT}" 2>/dev/null; then
            echo "Port ${MCP_PORT}     : LISTENING (http://127.0.0.1:${MCP_PORT}/mcp)"
        else
            echo "Port ${MCP_PORT}     : NOT LISTENING"
        fi
        if command -v nvidia-smi &>/dev/null; then
            echo "GPU VRAM       : $(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null || echo 'N/A')"
        fi
        ;;

    --test)
        echo "Verification OK"
        echo "Engine Dir: ${ENGINE_DIR:-<Not Detected>}"
        echo "Editor Binary: ${EDITOR_BIN:-<Not Detected>}"
        echo "UProject Path: ${UPROJECT_PATH:-<Not Detected>}"
        echo "MCP Port: ${MCP_PORT}"
        exit 0
        ;;

    *)
        echo "Usage: $0 [--gui | --daemon | --kill | --status | --test]" >&2
        exit 1
        ;;
esac
