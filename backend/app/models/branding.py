"""品牌配置模型 — 存放面向前端公开的诊所品牌信息（名称 / Logo）

从 .env 拆出的原因：Logo 是 base64 data URL（可达 100KB 量级），
写入 .env 会让每次保存配置都整文件重写，且 .env 本应只存可手改的部署参数。
本表数据不含密钥，可安全对外提供（浏览器标签图标接口免鉴权）。
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, func

from app.database import Base


class BrandingConfig(Base):
    __tablename__ = "branding_config"

    id = Column(Integer, primary_key=True, index=True)
    clinic_name = Column(String(100), nullable=True)
    clinic_logo = Column(Text, nullable=True)  # data URL，如 data:image/jpeg;base64,xxx
    updated_at = Column(DateTime, default=func.now, onupdate=func.now)