"""数据备份与恢复路由"""
import os
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app.config import settings
from app.routers.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/backup", tags=["数据管理"])


@router.get("/export", summary="导出数据备份（仅管理员）")
def export_backup(
    background: BackgroundTasks,
    current_user: "User" = Depends(get_current_user),
):
    """导出 SQLite 数据库文件（含患者隐私，仅管理员可操作）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可导出数据备份")
    db_path = settings.database_url.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        # 尝试相对路径
        db_path = os.path.join(os.getcwd(), "tcm_doctor.db")

    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="数据库文件不存在")

    # 复制到临时文件（避免锁定）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = os.path.join(os.getcwd(), f"tcm_backup_{timestamp}.db")
    shutil.copy2(db_path, temp_path)

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
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可导入数据恢复")
    if not file.filename.endswith(('.db', '.sqlite', '.sqlite3')):
        raise HTTPException(status_code=400, detail="请上传 .db 格式的备份文件")

    content = await file.read()

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
    """清空所有数据（保留表结构）— 显式要求管理员权限"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可清空数据")
    from app.models.herb import Herb, IncompatibilityRule, HerbInventory, InventoryTransaction
    from app.models.prescription import ClassicFormula, Prescription, PrescriptionItem
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.models.knowledge import KnowledgeEntry
    from app.models.conversation import Conversation, Message
    from app.models.inquiry import InquiryRecord
    from app.models.user import AuthToken

    # 按依赖顺序删除（含会话/问诊/令牌，避免重置后残留关联数据 M7）
    for model in [Message, Conversation, PrescriptionItem, Prescription, InventoryTransaction,
                  HerbInventory, IncompatibilityRule, InquiryRecord, AuthToken, Visit, Patient,
                  ClassicFormula, KnowledgeEntry, Herb]:
        db.query(model).delete()

    db.commit()

    # 重新导入种子数据（含字典与腧穴，M4）
    from app.seed import seed_all
    seed_all()

    return {"message": "数据已清空并重新初始化"}
