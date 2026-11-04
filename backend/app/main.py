"""FastAPI 主入口"""
import logging
import os
import re
import time
import json
from contextlib import asynccontextmanager
from datetime import datetime

logger = logging.getLogger(__name__)
from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings, build_display_version, resolve_env_path
from app.database import engine, Base, SessionLocal, get_db
from app.migrations import run_migrations
from app.models.user import User, AuthToken
from app.permissions import has_read, has_write, has_perm
from app.routers import patient, herb, prescription, knowledge, diagnosis, dictionaries, acupuncture
from app.routers import acupoint_formula
from app.routers import stats, backup, auth, followup_reminders, stock
from app.routers import system_log
from app.routers.auth import get_current_user, AUTH_COOKIE_NAME

WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def _purge_expired_logs() -> None:
    """按 LOG_RETENTION_DAYS 清理超期操作日志；0 表示关闭自动清理。失败不影响启动。"""
    days = int(getattr(settings, "log_retention_days", 0) or 0)
    if days <= 0:
        return
    from datetime import timedelta
    from app.models.log import OperationLog
    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=days)
        deleted = db.query(OperationLog).filter(OperationLog.created_at < cutoff).delete()
        db.commit()
        if deleted:
            logger.info(f"已自动清理 {deleted} 条超过 {days} 天的操作日志")
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(f"自动清理操作日志失败（不影响启动）: {e}")
    finally:
        db.close()


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

    # 启动时自动清理超期操作日志，避免日志表随使用无限增长（可用 LOG_RETENTION_DAYS 调整）
    _purge_expired_logs()

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


# ── 统一错误响应 ──
# 所有异常统一以 {"detail": ...} 形状返回，避免 500 泄漏堆栈，便于前端统一解析。
@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        try:
            from app.utils.operation_log import write_log
            tb = "".join(__import__("traceback").format_exception(type(exc), exc, exc.__traceback__))
            uid = getattr(request.state, "user_id", None)
            uname = getattr(request.state, "username", None)
            write_log(level="ERROR", user_id=uid, username=uname, action=request.url.path, endpoint=request.url.path,
                      method=request.method, status_code=exc.status_code, success=False,
                      message=str(exc.detail)[:500], error_detail=tb,
                      ip=request.client.host if request.client else "unknown")
        except Exception:
            pass
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("未处理的异常: %s %s", request.method, request.url.path)
    tb = "".join(__import__("traceback").format_exception(type(exc), exc, exc.__traceback__))
    try:
        from app.utils.operation_log import write_log
        uid = getattr(request.state, "user_id", None)
        uname = getattr(request.state, "username", None)
        write_log(level="ERROR", user_id=uid, username=uname, action=request.url.path,
                  endpoint=request.url.path, method=request.method, status_code=500,
                  success=False, message=str(exc)[:500], error_detail=tb,
                  ip=request.client.host if request.client else "unknown")
    except Exception:
        pass
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请联系管理员"})


def _extract_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(AUTH_COOKIE_NAME, "")


def _is_password_change_path(path: str) -> bool:
    """强制改密期间仍允许访问的接口（改密 / 登出 / 当前用户）"""
    return path in ("/api/v1/auth/password", "/api/v1/auth/logout", "/api/v1/auth/me")


