"""FastAPI 主入口"""
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

logger = logging.getLogger(__name__)
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings, build_display_version
from app.database import engine, Base, SessionLocal
from app.migrations import run_migrations
from app.models.user import User, AuthToken
from app.routers import patient, herb, prescription, knowledge, diagnosis, dictionaries, acupuncture
from app.routers import acupoint_formula
from app.routers import stats, backup, auth, followup_reminders
from app.routers.auth import get_current_user

WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时创建表 + 导入初始数据"""
    # 导入所有模型确保 Base.metadata 包含所有表
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    run_migrations()

    # 首次启动时导入药材、经典方剂数据
    from app.seed import seed_all
    seed_all()

    # 语义检索索引（开启 enable_semantic_search 时自动重建；否则降级为关键词检索）
    if settings.enable_semantic_search:
        try:
            from app.services import vector_store
            if vector_store.bootstrap(settings.chroma_persist_dir, settings.embedding_model, True):
                db = SessionLocal()
                try:
                    n = vector_store.rebuild_from_knowledge_db(db)
                    logger.info(f"语义索引重建完成，共 {n} 条")
                finally:
                    db.close()
        except Exception as e:
            logger.warning(f"语义检索初始化失败，降级为关键词检索: {e}")

    yield





app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="中医诊所问诊管理平台 API — 集成 DeepSeek 智能辨证",
    lifespan=lifespan,
)

# CORS — 允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:8765", "http://127.0.0.1:8765"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _is_password_change_path(path: str) -> bool:
    """强制改密期间仍允许访问的接口（改密 / 登出 / 当前用户）"""
    return path in ("/api/v1/auth/password", "/api/v1/auth/logout", "/api/v1/auth/me")


@app.middleware("http")
async def require_admin_for_writes(request: Request, call_next):
    """统一鉴权中间件：
    - /api/v1 下除 /api/v1/auth 外，所有请求都必须携带有效 token（不再允许游客匿名访问）；
    - 写操作（POST/PUT/DELETE/PATCH）额外要求管理员权限；
    - 用户处于“必须改密”状态时，除改密/登出/当前用户外一律拒绝（403）；
    - 游客登录关闭后，任何遗留 guest 令牌一并拒绝。
    """
    path = request.url.path
    method = request.method
    is_write = method in WRITE_METHODS
    is_api = path.startswith("/api/v1")
    is_auth = path.startswith("/api/v1/auth")

    if is_api and not is_auth:
        token = _extract_token(request)
        if not token:
            return JSONResponse({"detail": "未登录"}, status_code=401)
        db = SessionLocal()
        try:
            record = db.query(AuthToken).filter(AuthToken.token == token).first()
            if not record or record.expires_at < datetime.now():
                return JSONResponse({"detail": "登录已过期，请重新登录"}, status_code=401)
            user = db.query(User).filter(User.id == record.user_id).first()
            if not user:
                return JSONResponse({"detail": "用户不存在"}, status_code=401)
            # 游客登录已关闭：拒绝任何遗留 guest 令牌
            if not settings.allow_guest_login and user.username == "guest":
                return JSONResponse({"detail": "游客登录已禁用"}, status_code=403)
            # 强制改密：除改密/登出/当前用户信息外一律拦截
            if user.must_change_password and not _is_password_change_path(path):
                return JSONResponse({"detail": "请先修改初始密码后再使用系统"}, status_code=403)
            # 写操作需管理员
            if is_write and not user.is_admin:
                return JSONResponse({"detail": "权限不足，仅管理员可修改数据"}, status_code=403)
        finally:
            db.close()

    return await call_next(request)

# 注册路由
app.include_router(patient.router, prefix="/api/v1")
app.include_router(herb.router, prefix="/api/v1")
app.include_router(prescription.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(diagnosis.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(backup.router, prefix="/api/v1")
app.include_router(dictionaries.router, prefix="/api/v1")
app.include_router(acupuncture.router, prefix="/api/v1")
app.include_router(acupoint_formula.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(followup_reminders.router, prefix="/api/v1")


@app.get("/health", tags=["系统"])
def health_check():
    """健康检查 — Electron 启动时轮询此接口"""
    return {"status": "ok", "version": build_display_version()}


@app.get("/api/v1/config", tags=["系统"])
def get_config():
    """获取系统配置"""
    # 数据库文件路径（解析为绝对路径，便于排查数据落盘位置）
    raw_db = str(engine.url.database) if engine.url and engine.url.database else ""
    db_path = os.path.abspath(raw_db) if raw_db else ""

    # 各表数据条数（运营概览）
    counts: dict = {}
    try:
        from app.models.patient import Patient
        from app.models.visit import Visit
        from app.models.followup import FollowUp
        from app.models.prescription import Prescription
        from app.models.inquiry import InquiryRecord

        db = SessionLocal()
        try:
            counts = {
                "patients": db.query(Patient).count(),
                "visits": db.query(Visit).count(),
                "followups": db.query(FollowUp).count(),
                "prescriptions": db.query(Prescription).count(),
                "inquiries": db.query(InquiryRecord).count(),
            }
        finally:
            db.close()
    except Exception as e:  # 统计失败不应影响配置下发
        logger.warning(f"统计系统数据条数失败: {e}")

    return {
        "app_name": settings.app_name,
        "version": build_display_version(),
        "clinic_name": settings.clinic_name,
        "doctor_name": settings.doctor_name,
        "clinic_logo": settings.clinic_logo,
        "deepseek_configured": bool(settings.deepseek_api_key),
        "deepseek_model": settings.deepseek_model,
        "deepseek_base_url": settings.deepseek_base_url,
        "vision_configured": bool(settings.deepseek_vision_model),
        "deepseek_vision_model": settings.deepseek_vision_model,
        "deepseek_vision_base_url": settings.deepseek_vision_base_url,
        "vision_key_configured": bool(settings.deepseek_vision_api_key),
        "db_path": db_path,
        "counts": counts,
    }


class ConfigUpdate(BaseModel):
    """系统配置更新请求体（通过 JSON 传输，避免密钥出现在 URL / 访问日志中）"""
    clinic_name: str | None = None
    doctor_name: str | None = None
    clinic_logo: str | None = None
    deepseek_api_key: str | None = None
    deepseek_model: str | None = None
    deepseek_base_url: str | None = None
    deepseek_vision_model: str | None = None
    deepseek_vision_base_url: str | None = None
    deepseek_vision_api_key: str | None = None


@app.put("/api/v1/config", tags=["系统"])
def update_config(payload: ConfigUpdate, current_user: User = Depends(get_current_user)):
    """更新系统配置 — 同时写入 .env 文件持久化（密钥不回显、文件权限 600）"""
    if not current_user.is_admin:
        return JSONResponse({"detail": "仅管理员可修改系统配置"}, status_code=403)
    data = payload.model_dump(exclude_unset=True)
    clinic_name = data.get("clinic_name")
    doctor_name = data.get("doctor_name")
    clinic_logo = data.get("clinic_logo")
    deepseek_api_key = data.get("deepseek_api_key")
    deepseek_model = data.get("deepseek_model")
    deepseek_base_url = data.get("deepseek_base_url")
    deepseek_vision_model = data.get("deepseek_vision_model")
    deepseek_vision_base_url = data.get("deepseek_vision_base_url")
    deepseek_vision_api_key = data.get("deepseek_vision_api_key")

    # .env 路径：容器内优先放 DATA_DIR（与 pydantic_settings 一致），否则项目根目录
    data_dir = os.environ.get("DATA_DIR", "")
    if data_dir:
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        env_path = Path(data_dir) / ".env"
    else:
        env_path = Path(__file__).parent.parent / ".env"
    env_lines: dict[str, str] = {}

    # 读取已有 .env
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_lines[k.strip()] = v.strip()

    # 更新内存 + env（诊所信息允许清空；密钥忽略空字符串，防止误清已有配置）
    if clinic_name is not None:
        settings.clinic_name = clinic_name
        env_lines["CLINIC_NAME"] = clinic_name
    if doctor_name is not None:
        settings.doctor_name = doctor_name
        env_lines["DOCTOR_NAME"] = doctor_name
    # 诊所 logo 允许清空：空字符串也写入
    if clinic_logo is not None:
        settings.clinic_logo = clinic_logo
        env_lines["CLINIC_LOGO"] = clinic_logo
    if deepseek_api_key:
        settings.deepseek_api_key = deepseek_api_key
        env_lines["DEEPSEEK_API_KEY"] = deepseek_api_key
    if deepseek_model:
        settings.deepseek_model = deepseek_model
        env_lines["DEEPSEEK_MODEL"] = deepseek_model
    if deepseek_base_url:
        settings.deepseek_base_url = deepseek_base_url
        env_lines["DEEPSEEK_BASE_URL"] = deepseek_base_url
    if deepseek_vision_model:
        settings.deepseek_vision_model = deepseek_vision_model
        env_lines["DEEPSEEK_VISION_MODEL"] = deepseek_vision_model
    if deepseek_vision_base_url:
        settings.deepseek_vision_base_url = deepseek_vision_base_url
        env_lines["DEEPSEEK_VISION_BASE_URL"] = deepseek_vision_base_url
    if deepseek_vision_api_key:
        settings.deepseek_vision_api_key = deepseek_vision_api_key
        env_lines["DEEPSEEK_VISION_API_KEY"] = deepseek_vision_api_key

    # 写回 .env（原子写入：先写临时文件再替换，避免 reload 期间读到空文件）
    tmp_path = env_path.with_suffix(".env.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        for k, v in env_lines.items():
            f.write(f"{k}={v}\n")
    tmp_path.replace(env_path)

    # 限制 .env 权限，避免密钥被同机其它进程读取
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass

    return {"message": "配置已保存", "deepseek_configured": bool(settings.deepseek_api_key)}


# ---- 生产模式：直接托管已构建的前端静态文件 ----
# 仅当 backend/static 目录存在时挂载（由 Docker 镜像从 frontend/dist 复制而来）；
# 开发模式不挂载，前端由 vite dev server 提供。前端使用 hash 路由，静态服务只需兜底返回 index.html。
_STATIC_DIR = Path(__file__).parent.parent / "static"
if _STATIC_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")