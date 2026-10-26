# Docker 部署（群晖 / 任意 Docker 主机）

本项目是 **Vue3 前端 + FastAPI(Python) 后端** 的 Web 应用（不是 Java，没有 jar）。
打包形态是一个 Docker 镜像：镜像内已构建好前端，并由后端在同一端口（`8765`）直接托管，
因此**只需暴露一个端口**，无需额外 Nginx 反代。

## 默认账号（首次启动自动创建）

| 账号 | 密码 | 权限 |
|------|------|------|
| `admin` | `admin123` | 管理员；**首次登录会强制要求改密码** |
| `guest` | `guest123` | 游客，仅可浏览，不能增删改（界面隐藏导出/写入口） |

> 数据（药材/经典方/针灸方/知识库/用户）首次启动会自动 seed，无需手动导入。

## 方式一：docker-compose（推荐，群晖 Container Manager 适用）

1. 把本项目（含 `Dockerfile`、`docker-compose.yml`）放到群晖共享文件夹，或 `git clone`。
2. 群晖 **Container Manager → 项目 → 创建** → 选择该目录的 `docker-compose.yml` → 构建并启动。
   或在有 docker 的机器上：
   ```bash
   docker compose up -d --build
   ```
3. 浏览器访问 `http://<群晖IP>:8765`，用 `admin / admin123` 登录（首次改密）。

## 方式二：直接运行（已构建好镜像时）

```bash
docker run -d --name tcm-doctor -p 8765:8765 \
  -e HOST=0.0.0.0 -e PORT=8765 \
  -e DATABASE_URL=sqlite:////data/tcm_doctor.db \
  -e SECRET_KEY=please-change-this-secret \
  -e ALLOW_GUEST_LOGIN=true \
  -v tcm_data:/data \
  --restart unless-stopped \
  tcm-doctor:latest
```

## 环境变量说明

| 变量 | 默认值/说明 |
|------|------|
| `HOST` / `PORT` | 容器内必须 `0.0.0.0`，端口 `8765` |
| `DATABASE_URL` | 建议指向挂载卷，如 `sqlite:////data/tcm_doctor.db` |
| `SECRET_KEY` | 请改为随机字符串 |
| `ALLOW_GUEST_LOGIN` | `true` 允许游客免密浏览 |
| `ENABLE_SEMANTIC_SEARCH` | `false`（关键词检索，轻量）；改 `true` 需镜像含 chromadb（见下） |
| `DEEPSEEK_API_KEY` | 填入后启用 AI 智能辨证；留空则 AI 功能不可用，但录入/浏览正常 |

## 数据持久化

数据库通过 `volumes: tcm_data:/data` 挂载，**容器/镜像重建不会丢失数据**。
备份即备份该卷（或系统设置里的「数据备份」导出 `.db`）。

## 启用语义检索（可选）

默认关键词检索即可用。若想用 ChromaDB 语义向量检索倪海厦医籍，需：
1. 将 `Dockerfile` 中 `pip install ... openai` 改为 `pip install -e ".[ai]"`（会引入 chromadb + sentence-transformers，镜像明显变大）。
2. 设置 `ENABLE_SEMANTIC_SEARCH=true`，首次启动会下载中文向量模型（需联网）。

## 自定义构建镜像

```bash
docker build -t tcm-doctor:latest .
docker save tcm-doctor:latest -o tcm-doctor-image.tar   # 导出，可拷到无网机器 docker load
```