@app.middleware("http")
async def require_admin_for_writes(request: Request, call_next):
    """统一鉴权中间件：
    - /api/v1 下除 /api/v1/auth 外，所有请求都必须携带有效 token（不再允许游客匿名访问）；
    - 按角色权限矩阵校验：写操作要求该业务域为 RW；管理域（备份/系统日志）仅管理员可读；
    - 账号停用后拒绝任何已发令牌；
    - 用户处于“必须改密”状态时，除改密/登出/当前用户外一律拒绝（403）；
    - 游客登录关闭后，任何遗留 guest 令牌一并拒绝。
    """
    path = request.url.path
    method = request.method
    is_write = method in WRITE_METHODS
    is_api = path.startswith("/api/v1")
    is_auth = path.startswith("/api/v1/auth") or path == "/api/v1/favicon"

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
            # 把已认证用户写入 request.state，供操作日志 / 异常处理器直接复用，
            # 既避免每次请求重复查库，又让 5xx ERROR 日志不再匿名（审计追责可用）
            request.state.user_id = user.id
            request.state.username = user.username
            client_ip = request.client.host if request.client else "unknown"
            # 游客登录已关闭：拒绝任何遗留 guest 令牌
            if not settings.allow_guest_login and user.username == "guest":
                return JSONResponse({"detail": "游客登录已禁用"}, status_code=403)
            # 强制改密：除改密/登出/当前用户信息外一律拦截
            # 注：账号停用(is_active)的校验统一交给 get_current_user（同时覆盖 /auth 域），
            # 此处不再重复，避免两处逻辑分叉。
            if user.must_change_password and not _is_password_change_path(path):
                return JSONResponse({"detail": "请先修改初始密码后再使用系统"}, status_code=403)
            # 按权限点校验：写操作要求该业务域的写权限点；管理域只读也需对应读权限点
            if is_write:
                if not has_write(path, user):
                    write_log(level="WARN", user_id=user.id, username=user.username,
                              action=path, endpoint=path, method=method, status_code=403,
                              success=False, message="越权访问被拒绝", ip=client_ip)
                    return JSONResponse({"detail": "权限不足，当前账号无权修改该数据"}, status_code=403)
            else:
                if not has_read(path, user):
                    write_log(level="WARN", user_id=user.id, username=user.username,
                              action=path, endpoint=path, method=method, status_code=403,
                              success=False, message="越权访问被拒绝", ip=client_ip)
                    return JSONResponse({"detail": "权限不足，当前账号无权访问该数据"}, status_code=403)
        finally:
            db.close()

    return await call_next(request)


# ── 操作日志自动采集中间件 ──
# 覆盖所有 /api/v1 请求：记录谁/何时/哪个接口/方法/状态码/耗时/IP；4xx 记 WARN 并捕获 detail，
# 5xx 记 ERROR；登录/登出/游客登录由 auth 路由显式审计(避免重复)，此处跳过。
from app.utils.operation_log import write_log

_ACTION_MAP = {
    "/api/v1/auth/password": "修改密码",
    "/api/v1/stock/batches/in": "入库",
    "/api/v1/stock/batches/out": "出库",
    "/api/v1/stock/batches/writeoff": "报损核销",
    "/api/v1/stock/purchases": "采购入库",
    "/api/v1/stock/adjust/bulk": "批量盘点校准",
    "/api/v1/stock/items": "物品管理",
    "/api/v1/stock/batches": "批次管理",
    "/api/v1/stock/transactions": "出入库流水",
    "/api/v1/stock/alerts": "库存预警",
    "/api/v1/prescriptions": "处方",
    "/api/v1/prescriptions/classic-formulas": "中药方库",
    "/api/v1/backup/export": "数据备份",
    "/api/v1/backup/import": "数据恢复",
    "/api/v1/backup/reset": "数据清空",
    "/api/v1/patients": "患者",
    "/api/v1/visits": "就诊记录",
    "/api/v1/herbs": "药材字典",
    "/api/v1/acupoints": "针灸穴位",
    "/api/v1/acupoint-formulas": "针灸方库",
    "/api/v1/dictionaries": "数据字典",
    "/api/v1/suppliers": "供应商",
    "/api/v1/config": "系统配置",
    "/api/v1/stock/overview": "库存总览",
    "/api/v1/stock/options": "库存选项",
    "/api/v1/stock/suppliers": "供应商",
    "/api/v1/stock/purchases": "采购入库",
    "/api/v1/stock/reports": "进销存报表",
    "/api/v1/stats/dashboard": "工作台统计",
    "/api/v1/stats": "统计报表",
    "/api/v1/system/logs": "操作日志",
    "/api/v1/diagnosis": "智能问诊",
    "/api/v1/book-library": "医籍文库",
    "/api/v1/knowledge": "知识检索",
}
_EXPLICIT_AUDIT_PATHS = {
    "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/guest",
}

# 方法 → 动作前缀，让「查看/新增/修改/删除」区分开，而不是全堆成路径名
_METHOD_VERB = {"GET": "查看", "POST": "新增", "PUT": "修改", "PATCH": "修改", "DELETE": "删除"}

