#!/usr/bin/env bash
# tcm-doctor 一键启动脚本（开发/检查用）
# 用法:
#   ./start.sh            # 默认：前后端开发模式（后端 uvicorn + 前端 vite）
#   ./start.sh web        # 同上
#   ./start.sh electron   # Electron 桌面壳开发模式（会自动 tsc 编译 electron 入口）
set -u

cd "$(dirname "$0")" || exit 1

MODE="${1:-web}"

echo "==> tcm-doctor 启动脚本 (模式: $MODE)"

# ---- 前端依赖 ----
if [ ! -d "frontend/node_modules" ]; then
  echo "==> 安装前端依赖 (frontend) ..."
  (cd frontend && npm install) || { echo "前端依赖安装失败，请手动: cd frontend && npm install"; exit 1; }
fi

# ---- 根依赖 (concurrently / typescript / electron) ----
if [ ! -d "node_modules" ]; then
  echo "==> 安装根依赖 (concurrently/electron/typescript) ..."
  npm install || { echo "根依赖安装失败，请手动: npm install"; exit 1; }
fi

# ---- 后端 .env ----
if [ ! -f "backend/.env" ]; then
  echo "==> 未检测到 backend/.env，写入默认开发配置 ..."
  cat > backend/.env <<'EOF'
APP_NAME=tcm-doctor
DATABASE_URL=sqlite:///./tcm_doctor.db
SECRET_KEY=dev-secret-change-me
DEEPSEEK_API_KEY=
HOST=127.0.0.1
PORT=8765
ALLOW_GUEST_LOGIN=false
ENABLE_SEMANTIC_SEARCH=false
EOF
  echo "    （已生成 backend/.env；如需 AI 辨证，填入 DEEPSEEK_API_KEY）"
fi

# ---- 后端 Python 依赖 ----
if ! python3 -c "import fastapi, uvicorn, sqlalchemy" >/dev/null 2>&1; then
  echo "==> 未检测到后端依赖，尝试 pip 安装 (含 ai 可选依赖: chromadb/openai) ..."
  (cd backend && python3 -m pip install -e ".[ai]") || {
    echo "后端依赖安装失败。请手动: cd backend && python3 -m pip install -e \".[ai]\""; exit 1; }
fi

# ---- 启动 ----
if [ "$MODE" = "electron" ]; then
  echo "==> 启动 Electron 桌面壳 (dev) ..."
  npm run dev:electron
else
  echo "==> 启动开发模式：后端 uvicorn(:8765) + 前端 vite"
  echo "    前端地址见 vite 输出（通常 http://localhost:5173）"
  echo "    后端 API 文档: http://127.0.0.1:8765/docs"
  npm run dev
fi
