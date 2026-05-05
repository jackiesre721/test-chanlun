#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PID_DIR=".cache"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

stop_service() {
    local name="$1" pid_file="$2" port="$3"
    local stopped=false

    # 先尝试 PID 文件
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log "停止 $name (PID $pid)..."
            kill "$pid" 2>/dev/null || true
            # 等待进程退出
            for i in $(seq 1 10); do
                kill -0 "$pid" 2>/dev/null || break
                sleep 0.3
            done
            # 如果还活着，强杀
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
            stopped=true
        fi
        rm -f "$pid_file"
    fi

    # 兜底：按端口杀
    pids=$(lsof -i ":$port" -sTCP:LISTEN -t 2>/dev/null || true)
    if [ -n "$pids" ]; then
        for pid in $pids; do
            log "端口 $port 仍有进程 (PID $pid)，正在停止..."
            kill "$pid" 2>/dev/null || true
        done
        stopped=true
    fi

    if [ "$stopped" = true ]; then
        log "$name 已停止"
    else
        log "$name 未在运行"
    fi
}

stop_service "后端" "$BACKEND_PID_FILE" "${CHANLAN_PORT:-8000}"
stop_service "前端" "$FRONTEND_PID_FILE" "${VITE_PORT:-5173}"

echo ""
log "✓ 所有服务已停止"
