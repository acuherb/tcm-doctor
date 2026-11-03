"""操作日志模型 — 统一记录登录/登出、API 访问与异常，便于开发排错与使用期问题发现"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float

from app.database import Base


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    level = Column(String(10), default="INFO", index=True)        # INFO / WARN / ERROR
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(50), nullable=True)
    action = Column(String(100), nullable=True)                   # 登录 / 登出 / 入库 / 发药 ...
    endpoint = Column(String(200), nullable=True)                 # /api/v1/stock/items
    method = Column(String(10), nullable=True)
    status_code = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    message = Column(String(500), nullable=True)                  # 业务消息 / 失败原因(detail)
    target = Column(String(300), nullable=True)                   # 业务对象摘要（如「三七 +50g」），便于直接看出本次改动落在哪条数据上
    error_detail = Column(Text, nullable=True)                    # 堆栈 / 明细(不记录敏感字段)
    ip = Column(String(50), nullable=True)
    duration_ms = Column(Float, nullable=True)