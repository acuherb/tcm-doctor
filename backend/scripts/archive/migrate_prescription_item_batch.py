"""为 prescription_items 增加 inventory_id 与 price 两列（开方按批次取价/出货）。

幂等：列已存在则跳过。已有的 tcm_doctor.db 不会因 SQLAlchemy create_all 自动加列，
故需本脚本；新环境若直接建库则模型已含这两列，本脚本也会安全跳过。
"""
import os
import sqlite3

DB = os.path.join(os.path.dirname(__file__), "tcm_doctor.db")


def main():
    if not os.path.exists(DB):
        print("数据库不存在，跳过（将由 init_db 在建库时创建新列）。")
        return
    conn = sqlite3.connect(DB)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(prescription_items)")}
    for col, typ in [("inventory_id", "INTEGER"), ("price", "NUMERIC(8,2)")]:
        if col not in existing:
            conn.execute(f"ALTER TABLE prescription_items ADD COLUMN {col} {typ}")
            print("已添加列:", col)
        else:
            print("列已存在，跳过:", col)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
