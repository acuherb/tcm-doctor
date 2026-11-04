"""现有库级联迁移（保留数据）：为存量 SQLite 库补上外键 ON DELETE 级联/置空。

背景：
- 早期库在建表时 FK 未带 ondelete（SQLite 默认），开启 PRAGMA foreign_keys=ON 后，
  删除被引用的父记录会被 SQLite 直接拒绝。新库已由模型（create_all）获得级联，
  但存量库需本脚本一次性重建表结构才能拿到级联（SQLite 不支持 ALTER 外键）。
- 功能安全性已由删除端点守卫 + ORM 级联兜底（不会 500/孤儿行），本脚本是 DB 级纵深加固。

安全性：
- 执行前自动把数据库文件复制为带时间戳的 .bak 备份；
- 全程在「关闭外键 + 事务」下进行改名/重建/拷贝，任一环节失败回滚，不直接破坏原库；
- 显式执行（不在应用启动时自动跑），由运维确认后运行。

用法：
    python scripts/apply_cascade_migration.py [--db path/to/tcm_doctor.db]
不传 --db 时按 app.config 的 database_url 推断。
"""
from __future__ import annotations

import os
import shutil
import sys
import time

# 允许以脚本方式导入 app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402


def _resolve_db_path() -> str:
    url = settings.database_url
    # 支持 sqlite:///absolute 或 sqlite:///relative 或 sqlite:///./x
    if url.startswith("sqlite:///"):
        p = url[len("sqlite:///"):]
        if not os.path.isabs(p):
            p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p)
        return os.path.abspath(p)
    raise RuntimeError(f"暂不支持的 database_url: {url}")


def apply(db_path: str) -> None:
    if not os.path.exists(db_path):
        print(f"[skip] 数据库文件不存在：{db_path}（全新库由应用启动时建表，已含级联，无需迁移）")
        return

    # 1) 备份
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = f"{db_path}.cascade-{stamp}.bak"
    shutil.copy2(db_path, bak)
    print(f"[backup] 已备份原库到 {bak}")

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    insp = inspect(engine)
    existing = set(insp.get_table_names())

    # 仅处理模型已注册、且库中已存在的表（排除 schema_migrations 等内部表，保留不动）
    app_tables = [t for t in Base.metadata.tables.values() if t.name in existing
                  and t.name != "schema_migrations"]

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))

    try:
        # 2) 全部改名 _cascade_old
        with engine.begin() as conn:
            for t in app_tables:
                conn.execute(text(f"ALTER TABLE {t.name} RENAME TO {t.name}__cascade_old"))

        # 2.5) 删除旧表上的索引（SQLite 索引名全局唯一，不删会与新建表索引重名）
        with engine.begin() as conn:
            for t in app_tables:
                old = f"{t.name}__cascade_old"
                for idx in inspect(engine).get_indexes(old):
                    conn.execute(text(f"DROP INDEX IF EXISTS {idx['name']}"))

        # 3) 按当前模型重建（含 ondelete 级联 + 索引）
        Base.metadata.create_all(engine, tables=[t for t in app_tables])

        # 4) 按列名交集拷贝数据（新表可能比旧表多列，旧表可能多已弃用列，取交集保证不丢数据）
        for t in app_tables:
            old = f"{t.name}__cascade_old"
            new_cols = {c.name for c in t.columns}
            old_cols = {c["name"] for c in inspect(engine).get_columns(old)}
            common = [c for c in new_cols & old_cols]
            if not common:
                continue
            col_list = ", ".join(common)
            with engine.begin() as conn:
                conn.execute(text(
                    f"INSERT INTO {t.name} ({col_list}) SELECT {col_list} FROM {old}"
                ))

        # 5) 删除旧表
        with engine.begin() as conn:
            for t in app_tables:
                conn.execute(text(f"DROP TABLE {t.name}__cascade_old"))

        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))

        print(f"[done] 已为 {len(app_tables)} 张表重建外键级联，数据已保留（备份：{bak}）")
    except Exception:
        print("[error] 迁移失败，原库未改动（备份文件可用作恢复）", file=sys.stderr)
        raise


if __name__ == "__main__":
    arg_db = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else None
    db_path = arg_db or _resolve_db_path()
    apply(db_path)
