#!/usr/bin/env bash
# 构建并导出 tcm-doctor 镜像为 tar，供群晖 Container Manager 手动导入。
# 用法: ./build.sh
set -euo pipefail
cd "$(dirname "$0")"

IMAGE=tcm-doctor
TAG=latest

echo "== 构建镜像 $IMAGE:$TAG =="
docker build -t "$IMAGE:$TAG" .

echo "== 导出 tar =="
docker save "$IMAGE:$TAG" -o tcm-doctor-image.tar

ls -lh tcm-doctor-image.tar
echo "完成。把 tcm-doctor-image.tar 拷到群晖导入即可。"
echo "注意：创建容器时务必挂载 本地目录 -> /data（端口 8765->8765），否则数据不持久化。"
