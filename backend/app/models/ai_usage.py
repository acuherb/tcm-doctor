"""AI 用量日志模型 — 逐次记录 LLM 调用的 token 消耗与估算成本。

仅统计「本功能启用后」的调用：此前版本未保留 usage，无法回溯历史用量。
费用为按 .env 中可配置单价计算的估算值，最终以服务商账单为准。
"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AiUsageLog(Base):
    __tablename__ = "ai_usage_logs"
    __table_args__ = (
        Index("idx_ai_usage_created", "created_at"),
        Index("idx_ai_usage_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    user_id: Mapped[int | None] = mapped_column(Integer, comment="调用账号ID")
    username: Mapped[str | None] = mapped_column(String(50), comment="调用账号")
    scene: Mapped[str | None] = mapped_column(String(20), comment="场景: chat(对话问诊) / analyze(四诊辨证)")
    model: Mapped[str | None] = mapped_column(String(100), comment="实际调用的模型")
    is_vision: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否走 Vision 端点")

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, comment="输入 token")
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, comment="输出 token")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, comment="总 token")
    cache_hit_tokens: Mapped[int] = mapped_column(Integer, default=0, comment="输入中缓存命中 token")
    cache_miss_tokens: Mapped[int] = mapped_column(Integer, default=0, comment="输入中缓存未命中 token")

    cost: Mapped[float] = mapped_column(Float, default=0.0, comment="估算费用(元)，按记录时的单价计算")
    success: Mapped[bool] = mapped_column(Boolean, default=True, comment="调用是否成功")
    error: Mapped[str | None] = mapped_column(String(200), comment="失败原因摘要")
    duration_ms: Mapped[float | None] = mapped_column(Float, comment="上游耗时(毫秒)")