# 路径段 → 中文名词：兜底时逐段翻译，避免出现「修改 items」这类半英文动作
_SEGMENT_CN = {
    "items": "物品", "batches": "批次", "suppliers": "供应商", "purchases": "采购单",
    "transactions": "流水", "alerts": "预警", "overview": "总览", "options": "选项",
    "reports": "报表", "summary": "汇总", "profit": "利润", "turnover": "周转",
    "tags": "标签", "meta": "元数据", "classic-formulas": "经典方", "formulas": "处方",
    "herbs": "药材", "acupoints": "穴位", "acupoint-formulas": "针灸方",
    "patients": "患者", "visits": "就诊", "dictionaries": "字典", "config": "配置",
    "stats": "统计", "dashboard": "工作台", "logs": "日志", "export": "导出",
    "import": "导入", "reset": "重置", "check": "盘点", "in": "入库", "out": "出库",
    "writeoff": "报损", "password": "密码", "settings": "设置", "backup": "备份",
    "diagnosis": "问诊", "knowledge": "知识", "csv": "CSV", "{id}": "详情",
}


def _is_cn(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def _resolve_action(method: str, path: str) -> str:
    """把请求解析成人类可读的中文动作名。

    优先命中 _ACTION_MAP（含前缀匹配，兼容 /stock/items/12 这类带 ID 的路径）；
    未命中时逐段翻译路径为中文，保证任何接口都不会出现裸英文动作名。
    """
    if path in _ACTION_MAP:
        return _ACTION_MAP[path]
    # 前缀匹配：取最长命中，避免 /stock/items 抢走 /stock/items/xxx 的具体语义
    best = None
    for key in _ACTION_MAP:
        if path.startswith(key + "/") and (best is None or len(key) > len(best)):
            best = key
    if best:
        # 命中前缀后，额外段（如 /items/45/xxx）继续翻译，不再拼英文
        rest = path[len(best):].strip("/")
        extra = [s for s in rest.split("/") if s]
        extra_cn = [s for s in (_SEGMENT_CN.get(re.sub(r"^\d+$", "{id}", p), "") for p in extra) if s]
        base = _ACTION_MAP[best]
        return f"{base}·{'·'.join(extra_cn)}" if extra_cn else base
    parts = [re.sub(r"^\d+$", "{id}", p) for p in path.split("/") if p not in ("", "api", "v1")]
    # 逐段翻译；未收录段原样保留，段间用 / 分隔，便于看出是待补充映射的接口
    cn = [_SEGMENT_CN.get(p, p) for p in parts]
    cn = [c for c in cn if c]
    verb = _METHOD_VERB.get(method, method)
    if not cn:
        return f"{verb}接口"
    # 末尾若是详情/单条路径，去掉它让动词更自然（如「查看 物品」而非「查看 物品 详情」）
    if cn[-1] == "详情":
        cn = cn[:-1]
    if not cn:
        return f"{verb}详情"
    # 中文段直接相连，未收录的英文段之间保留 /，避免拼成「unknownxyz」
    joined = cn[0]
    for prev, cur in zip(cn, cn[1:]):
        joined += cur if (_is_cn(prev) and _is_cn(cur)) else f"/{cur}"
    return f"{verb}{joined}"


def _deferred_log(token, ip, method, path, status_code, level, success, action, message, duration_ms, user_id=None, username=None, target=None):
    """响应返回后再写日志：若鉴权中间件已写入 request.state 则直接复用，否则按需用 token 反查；
    入库不占用接口响应时间。"""
    if user_id is None and token:
        db = SessionLocal()
        try:
            rec = db.query(AuthToken).filter(AuthToken.token == token).first()
            if rec and rec.expires_at >= datetime.now():
                u = db.query(User).filter(User.id == rec.user_id).first()
                if u:
                    user_id, username = u.id, u.username
        finally:
            db.close()
    write_log(
        level=level, user_id=user_id, username=username, action=action,
        endpoint=path, method=method, status_code=status_code, success=success,
        message=message, target=target, ip=ip, duration_ms=duration_ms,
    )


# 业务对象提取：仅取白名单字段，密码/证件等一律不记录。
# 这些字段覆盖了系统主要写操作（患者、药材、处方、出入库、穴位、方剂）的关键标识。
_TARGET_NAME_KEYS = (
    "name", "patient_name", "herb_name", "item_name", "formula_name", "username",
    "display_name", "supplier_name", "acupoint_name", "term_name", "title", "book_name",
    "real_name", "nickname", "disease_name", "label",
)
_TARGET_QTY_KEYS = ("quantity", "qty", "amount", "count", "dose", "days", "price", "unit_price")
_TARGET_EXCLUDE = {"password", "old_password", "new_password", "id_card", "phone", "token"}


def _extract_target(body: bytes | None) -> str | None:
    """从请求体提取业务对象摘要，如「三七 +50」；解析失败或无可识别字段则返回 None。

    只读白名单字段：即便请求体里含密码/身份证等，也不会进入日志，避免敏感信息落库。
    """
    if not body:
        return None
    try:
        data = json.loads(body)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    name = None
    for key in _TARGET_NAME_KEYS:
        if key in _TARGET_EXCLUDE:
            continue
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            name = val.strip()
            break
    # 嵌套对象（如中药方 composition.herbs）取首个药名，便于看出改的是哪一味
    if not name:
        for key in ("herbs", "items", "acupoints", "terms", "records"):
            arr = data.get(key)
            if isinstance(arr, list) and arr and isinstance(arr[0], dict):
                first = arr[0]
                for nk in ("herb", "herb_name", "name", "item_name", "acupoint_name"):
                    v = first.get(nk)
                    if isinstance(v, str) and v.strip():
                        name = f"{v.strip()} 等 {len(arr)} 项" if len(arr) > 1 else v.strip()
                        break
                if name:
                    break
    qty = None
    for key in _TARGET_QTY_KEYS:
        val = data.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            qty = val
            break
        if isinstance(val, str) and val.strip():
            qty = val.strip()
            break

    if not name and qty is None:
        # 无名称时退化：记录 id（修改/删除单条时通常有 id，能定位是哪条数据）
        rid = data.get("id")
        return f"#{rid}" if isinstance(rid, int) else None
    parts = []
    if name:
        parts.append(name)
    if qty is not None:
        parts.append(f"{'+' if len(parts) else ''}{qty}")
    return " ".join(parts) if parts else None


@app.middleware("http")
async def operation_log_middleware(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/v1") or path in _EXPLICIT_AUDIT_PATHS:
        return await call_next(request)
    # 日志自身的读操作（列表 / 导出）不再记录，避免 INFO 噪音刷屏
    if request.method == "GET" and path.startswith("/api/v1/system/logs"):
        return await call_next(request)

    method = request.method
    ip = request.client.host if request.client else "unknown"
    token = _extract_token(request)

    # 写请求才提取业务对象：只读 GET 的 body 无意义，且避免额外开销。
    # Starlette 的 request.body() 会把原始字节缓存在 request._body，下游路由再次读取时可复用，
    # 因此这里预读不会导致请求体丢失。
    target = None
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        try:
            raw = await request.body()
            target = _extract_target(raw)
        except Exception:
            target = None

    # 优先复用鉴权中间件写入的 request.state（已在鉴权时查过用户，避免每次请求重复查库）
    uid = getattr(request.state, "user_id", None)
    uname = getattr(request.state, "username", None)

    start = time.perf_counter()
    status_code = 500
    message = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        # 流式响应（如 AI 问诊 SSE）的 response.body 恒为 b""，无法解析 detail；跳过无效解析
        if status_code >= 400 and not isinstance(response, StreamingResponse):
            try:
                body = json.loads(response.body.decode())
                message = body.get("detail") if isinstance(body, dict) else None
            except Exception:
                pass
    except Exception as exc:  # 未被全局异常处理器捕获的兜底：记 ERROR 并保留堆栈，再原样抛出
        status_code = 500
        error_detail = "".join(
            __import__("traceback").format_exception(type(exc), exc, exc.__traceback__)
        )
        message = str(exc)
        duration = round((time.perf_counter() - start) * 1000, 1)
        # 未处理异常无 response 可挂后台任务，同步记录（罕见路径）
        if uid is None and token:
            db = SessionLocal()
            try:
                rec = db.query(AuthToken).filter(AuthToken.token == token).first()
                if rec and rec.expires_at >= datetime.now():
                    u = db.query(User).filter(User.id == rec.user_id).first()
                    if u:
                        uid, uname = u.id, u.username
            finally:
                db.close()
        write_log(
            level="ERROR", user_id=uid, username=uname, action=_ACTION_MAP.get(path, path),
            endpoint=path, method=method, status_code=500, success=False,
            message=message, error_detail=error_detail, ip=ip, duration_ms=duration,
        )
        raise

    duration = round((time.perf_counter() - start) * 1000, 1)
    # 鉴权中间件在内层执行后才写 request.state，故响应返回后回读一次，避免已登录用户被误判为匿名
    if uid is None:
        uid = getattr(request.state, "user_id", None)
        uname = getattr(request.state, "username", None)
    if status_code >= 500:
        level, success = "ERROR", False
    elif status_code == 401 and uid is None:
        # 匿名访问触发 401 多为未登录前端轮询配置，属噪音：降为 DEBUG，默认「关键操作」视图不可见
        level, success = "DEBUG", False
    elif status_code >= 400:
        level, success = "WARN", False
    else:
        level, success = "INFO", True
    action = _resolve_action(method, path)

    # 5xx 由全局异常处理器统一记 ERROR(含堆栈)，此处不再重复；
    # 其余按级别记录，但放到后台任务——响应先返回，日志随后写，对接口耗时零影响。
    if status_code < 500:
        response.background = BackgroundTask(
            _deferred_log, token, ip, method, path, status_code, level, success, action, message, duration, uid, uname, target
        )
    return response


# 注册路由
app.include_router(patient.router, prefix="/api/v1")
app.include_router(herb.router, prefix="/api/v1")
app.include_router(stock.router, prefix="/api/v1")
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
app.include_router(system_log.router, prefix="/api/v1")


def _clean_env_value(value: str) -> str:
    """剥离首尾空白及误粘的引号/反引号（如 `https://api.deepseek.com`），避免写坏 .env"""
    return value.strip().strip("`'\"").strip()


@app.get("/health", tags=["系统"])
def health_check():
    """健康检查 — Electron 启动时轮询此接口"""
    return {"status": "ok", "version": build_display_version()}


def _read_branding(db) -> dict:
    """读取诊所品牌信息：数据库优先，未落库时回退 .env（兼容旧配置）"""
    from app.models.branding import BrandingConfig
    row = db.query(BrandingConfig).first()
    if row:
        return {
            "clinic_name": row.clinic_name or "",
            "clinic_logo": row.clinic_logo or "",
        }
    return {
        "clinic_name": settings.clinic_name or "",
        "clinic_logo": settings.clinic_logo or "",
    }


def _save_branding(db, clinic_name: str | None, clinic_logo: str | None) -> None:
    """写入诊所品牌信息到数据库（None 表示该字段不修改；空串表示清空）"""
    from app.models.branding import BrandingConfig
    row = db.query(BrandingConfig).first()
    if not row:
        row = BrandingConfig()
        db.add(row)
    if clinic_name is not None:
        row.clinic_name = clinic_name
    if clinic_logo is not None:
        row.clinic_logo = clinic_logo
    db.commit()


@app.get("/api/v1/favicon", tags=["系统"])
def get_favicon(db: Session = Depends(get_db)):
    """浏览器标签图标（免鉴权）：新开标签页由 index.html 直接引用，返回诊所 Logo 原始字节。

    仅暴露 Logo 本身（诊所对外展示信息），不含任何配置或密钥；未设置 Logo 时返回 404，
    前端 link 自动回退默认 /favicon.svg。加短时缓存避免每次开页重复读取。
    """
    from fastapi.responses import Response
    import base64

    brand = _read_branding(db)
    data_url = brand["clinic_logo"]
    if not data_url.startswith("data:") or "," not in data_url:
        raise HTTPException(status_code=404, detail="未设置诊所 Logo")
    header, _, payload = data_url.partition(",")
    media_type = header[5:].split(";")[0] or "image/png"
    try:
        binary = base64.b64decode(payload)
    except Exception:
        raise HTTPException(status_code=404, detail="Logo 数据无法解析")
    return Response(
        content=binary,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/api/v1/config", tags=["系统"])
def get_config(current_user: User = Depends(get_current_user)):
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

    # 诊所品牌信息单独会话读取（上面的 db 已在 finally 关闭）
    brand_db = SessionLocal()
    try:
        brand = _read_branding(brand_db)
    finally:
        brand_db.close()

    return {
        "app_name": settings.app_name,
        "version": build_display_version(),
        "clinic_name": brand["clinic_name"],
        "doctor_name": settings.doctor_name,
        "clinic_logo": brand["clinic_logo"],
        "ui_theme": settings.ui_theme,
        "deepseek_configured": bool(settings.deepseek_api_key),
        "deepseek_model": settings.deepseek_model,
        "deepseek_base_url": settings.deepseek_base_url,
        "vision_configured": bool(settings.deepseek_vision_model),
        "deepseek_vision_model": settings.deepseek_vision_model,
        "deepseek_vision_base_url": settings.deepseek_vision_base_url,
        "vision_key_configured": bool(settings.deepseek_vision_api_key),
        # 数据库路径与各表条数属运维信息，仅 system:read 可见，避免向普通账号暴露服务器路径
        "db_path": db_path if has_perm(current_user, "system:read") else None,
        "counts": counts if has_perm(current_user, "system:read") else {},
    }


class ConfigUpdate(BaseModel):
    """系统配置更新请求体（通过 JSON 传输，避免密钥出现在 URL / 访问日志中）"""
    clinic_name: str | None = None
    doctor_name: str | None = None
    clinic_logo: str | None = None
    ui_theme: str | None = None
    deepseek_api_key: str | None = None
    deepseek_model: str | None = None
    deepseek_base_url: str | None = None
    deepseek_vision_model: str | None = None
    deepseek_vision_base_url: str | None = None
    deepseek_vision_api_key: str | None = None


@app.put("/api/v1/config", tags=["系统"])
def update_config(
    payload: ConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新系统配置 — 诊所品牌写入数据库，其余参数写入 .env 持久化（密钥不回显、文件权限 600）"""
    if not has_perm(current_user, "system:write"):
        return JSONResponse({"detail": "权限不足，仅 system:write 账号可修改系统配置"}, status_code=403)
    data = payload.model_dump(exclude_unset=True)
    clinic_name = data.get("clinic_name")
    doctor_name = data.get("doctor_name")
    clinic_logo = data.get("clinic_logo")
    ui_theme = data.get("ui_theme")
    deepseek_api_key = data.get("deepseek_api_key")
    deepseek_model = data.get("deepseek_model")
    deepseek_base_url = data.get("deepseek_base_url")
    deepseek_vision_model = data.get("deepseek_vision_model")
    deepseek_vision_base_url = data.get("deepseek_vision_base_url")
    deepseek_vision_api_key = data.get("deepseek_vision_api_key")

    # 复用 config 的 .env 解析（兼顾 PyInstaller frozen / DATA_DIR / 开发三场景），避免重复实现导致不一致
    env_path = resolve_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_lines: dict[str, str] = {}

    # 读取已有 .env
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_lines[k.strip()] = v.strip()

    # 诊所品牌（名称 / Logo）写入数据库：Logo 为 base64 大字段，写 .env 会导致整文件反复重写
    if clinic_name is not None or clinic_logo is not None:
        _save_branding(db, clinic_name, clinic_logo)
    if doctor_name is not None:
        settings.doctor_name = doctor_name
        env_lines["DOCTOR_NAME"] = doctor_name
    # 旧版本曾把诊所信息写进 .env，这里剔除，避免与数据库中的新值产生双源歧义
    env_lines.pop("CLINIC_NAME", None)
    # 界面风格：仅接受已知主题，非法值忽略（防止写入无效 CSS 选择器）
    if ui_theme is not None:
        allowed_themes = {"herbal", "ink", "vermilion", "jade"}
        if ui_theme in allowed_themes:
            settings.ui_theme = ui_theme
            env_lines["UI_THEME"] = ui_theme
    if deepseek_api_key:
        deepseek_api_key = _clean_env_value(deepseek_api_key)
        settings.deepseek_api_key = deepseek_api_key
        env_lines["DEEPSEEK_API_KEY"] = deepseek_api_key
    if deepseek_model:
        settings.deepseek_model = deepseek_model
        env_lines["DEEPSEEK_MODEL"] = deepseek_model
    if deepseek_base_url:
        deepseek_base_url = _clean_env_value(deepseek_base_url)
        settings.deepseek_base_url = deepseek_base_url
        env_lines["DEEPSEEK_BASE_URL"] = deepseek_base_url
    if deepseek_vision_model:
        settings.deepseek_vision_model = deepseek_vision_model
        env_lines["DEEPSEEK_VISION_MODEL"] = deepseek_vision_model
    if deepseek_vision_base_url:
        deepseek_vision_base_url = _clean_env_value(deepseek_vision_base_url)
        settings.deepseek_vision_base_url = deepseek_vision_base_url
        env_lines["DEEPSEEK_VISION_BASE_URL"] = deepseek_vision_base_url
    if deepseek_vision_api_key:
        deepseek_vision_api_key = _clean_env_value(deepseek_vision_api_key)
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