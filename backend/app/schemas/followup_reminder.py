"""随访提醒 Pydantic 模型"""
from datetime import datetime
from pydantic import BaseModel, Field


class FollowUpReminderCreate(BaseModel):
    """创建随访提醒（手动）"""
    patient_id: int
    due_date: str = Field(..., description="应回访日期 YYYY-MM-DD")
    note: str | None = Field(None, description="备注/复诊建议")
    source_type: str = Field("manual", description="来源: prescription/manual")


class FollowUpReminderUpdate(BaseModel):
    """更新随访提醒（标记完成/取消/改期）"""
    status: str | None = Field(None, description="pending/done/cancelled")
    due_date: str | None = None
    note: str | None = None


class FollowUpReminderResponse(BaseModel):
    """随访提醒响应"""
    id: int
    patient_id: int
    due_date: str
    source_type: str
    source_id: int | None
    status: str
    note: str | None
    created_at: datetime | None
    patient_name: str | None = None
    overdue: bool = False

    model_config = {"from_attributes": True}
