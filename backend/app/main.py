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
from app.models.user import User, AuthToken
from app.routers import patient, herb, prescription, knowledge, diagnosis, dictionaries, acupuncture
from app.routers import acupoint_formula
from app.routers import stats, backup, auth
from app.routers.auth import get_current_user

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
    # inquiry_records.visit_id（关联就诊，可为空，向后兼容旧记录）
    if "inquiry_records" in inspector.get_table_names():
        icols = {c["name"] for c in inspector.get_columns("inquiry_records")}
        if "visit_id" not in icols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE inquiry_records ADD COLUMN visit_id INTEGER"))

    # visits.parent_visit_id（复诊指向其初诊，构成一次完整就诊）
    if "visits" in inspector.get_table_names():
        vcols = {c["name"] for c in inspector.get_columns("visits")}
        if "parent_visit_id" not in vcols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE visits ADD COLUMN parent_visit_id INTEGER REFERENCES visits(id)"
                ))

    # herbs.price（参考单价，用于处方总价估算 M5）
    if "herbs" in inspector.get_table_names():
        hcols = {c["name"] for c in inspector.get_columns("herbs")}
        if "price" not in hcols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE herbs ADD COLUMN price NUMERIC(8,2)"))

    # visits.ai_analysis（AI 辅助辨证完整分析，供病历参考）
    if "visits" in inspector.get_table_names():
        vcols = {c["name"] for c in inspector.get_columns("visits")}
        if "ai_analysis" not in vcols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE visits ADD COLUMN ai_analysis TEXT"))
        if "pulse_term_ids" not in vcols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE visits ADD COLUMN pulse_term_ids TEXT"))
        # visits.visit_type（初诊/复诊；历史记录默认按初诊处理）
        if "visit_type" not in vcols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE visits ADD COLUMN visit_type VARCHAR(10) DEFAULT '初诊'"))
        # visits 影像资料（舌苔/面色照片 + 化验单列表）
        for col, ctype in (
            ("tongue_image", "TEXT"),
            ("face_image", "TEXT"),
            ("lab_report_images", "TEXT"),
        ):
            if col not in vcols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE visits ADD COLUMN {col} {ctype}"))

    # patients.tags（患者标签，如'不遵医瞩'）
    if "patients" in inspector.get_table_names():
        pcols = {c["name"] for c in inspector.get_columns("patients")}
        if "tags" not in pcols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE patients ADD COLUMN tags TEXT"))
        for col, ctype in (("height", "INTEGER"), ("weight", "REAL")):
            if col not in pcols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE patients ADD COLUMN {col} {ctype}"))

    # dictionary_terms.color（词条自定义颜色，用于标签着色）
    if "dictionary_terms" in inspector.get_table_names():
        dcols = {c["name"] for c in inspector.get_columns("dictionary_terms")}
        if "color" not in dcols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE dictionary_terms ADD COLUMN color VARCHAR(20)"))

    # herb_inventory.sale_price（售价，开方计价用；unit_price 视为进价）
    if "herb_inventory" in inspector.get_table_names():
        icols = {c["name"] for c in inspector.get_columns("herb_inventory")}
        if "sale_price" not in icols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE herb_inventory ADD COLUMN sale_price NUMERIC(8,2)"))

    # prescriptions.acupuncture_fee（针灸费用，计入处方总价）
    if "prescriptions" in inspector.get_table_names():
        pcols = {c["name"] for c in inspector.get_columns("prescriptions")}
        if "acupuncture_fee" not in pcols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN acupuncture_fee NUMERIC(8,2)"))

    # 其它表的新增列可在下方照此扩展

    # 默认患者标签词（字典 tag 类型）：存量库首次启动注入，管理员可在字典页继续自定义
    if "dictionary_terms" in inspector.get_table_names():
        try:
            from app.models.dictionaries import DictionaryTerm
            db = SessionLocal()
            try:
                if db.query(DictionaryTerm).filter(DictionaryTerm.term_type == "tag").count() == 0:
                    default_tags = {
                        "不遵医瞩": "#F56C6C",
                        "过敏体质": "#E6A23C",
                        "慢性病": "#409EFF",
                        "孕妇": "#9B59B6",
                        "儿童": "#67C23A",
                        "老年": "#909399",
                    }
                    for name, color in default_tags.items():
                        db.add(DictionaryTerm(term_type="tag", name=name, is_active=True, color=color))
                    db.commit()
                    logger.info("已注入默认患者标签词(字典 tag 类型)")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"注入默认患者标签词失败: {e}")


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
    return {"status": "ok", "version": build_display_version()}


@app.get("/api/v1/config", tags=["系统"])
def get_config():
    """获取系统配置"""
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