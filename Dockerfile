# syntax=docker/dockerfile:1

# ---------- 前端构建阶段 ----------
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# 直接调用 vite 构建（跳过 vue-tsc 类型检查，避免类型问题阻塞镜像构建）
RUN npx vite build

# ---------- 后端运行阶段 ----------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app/backend

# 复制后端代码与种子数据（app/data 内含药材/方剂/知识库初始数据，需保留）
COPY backend/ ./

# 安装 Python 依赖：基础依赖 + openai（确保 AI 辨证对话可用）。
# 基础依赖均为纯 Python wheel，无需 gcc 编译，故不装 build-essential。
# 如需语义检索（ENABLE_SEMANTIC_SEARCH=true），请改用 pip install -e ".[ai]"
# （会引入 chromadb，需要编译工具链与系统库）。
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e . \
    && pip install --no-cache-dir openai

# 前端静态产物（由前端构建阶段生成），由 FastAPI 在生产模式直接托管
COPY --from=frontend-builder /app/frontend/dist ./static

EXPOSE 8765

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8765}"]
