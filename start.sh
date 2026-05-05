#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# --- 配置 ---
BACKEND_PORT="${CHANLAN_PORT:-8000}"
FRONTEND_PORT="${VITE_PORT:-5173}"
PID_DIR=".cache"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

# --- 工具函数 ---
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
die()  { log "ERROR: $*" >&2; exit 1; }

check_port() { lsof -i ":$1" -sTCP:LISTEN -t 2>/dev/null || true; }

# --- 前置检查 ---
[ -f pyproject.toml ] || die "请在项目根目录运行"

mkdir -p "$PID_DIR"

# 如果已经在运行，提示并退出
if [ -f "$BACKEND_PID_FILE" ] && kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
    log "后端已在运行 (PID $(cat "$BACKEND_PID_FILE"), 端口 $BACKEND_PORT)"
else
    # 确保 venv 存在
    if [ ! -f .venv/bin/uvicorn ]; then
        log "安装 Python 依赖..."
        python3 -m venv .venv
        .venv/bin/pip install -q -e .
    fi

    log "启动后端 (FastAPI → :$BACKEND_PORT)..."
    .venv/bin/python -m uvicorn app.main:app \
        --host 0.0.0.0 --port "$BACKEND_PORT" &>/dev/null &
    echo $! > "$BACKEND_PID_FILE"

    # 等待后端就绪
    for i in $(seq 1 20); do
        if [ -n "$(check_port "$BACKEND_PORT")" ]; then
            break
        fi
        sleep 0.5
    done
    log "后端已启动 (PID $(cat "$BACKEND_PID_FILE"))"
fi

if [ -f "$FRONTEND_PID_FILE" ] && kill -0 "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; then
    log "前端已在运行 (PID $(cat "$FRONTEND_PID_FILE"), 端口 $FRONTEND_PORT)"
else
    # 确保 Node 版本满足 Vite 8 要求
    node_version=$(node -v 2>/dev/null || echo "v0")
    node_major=$(echo "$node_version" | sed 's/v\([0-9]*\).*/\1/')
    if [ "$node_major" -lt 20 ]; then
        # 尝试 nvm
        if [ -f "$HOME/.nvm/nvm.sh" ]; then
            source "$HOME/.nvm/nvm.sh"
            nvm use 22 &>/dev/null || true
        fi
    fi

    # 确保 npm 依赖存在
    if [ ! -d frontend/node_modules ]; then
        log "安装前端依赖..."
        (cd frontend && npm install --silent)
    fi

    log "启动前端 (Vite → :$FRONTEND_PORT)..."
    (cd frontend && npx vite --port "$FRONTEND_PORT") &>/dev/null &
    echo $! > "$FRONTEND_PID_FILE"

    for i in $(seq 1 20); do
        if [ -n "$(check_port "$FRONTEND_PORT")" ]; then
            break
        fi
        sleep 0.5
    done
    log "前端已启动 (PID $(cat "$FRONTEND_PID_FILE"))"
fi

echo ""
log "✓ 服务已就绪:"
log "  后端 API  → http://localhost:$BACKEND_PORT"
log "  前端页面  → http://localhost:$FRONTEND_PORT"
log "  停止服务  → ./stop.sh"
