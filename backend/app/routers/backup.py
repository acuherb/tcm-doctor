"""数据备份与恢复路由"""
import logging
import os
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app.config import settings
from app.routers.auth import get_current_user
from app.models.user import User
from app.permissions import has_perm
from app.utils.operation_log import set_log_context
from app import auto_backup

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["数据管理"])

# 上传备份体积上限（防止大文件打满内存）
MAX_BACKUP_BYTES = 200 * 1024 * 1024
# 自动备份文件名白名单：只允许本模块生成的文件，杜绝路径穿越下载任意文件
AUTO_BACKUP_NAME_RE = re.compile(r"tcm_auto_[0-9]{8}_[0-9]{6}_[0-9]{6}_(auto|manual)\.db")


@router.get("/export", summary="导出数据备份（仅管理员）")
def export_backup(
    background: BackgroundTasks,
    current_user: "User" = Depends(get_current_user),
):
    """导出 SQLite 数据库文件（含患者隐私，仅管理员可操作）"""
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="仅管理员可导出数据备份")
    db_path = settings.database_url.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        # 尝试相对路径
        db_path = os.path.join(os.getcwd(), "tcm_doctor.db")

    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="数据库文件不存在")

    # 临时文件放数据库同目录：桌面版 CWD 是只读的安装目录，写 CWD 会直接 500
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = os.path.join(os.path.dirname(os.path.abspath(db_path)), f"tcm_backup_{timestamp}.db")
    shutil.copy2(db_path, temp_path)
    # 导出副本不携带会话令牌，避免备份文件外流即等于拿到管理员会话
    try:
        with sqlite3.connect(temp_path) as snap:
            snap.execute("DELETE FROM auth_tokens")
            snap.commit()
    except sqlite3.OperationalError:
        pass
    try:
        os.chmod(temp_path, 0o600)
    except OSError:
        pass

    # 启用备份加密时，导出文件一并加密（与自动备份一致），离线拷贝也受保护
    from app.services import backup_crypto
    if backup_crypto.encryption_enabled():
        p = Path(temp_path)
        p.write_bytes(backup_crypto.encrypt(p.read_bytes()))

    background.add_task(os.remove, temp_path)
    return FileResponse(
        path=temp_path,
        filename=f"tcm_backup_{datetime.now().strftime('%Y-%m-%d')}.db",
        media_type="application/octet-stream",
        background=background,
    )


