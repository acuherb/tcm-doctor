"""FastAPI 主入口"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime

logger = logging.getLogger(__name__)
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models.user import User, AuthToken
from app.routers import patient, herb, prescription, knowledge, diagnosis, dictionaries, acupuncture
from app.routers import acupoint_formula
from app.routers import stats, backup, auth

WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时创建表 + 导入初始数据"""
    # 导入所有模型确保 Base.metadata 包含所有表
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    _run_light_migrations()

    # 首次启动时导入药材、配伍禁忌、经典方剂数据
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


def _run_light_migrations() -> None:
    """轻量迁移：为既有表补充新增列（SQLite 下 create_all 不会为已存在表加列）"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    # prescriptions.prescription_type
    if "prescriptions" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("prescriptions")}
        if "prescription_type" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE prescriptions ADD COLUMN prescription_type VARCHAR(20) NOT NULL DEFAULT '药方'"
                ))
        if "acupoint_formula_name" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN acupoint_formula_name VARCHAR(100)"))
        if "acupoint_technique" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN acupoint_technique VARCHAR(50)"))
        if "treatment_frequency" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN treatment_frequency VARCHAR(20)"))
        if "treatment_days" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN treatment_days INTEGER"))
        if "acupoint_formula_id" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN acupoint_formula_id INTEGER"))

    # users.must_change_password（升级已有库时默认为 1，即要求改密）
    if "users" in inspector.get_table_names():
        ucols = {c["name"] for c in inspector.get_columns("users")}
        if "must_change_password" not in ucols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT 1"))
    # 其它表的新增列可在下方照此扩展


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="中医诊所问诊管理平台 API — 集成 DeepSeek 智能辨证",
    lifespan=lifespan,
)

# CORS — 允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:8765", "http://127.0.0.1:8765", "file://"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


@app.middleware("http")
async def require_admin_for_writes(request: Request, call_next):
    """只读保护：所有写操作（增/删/改）必须由管理员发出；游客只能浏览"""
    path = request.url.path
    method = request.method
    is_write = method in WRITE_METHODS
    is_api = path.startswith("/api/v1")
    is_auth = path.startswith("/api/v1/auth")

    if is_api and is_write and not is_auth:
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
            if not user.is_admin:
                return JSONResponse({"detail": "游客账户仅可浏览，如需修改请用管理员登录"}, status_code=403)
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


@app.get("/health", tags=["系统"])
def health_check():
    """健康检查 — Electron 启动时轮询此接口"""
    return {"status": "ok", "version": settings.app_version}


@app.get("/api/v1/config", tags=["系统"])
def get_config():
    """获取系统配置"""
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "clinic_name": settings.clinic_name,
        "doctor_name": settings.doctor_name,
        "deepseek_configured": bool(settings.deepseek_api_key),
        "deepseek_model": settings.deepseek_model,
        "deepseek_base_url": settings.deepseek_base_url,
        "vision_configured": bool(settings.deepseek_vision_model),
        "deepseek_vision_model": settings.deepseek_vision_model,
        "deepseek_vision_base_url": settings.deepseek_vision_base_url,
        "vision_key_configured": bool(settings.deepseek_vision_api_key),
    }


@app.put("/api/v1/config", tags=["系统"])
def update_config(
    clinic_name: str | None = None,
    doctor_name: str | None = None,
    deepseek_api_key: str | None = None,
    deepseek_model: str | None = None,
    deepseek_base_url: str | None = None,
    deepseek_vision_model: str | None = None,
    deepseek_vision_base_url: str | None = None,
    deepseek_vision_api_key: str | None = None,
):
    """更新系统配置 — 同时写入 .env 文件持久化"""
    # .env 路径与 pydantic_settings 一致（项目根目录）
    env_path = Path(__file__).parent.parent / ".env"
    env_lines: dict[str, str] = {}

    # 读取已有 .env
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_lines[k.strip()] = v.strip()

    # 更新内存 + env（诊所信息允许清空）
    if clinic_name is not None:
        settings.clinic_name = clinic_name
        env_lines["CLINIC_NAME"] = clinic_name
    if doctor_name is not None:
        settings.doctor_name = doctor_name
        env_lines["DOCTOR_NAME"] = doctor_name

    # 更新内存 + env（忽略空字符串，防止误清已有配置）
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

    return {"message": "配置已保存", "deepseek_configured": bool(settings.deepseek_api_key)}