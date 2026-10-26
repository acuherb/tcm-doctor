"""应用配置管理"""
import sys
import os
from pydantic_settings import BaseSettings


def _get_env_file() -> str:
    """PyInstaller 打包后 .env 在 exe 同目录，开发时在项目根目录"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), '.env')
    return ".env"


class Settings(BaseSettings):
    """应用配置"""

    # 应用信息
    app_name: str = "中医诊所管理平台"
    app_version: str = "0.1.0"

    # 诊所信息（用于处方笺抬头、门诊病历落款等）
    clinic_name: str = ""
    doctor_name: str = ""

    # 数据库
    database_url: str = "sqlite:///./tcm_doctor.db"

    # DeepSeek API
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Vision API（图片识别，支持 OpenAI 兼容格式的 Vision 端点）
    deepseek_vision_model: str = ""  # 留空则不支持图片，如 Pro/moonshotai/Kimi-K2.6
    deepseek_vision_base_url: str = ""  # 留空则与 deepseek_base_url 相同
    deepseek_vision_api_key: str = ""  # 留空则复用 deepseek_api_key

    # 向量数据库
    chroma_persist_dir: str = "./chroma_data"
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    # 语义检索需安装 chromadb + sentence-transformers 并下载中文向量模型；
    # 关闭时系统使用关键词检索（默认，轻量、无需大模型依赖）
    enable_semantic_search: bool = False

    # 服务配置
    host: str = "127.0.0.1"
    port: int = 8765

    # 安全
    # 游客免密登录（仅浏览，写操作仍受限）；生产环境建议设为 False
    allow_guest_login: bool = False

    model_config = {
        "env_file": _get_env_file(),
        "env_file_encoding": "utf-8",
    }


settings = Settings()