@router.post("/import", summary="导入数据恢复")
async def import_backup(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """导入 SQLite 数据库文件恢复数据（校验合法性 + 原子替换 + 重载连接）"""
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="仅管理员可导入数据恢复")
    if not file.filename.endswith(('.db', '.sqlite', '.sqlite3')):
        raise HTTPException(status_code=400, detail="请上传 .db 格式的备份文件")

    content = await file.read()
    if len(content) > MAX_BACKUP_BYTES:
        raise HTTPException(status_code=413, detail="备份文件过大（上限 200MB）")

    # 0) 解密（若备份已加密）：明文备份（无魔数头）原样返回，向后兼容
    from app.services import backup_crypto
    try:
        content = backup_crypto.decrypt(content)
    except RuntimeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"备份解密失败：{e}。请确认已配置与备份时相同的 TCM_BACKUP_PASSPHRASE 后重试。",
        )

    # 1) 校验是否为合法的 SQLite 文件，避免误覆盖导致数据库损坏/数据丢失
    if not content.startswith(b"SQLite format 3\x00"):
        raise HTTPException(status_code=400, detail="文件不是合法的 SQLite 数据库备份")

    # 解析目标数据库路径（与导出逻辑保持一致）
    db_path = settings.database_url.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        db_path = os.path.join(os.getcwd(), "tcm_doctor.db")
    db_dir = os.path.dirname(os.path.abspath(db_path))

    # 2) 先备份当前数据库，导入异常时可手动回滚
    if os.path.exists(db_path):
        backup_path = db_path + f".bak_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        shutil.copy2(db_path, backup_path)

    # 3) 写入同目录临时文件后原子替换（os.replace 在同文件系统下为原子操作），
    #    避免直接覆盖正被应用打开/写入的活动库而造成损坏
    temp_path = os.path.join(db_dir, f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    with open(temp_path, "wb") as f:
        f.write(content)

    # 4) 校验 schema 版本，避免跨版本备份不兼容导致数据错乱
    try:
        with sqlite3.connect(temp_path) as imp:
            imp_ver = imp.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
    except Exception:
        os.remove(temp_path)
        raise HTTPException(status_code=400, detail="备份文件缺少 schema_migrations 版本信息，无法校验兼容性")
    with engine.connect() as conn:
        cur_ver = conn.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar()
    if imp_ver != cur_ver:
        os.remove(temp_path)
        raise HTTPException(
            status_code=400,
            detail=f"备份文件 schema 版本({imp_ver})与当前系统({cur_ver})不一致，拒绝导入以防数据不兼容",
        )

    try:
        os.replace(temp_path, db_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail="数据恢复失败：文件替换出错")

    # 4) 关闭现有连接池，使后续请求重新打开新数据库文件（无需重启进程）
    try:
        engine.dispose()
    except Exception:
        pass

    return {"message": "数据恢复成功，连接已自动重载，无需重启应用"}


@router.post("/reset", summary="清空数据")
def reset_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空所有数据（保留表结构）— 仅管理员可触发。
    清空后只重建框架基础（默认账号 + 数据字典 + 腧穴）；
    药材/医籍文库/中药方库/针灸方库等「用户内容库」清空后保持为空，由用户自行导入模板。"""
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="仅管理员可清空数据")
    from app.models.herb import Herb
    from app.models.stock import (
        StockItem, StockBatch, StockTransaction, Supplier, PurchaseOrder, PurchaseItem,
    )
    from app.models.prescription import (
        ClassicFormula, Prescription, PrescriptionItem, AcupointPrescription, PrescriptionInjection,
        AcupointFormula,
    )
    from app.models.acupuncture import Acupoint
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.models.knowledge import KnowledgeEntry
    from app.models.conversation import Conversation, Message
    from app.models.inquiry import InquiryRecord
    from app.models.followup import FollowUp
    from app.models.followup_reminder import FollowUpReminder
    from app.models.user import AuthToken
    from app.models.billing import Charge

    # 严格按「子表先于父表」顺序删除：启用 PRAGMA foreign_keys=ON 后，
    # 必须先清空子记录再删父记录，否则因缺级联而失败。覆盖会话/处方明细/随访/库存流水等全部子表。
    for model in [
        Charge,                                     # 收费单（引用处方/就诊/患者，最先清）
        Message, Conversation,                      # 会话/消息
        AcupointPrescription, PrescriptionInjection, PrescriptionItem, Prescription,  # 处方及其明细
        FollowUp, FollowUpReminder,                  # 随访/提醒（引用患者/就诊）
        InquiryRecord, Visit,                        # 问诊记录/就诊（引用患者）
        StockTransaction, StockBatch, PurchaseItem, PurchaseOrder, StockItem,        # 库存/采购（引用物品/供应商）
        AuthToken, Patient,                         # 令牌/患者（最后删父表）
        ClassicFormula, Herb, Supplier, KnowledgeEntry, AcupointFormula, Acupoint,  # 基础资料（被上述子表引用，置于其后）
    ]:
        db.query(model).delete()

    db.commit()

    # 重建框架基础：默认账号 + 游客 + 数据字典 + 腧穴。
    # 注意：不再重跑 seed_herbs / seed_classic_formulas / seed_knowledge，
    # 使药材、医籍文库、中药方库在清空后保持为空，由用户按自有模板自行导入。
    from app.seed import (
        seed_default_user, seed_guest_user, seed_dictionaries, seed_acupoints,
    )
    seed_default_user(db)
    seed_guest_user(db)
    seed_dictionaries(db)
    seed_acupoints(db)

    return {"message": "数据已清空并重新初始化（内容库需自行导入）"}


# ── 自动备份（在线快照 + 定时 + 保留份数 + 清单/下载）──

class AutoBackupConfig(BaseModel):
    enabled: bool | None = None
    interval_hours: int | None = Field(default=None, ge=1, le=720)
    keep: int | None = Field(default=None, ge=1, le=100)


@router.get("/auto/status", summary="自动备份配置与历史快照列表")
def auto_backup_status(current_user: User = Depends(get_current_user)):
    if not has_perm(current_user, "system:read"):
        raise HTTPException(status_code=403, detail="无权查看备份配置")
    items = auto_backup.list_backups()
    from app.services import backup_crypto
    return {
        "config": auto_backup.load_config(),
        "dir": str(auto_backup.backup_dir()),
        "last_backup": items[0]["created_at"] if items else None,
        "items": items,
        "encryption_enabled": backup_crypto.encryption_enabled(),
        "encryption_note": (
            "已启用备份加密（TCM_BACKUP_PASSPHRASE）：快照与导出均为密文，恢复需相同口令"
            if backup_crypto.encryption_enabled()
            else "未启用备份加密：备份为明文，建议通过 TCM_BACKUP_PASSPHRASE 环境变量设置强口令以加密患者隐私"
        ),
    }


@router.put("/auto/config", summary="更新自动备份配置")
def update_auto_backup_config(request: Request, payload: AutoBackupConfig, current_user: User = Depends(get_current_user)):
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="仅管理员可修改自动备份配置")
    cfg = auto_backup.save_config(payload.model_dump(exclude_unset=True))
    auto_backup.restart()
    set_log_context(request, action="修改自动备份配置", message=f"自动备份配置：{cfg}")
    return cfg


@router.post("/auto/run", summary="立即生成一份自动备份快照")
def run_auto_backup(request: Request, current_user: User = Depends(get_current_user)):
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="仅管理员可执行数据备份")
    try:
        info = auto_backup.run_cycle(force=True)
    except Exception as e:
        logger.warning(f"手动触发自动备份失败: {e}")
        # 详情只写日志，不把服务器绝对路径/异常文本回显给客户端
        raise HTTPException(status_code=500, detail="备份失败，请检查磁盘空间与数据目录权限")
    set_log_context(request, action="立即备份", message=f"生成快照 {info['name']}", target=info['name'])
    return {"message": "备份完成", **info}


@router.get("/auto/download/{name}", summary="下载指定自动备份快照")
def download_auto_backup(request: Request, name: str, current_user: User = Depends(get_current_user)):
    # 快照是整库（含患者数据），下载权限必须与手动导出一致；只读账号不应能取得全库副本
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="无权下载数据备份")
    if not AUTO_BACKUP_NAME_RE.fullmatch(name):
        raise HTTPException(status_code=400, detail="非法备份文件名")
    path = auto_backup.backup_dir() / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="备份文件不存在")
    set_log_context(request, action="下载自动备份", message=f"下载快照 {name}", target=name)
    return FileResponse(path=path, filename=name, media_type="application/octet-stream")