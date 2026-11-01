"""为 herbs 表增加 min_stock 列（药材级最低库存预警阈值）。幂等。

已有的 tcm_doctor.db 不会因 SQLAlchemy create_all 自动加列，故需本脚本；
新环境若直接建库则模型已含该列，本脚本也会安全跳过。
"""
import os
import sqlite3

DB = os.path.join(os.path.dirname(__file__), "tcm_doctor.db")


def main():
    if not os.path.exists(DB):
        print("数据库不存在，跳过（将由 init_db 在建库时创建新列）。")
        return
    conn = sqlite3.connect(DB)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(herbs)")}
    if "min_stock" not in existing:
        conn.execute("ALTER TABLE herbs ADD COLUMN min_stock NUMERIC(10,2)")
        print("已添加列: min_stock")
    else:
        print("列已存在，跳过: min_stock")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
