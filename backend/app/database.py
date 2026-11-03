"""数据库连接与会话管理"""
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    echo=False,
    # SQLite 需要 check_same_thread=False；timeout=30 提供 busy timeout，
    # 多 worker / 并发写时降低「database is locked」失败概率（配合进程内 inventory_lock 使用）。
    connect_args={"check_same_thread": False, "timeout": 30},
)

# 库存变更（发药/出库）进程内互斥锁：SQLite 不支撑行级 FOR UPDATE，
# 故以进程内锁串行化库存的「读-改-写」，避免并发超卖；对支持行锁的数据库可叠加 with_for_update。
inventory_lock = threading.Lock()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
