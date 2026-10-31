"""轻量版本化数据库迁移

替代原先散落在 main.py 中、逐表硬编码的 ALTER 语句。每次迁移带版本号，
应用版本记录到 `schema_migrations` 表；启动时可幂等追踪、缺失自动补齐。
新增表/列只需在此追加一条迁移，不再手动维护散落代码。

设计取舍：项目使用 SQLite，未引入 Alembic（其 batch 模式在 SQLite 下较繁琐）；
此处用“版本表 + 有序迁移列表”以最小成本获得版本追踪与可重放能力。
"""
from datetime import datetime

from sqlalchemy import inspect, text

from app.database import engine


MIGRATIONS: list = []


def migration(version: str, description: str):
    """装饰器：注册一条带版本号与说明的迁移"""

    def deco(fn):
        fn._version = version
        fn._description = description
        MIGRATIONS.append(fn)
        return fn

    return deco


def _add_column(table: str, col: str, ctype: str) -> None:
    """若表已存在且缺该列，则 ALTER 补列（幂等）"""
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns(table)}
    if col in cols:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}"))


@migration("0001", "补齐历史库缺失表列（药材/患者/就诊/处方/用户/字典/库存等）")
def m0001() -> None:
    _add_column("prescriptions", "prescription_type", "VARCHAR(20) NOT NULL DEFAULT '药方'")
    _add_column("prescriptions", "acupoint_formula_name", "VARCHAR(100)")
    _add_column("prescriptions", "acupoint_technique", "VARCHAR(50)")
    _add_column("prescriptions", "treatment_frequency", "VARCHAR(20)")
    _add_column("prescriptions", "treatment_days", "INTEGER")
    _add_column("prescriptions", "acupoint_formula_id", "INTEGER")
    _add_column("prescriptions", "acupuncture_fee", "NUMERIC(8,2)")
    _add_column("users", "must_change_password", "BOOLEAN NOT NULL DEFAULT 1")
    _add_column("inquiry_records", "visit_id", "INTEGER")
    _add_column("visits", "parent_visit_id", "INTEGER REFERENCES visits(id)")
    _add_column("visits", "ai_analysis", "TEXT")
    _add_column("visits", "pulse_term_ids", "TEXT")
    _add_column("visits", "visit_type", "VARCHAR(10) DEFAULT '初诊'")
    _add_column("visits", "tongue_image", "TEXT")
    _add_column("visits", "face_image", "TEXT")
    _add_column("visits", "lab_report_images", "TEXT")
    _add_column("herbs", "price", "NUMERIC(8,2)")
    _add_column("herbs", "aliases", "JSON")
    _add_column("herbs", "flavors", "JSON")
    _add_column("patients", "tags", "TEXT")
    _add_column("patients", "height", "INTEGER")
    _add_column("patients", "weight", "REAL")
    _add_column("dictionary_terms", "color", "VARCHAR(20)")
    _add_column("herb_inventory", "sale_price", "NUMERIC(8,2)")


@migration("0002", "注入默认患者标签词（字典 tag 类型）")
def m0002() -> None:
    import logging

    from app.database import SessionLocal
    from app.models.dictionaries import DictionaryTerm

    db = SessionLocal()
    try:
        if db.query(DictionaryTerm).filter(DictionaryTerm.term_type == "tag").count() == 0:
            default_tags = {
                "不遵医瞩": "#F56C6C",
                "过敏体质": "#E6A23C",
                "慢性病": "#409EFF",
                "孕妇": "#9B59B6",
                "儿童": "#67C23A",
                "老年": "#909399",
            }
            for name, color in default_tags.items():
                db.add(DictionaryTerm(term_type="tag", name=name, is_active=True, color=color))
            db.commit()
            logging.getLogger(__name__).info("已注入默认患者标签词(字典 tag 类型)")
    finally:
        db.close()


@migration("0003", "数据清洗：处方明细剂量超限提醒去重")
def m0003() -> None:
    import logging

    from app.database import SessionLocal
    from app.models.prescription import PrescriptionItem

    db = SessionLocal()
    try:
        items = db.query(PrescriptionItem).filter(
            PrescriptionItem.note.like("%剂量超限提醒%")
        ).all()
        changed = 0
        for it in items:
            if not it.note:
                continue
            notes = [s.strip() for s in it.note.split("；")]
            seen = set()
            for n in notes:
                if n.startswith("⚠️ 剂量超限提醒"):
                    seen.add(n)
            if len(seen) > 1:
                keep_reminder = sorted(seen, key=len, reverse=True)[0]
                others = [n for n in notes if n and not n.startswith("⚠️ 剂量超限提醒")]
                it.note = "；".join([keep_reminder] + others) if others else keep_reminder
                changed += 1
        if changed:
            db.commit()
            logging.getLogger(__name__).info(f"已清洗 {changed} 条重复的剂量超限提醒")
    finally:
        db.close()


def run_migrations() -> None:
    """应用所有未执行过的迁移（幂等：以 schema_migrations 表记录为准）"""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  version VARCHAR(50) PRIMARY KEY,"
            "  description TEXT,"
            "  applied_at DATETIME"
            ")"
        ))
        applied = {
            row[0]
            for row in conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
        }

    for fn in sorted(MIGRATIONS, key=lambda f: f._version):
        if fn._version in applied:
            continue
        fn()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO schema_migrations(version, description, applied_at) "
                    "VALUES (:v, :d, :t)"
                ),
                {"v": fn._version, "d": fn._description, "t": datetime.now()},
            )
