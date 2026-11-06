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
from sqlalchemy.orm.exc import StaleDataError
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
from app.utils.action_labels import resolve_action
from app.routers import patient, herb, prescription, knowledge, diagnosis, dictionaries, acupuncture
from app.routers import acupoint_formula
from app.routers import stats, backup, auth, followup_reminders, stock
from app.routers import system_log, templates
from app.routers import billing
from app.routers import registration
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

    # 自动备份：启动时先留一份在线快照，之后按间隔滚动保留；失败不影响应用启动
    try:
        from app import auto_backup
        auto_backup.start()
    except Exception as e:
        logger.warning(f"自动备份启动失败（不影响应用运行）: {e}")

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

    try:
        from app import auto_backup
        auto_backup.stop()
    except Exception:
        pass





app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="中医诊所问诊管理平台 API — 集成 DeepSeek 智能辨证",
    lifespan=lifespan,
)

# CORS — 开发服务器 + 后端自托管 + Electron 桌面版（file:// 页面的 Origin 为 "null"）。
# 反代到自定义域名时可用 CORS_EXTRA_ORIGINS（逗号分隔）追加，避免把白名单写死在代码里。
_extra_origins = [o.strip() for o in os.environ.get("CORS_EXTRA_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:8765",
                   "http://127.0.0.1:8765", "null", *_extra_origins],
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
            write_log(level="ERROR", user_id=uid, username=uname, action=resolve_action(request.method, request.url.path), endpoint=request.url.path,
                      method=request.method, status_code=exc.status_code, success=False,
                      message=str(exc.detail)[:500], error_detail=tb,
                      ip=request.client.host if request.client else "unknown")
        except Exception:
            pass
    # 主动抛出的 5xx HTTPException 同样不得把内部路径/异常文本回显给客户端（详情只进日志）
    detail = exc.detail if exc.status_code < 500 else "服务器内部错误，请联系管理员"
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(StaleDataError)
async def _stale_data_handler(request: Request, exc: StaleDataError):
    """乐观锁冲突：并发编辑同一记录（患者/就诊/处方/随访）时，对方已先提交。

    返回 409 让前端提示「数据已被他人修改，请刷新后重试」，而非 500。
    """
    logger.warning("乐观锁冲突(409): %s %s — %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=409,
        content={"detail": "该记录已被其他人修改，请刷新页面后重试（避免覆盖他人改动）"},
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("未处理的异常: %s %s", request.method, request.url.path)
    tb = "".join(__import__("traceback").format_exception(type(exc), exc, exc.__traceback__))
    try:
        from app.utils.operation_log import write_log
        uid = getattr(request.state, "user_id", None)
        uname = getattr(request.state, "username", None)
        write_log(level="ERROR", user_id=uid, username=uname, action=resolve_action(request.method, request.url.path),
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
    """强制改密期间仍允许访问的接口（改密 / 登出 / 当前用户 / 只读权限目录）。

    /auth/permissions 只是 RBAC 权限点的枚举元数据，不含任何患者数据，仍需有效令牌；
    放行它才能渲染改密页与权限选择列表，也不影响「未改密不得访问业务接口」的约束。
    """
    return path in (
        "/api/v1/auth/password", "/api/v1/auth/logout", "/api/v1/auth/me",
        "/api/v1/auth/permissions",
    )


# 无需令牌的公开接口。此前整段 /api/v1/auth/** 被豁免，导致未改密的默认超管可绕过
# 强制改密策略直接调用账号管理接口；改为只豁免登录/登出/游客/公共品牌配置。
PUBLIC_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/guest",
    "/api/v1/auth/logout",
    "/api/v1/favicon",
    "/api/v1/config/public",
}


@app.middleware("http")
async def require_admin_for_writes(request: Request, call_next):
    """统一鉴权中间件：
    - /api/v1 下除登录/登出/游客/公共品牌配置外，所有请求都必须携带有效 token；
    - 按角色权限矩阵校验：写操作要求该业务域为 RW；管理域（备份/系统日志）仅管理员可读；
    - 账号停用后拒绝任何已发令牌；
    - 用户处于“必须改密”状态时，除改密/登出/当前用户外一律拒绝（403）；
    - 游客登录关闭后，任何遗留 guest 令牌一并拒绝。
    """
    path = request.url.path
    method = request.method
    is_write = method in WRITE_METHODS
    is_api = path.startswith("/api/v1")
    # CORS 预检不带令牌，交给 CORSMiddleware 处理；否则跨域/桌面版请求会被本中间件直接 401
    is_preflight = method == "OPTIONS" and "access-control-request-method" in request.headers
    if is_api and is_preflight:
        return await call_next(request)

    if is_api and path not in PUBLIC_PATHS:
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
                              action=resolve_action(method, path), endpoint=path, method=method, status_code=403,
                              success=False, message="越权访问被拒绝", ip=client_ip)
                    return JSONResponse({"detail": "权限不足，当前账号无权修改该数据"}, status_code=403)
            else:
                if not has_read(path, user):
                    write_log(level="WARN", user_id=user.id, username=user.username,
                              action=resolve_action(method, path), endpoint=path, method=method, status_code=403,
                              success=False, message="越权访问被拒绝", ip=client_ip)
                    return JSONResponse({"detail": "权限不足，当前账号无权访问该数据"}, status_code=403)
        finally:
            db.close()

    return await call_next(request)


# ── 操作日志自动采集中间件 ──
# 覆盖所有 /api/v1 请求：记录谁/何时/哪个接口/方法/状态码/耗时/IP；4xx 记 WARN 并捕获 detail，
# 5xx 记 ERROR；登录/登出/游客登录由 auth 路由显式审计(避免重复)，此处跳过。
# 动作名统一由 action_labels.resolve_action() 生成中文；关键业务路由经
# operation_log.set_log_context() 补充动作/消息/对象/级别，仍由本中间件单点落库，
# 避免同一操作出现「显式审计」与「自动采集」两条重复日志。
from app.utils.operation_log import write_log

_EXPLICIT_AUDIT_PATHS = {
    "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/guest",
}


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
# 挂号收费模块的 body 常见形态：new_patient.name + registration_fee / paid / charge_no，
# 单独带出「给谁、多少钱、哪张单」，管理员不必展开详情就能看懂一条日志。
_TARGET_NAME_KEYS = (
    "name", "patient_name", "herb_name", "item_name", "formula_name", "username",
    "display_name", "supplier_name", "acupoint_name", "term_name", "title", "book_name",
    "real_name", "nickname", "disease_name", "label", "charge_no", "order_no",
)
_TARGET_MONEY_KEYS = (
    "registration_fee", "payable", "paid", "refund_amount", "total_price", "discount", "amount",
)
_TARGET_QTY_KEYS = ("quantity", "qty", "count", "dose", "days", "price", "unit_price")
_TARGET_ID_LABELS = {
    "patient_id": "患者", "visit_id": "就诊", "prescription_id": "处方",
    "charge_id": "收费单", "item_id": "物品",
}
_TARGET_EXCLUDE = {"password", "old_password", "new_password", "id_card", "phone", "token"}


def _extract_target(body: bytes | None) -> str | None:
    """从请求体提取业务对象摘要，如「张三 ¥20」；解析失败或无可识别字段则返回 None。

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
    # 挂号登记新建患者时姓名嵌在 new_patient.name，顶层没有 name 字段
    if not name:
        np = data.get("new_patient")
        if isinstance(np, dict) and isinstance(np.get("name"), str) and np["name"].strip():
            name = np["name"].strip()
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
    # 没有姓名时退化为业务单据编号，别让「对象」列空着
    if not name:
        for key, label in _TARGET_ID_LABELS.items():
            rid = data.get(key)
            if isinstance(rid, int):
                name = f"{label} #{rid}"
                break

    money = None
    for key in _TARGET_MONEY_KEYS:
        val = data.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            money = f"¥{val:g}"
            break
        if isinstance(val, str) and val.strip():
            money = f"¥{val.strip()}"
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

    if not name and money is None and qty is None:
        rid = data.get("id")
        return f"#{rid}" if isinstance(rid, int) else None
    parts = []
    if name:
        parts.append(name)
    if money:
        parts.append(money)
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
            level="ERROR", user_id=uid, username=uname, action=resolve_action(method, path),
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
    action = resolve_action(method, path)
    # 关键业务路由通过 set_log_context() 补充「谁对谁做了什么、为什么」；
    # 由中间件统一落库，字段(状态码/耗时/IP/操作人)保持完整且不会重复记两条。
    action = getattr(request.state, "log_action", None) or action
    level = getattr(request.state, "log_level", None) or level
    message = getattr(request.state, "log_message", None) or message
    target = getattr(request.state, "log_target", None) or target

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
# 模板导入导出 / 基础数据包一键安装（此前漏注册，导致相关接口全部 404）
app.include_router(templates.router, prefix="/api/v1")
# 收费管理（开方 -> 收费闭环）
app.include_router(billing.router, prefix="/api/v1")
# 挂号（前台分诊登记）：挂号 -> 就诊 -> 开方 -> 收费 闭环入口
app.include_router(registration.router, prefix="/api/v1")


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


@app.get("/api/v1/config/public", tags=["系统"])
def get_public_config():
    """登录页/未登录状态也可读取的公共配置：仅品牌信息，不含密钥、路径或统计。

    此前登录页请求需鉴权的 /config，401 被拦截器当成会话过期，导致 redirect 丢失、
    诊所名称与 Logo 永远显示默认值。
    """
    brand_db = SessionLocal()
    try:
        brand = _read_branding(brand_db)
    finally:
        brand_db.close()
    return {
        "clinic_name": brand["clinic_name"],
        "clinic_logo": brand["clinic_logo"],
        "ui_theme": settings.ui_theme,
    }


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
    # 临时文件同样含全部密钥，必须以 0600 创建（默认 umask 022 会给出 0644）
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for k, v in env_lines.items():
            f.write(f"{k}={v}\n")
    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    tmp_path.replace(env_path)

    # 限制 .env 权限，避免密钥被同机其它进程读取
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass

    return {"message": "配置已保存", "deepseek_configured": bool(settings.deepseek_api_key)}


# ---- 生产模式：直接托管已构建的前端静态文件 ----
# Docker 镜像把 frontend/dist 复制到 backend/static；Electron 打包版则通过
# TCM_STATIC_DIR 指向 resources/frontend/dist，由 Electron 主进程从 127.0.0.1:8765 同源加载，
# 避免 file:// 页面（Origin=null）触发 CORS 预检导致全部接口不可用。
# 开发模式不挂载，前端由 vite dev server 提供。前端使用 hash 路由，静态服务只需兜底返回 index.html。
_STATIC_DIR = Path(os.environ.get("TCM_STATIC_DIR") or (Path(__file__).parent.parent / "static"))
if (_STATIC_DIR / "index.html").exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")