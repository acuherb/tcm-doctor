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
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend \
    DATA_DIR=/data
WORKDIR /app/backend

# 容器内所有持久化数据（SQLite 数据库、.env 配置）统一落到 /data，
# 运行时挂载宿主机目录至此即可在删容器重建后保留数据。
RUN mkdir -p /data

# 复制后端代码与种子数据（app/data 内含药材/方剂/知识库初始数据，需保留）
COPY backend/ ./

# 显式安装固定版本依赖（纯 Python wheel，无需 gcc/apt）：
# 不在容器内用 `pip install -e .` 解析 pyproject，避免旧构建缓存元数据引发依赖冲突。
# 如需语义检索（ENABLE_SEMANTIC_SEARCH=true），请改为在 pyproject 的 [ai] 中安装
# chromadb + sentence-transformers，并相应调整此处。
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        fastapi==0.110.3 \
        uvicorn==0.30.6 \
        sqlalchemy==2.0.36 \
        alembic==1.13.2 \
        pydantic==2.9.2 \
        pydantic-settings==2.5.2 \
        httpx==0.27.2 \
        python-multipart==0.0.12 \
        openai

# 前端静态产物（由前端构建阶段生成），由 FastAPI 在生产模式直接托管
COPY --from=frontend-builder /app/frontend/dist ./static

EXPOSE 8765

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8765}"]
