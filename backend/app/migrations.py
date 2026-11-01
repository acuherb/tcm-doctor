"""轻量版本化数据库迁移

替代原先散落在 main.py 中、逐表硬编码的 ALTER 语句。每次迁移带版本号，
应用版本记录到 `schema_migrations` 表；启动时可幂等追踪、缺失自动补齐。
新增表/列只需在此追加一条迁移，不再手动维护散落代码。

设计取舍：项目使用 SQLite，未引入 Alembic（其 batch 模式在 SQLite 下较繁琐）；
此处用“版本表 + 有序迁移列表”以最小成本获得版本追踪与可重放能力。
"""
from datetime import datetime
import json
import logging

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
    """若表已存在且缺该列，则 ALTER 补列（幂等）。

    说明：SQLite 不支持 ORM 形式的加列，受控的 ALTER ADD COLUMN 在 SQLite 下无法绕过；
    此处把它统一收口到版本化迁移里（每条调用都带版本号、写入 schema_migrations），
    替代此前散落在 scripts/ 下的游离裸 ALTER 脚本。
    """
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns(table)}
    if col in cols:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}"))


# ── m0004 药材多维标签迁移所需的助手（吸收自 scripts/migrate_herb_tags.py）──
FLAVOR_CHARS = set("辛甘酸苦咸淡涩")
MERIDIANS = {"心", "肝", "脾", "肺", "肾", "胃", "大肠", "小肠", "膀胱", "三焦", "胆", "心包"}


def _split_meridian(s) -> list:
    """旧字段 meridian_tropism（如‘归心、肺、膀胱经’）拆分为十二经数组。"""
    if not s:
        return []
    parts = [p.strip() for p in str(s).replace("、", ",").replace("，", ",").replace("/", ",").split(",") if p.strip()]
    out = []
    for p in parts:
        tok = p.strip()
        if tok.startswith("归"):
            tok = tok[1:]
        tok = tok.replace("经", "").replace("手", "").replace("足", "")
        tok = tok.replace("太阴", "").replace("太阳", "").replace("少阴", "").replace("少阳", "").replace("厥阴", "")
        tok = tok.replace("阳明", "").replace("脉", "").replace("维", "").replace("跷", "")
        tok = tok.strip()
        if tok in MERIDIANS and tok not in out:
            out.append(tok)
    return out


def _backfill_herb_tags() -> None:
    """遗留数据回填：仅当旧库 herbs 仍保留 flavor/meridian_tropism/category 源列时执行。

    当前 Herb 模型已无这些源列，故现网库通常为空操作；保留以兼容极老的库，
    且用源列存在性做硬守卫，避免对不存在的列做 SELECT 而报错。
    """
    insp = inspect(engine)
    if "herbs" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("herbs")}
    for needed in ("flavor", "meridian_tropism", "category"):
        if needed not in cols:
            return  # 非遗留库，跳过，杜绝 SELECT 报错
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, flavor, meridian_tropism, category, flavors, meridians, tags FROM herbs")
        ).fetchall()
        updated = 0
        for hid, flavor, meridian, category, flavors, meridians, tags in rows:
            upd: dict = {}
            if flavors is None and flavor:
                fl = [c for c in str(flavor) if c in FLAVOR_CHARS]
                if fl:
                    upd["flavors"] = json.dumps(fl, ensure_ascii=False)
            if meridians is None and meridian:
                md = _split_meridian(meridian)
                if md:
                    upd["meridians"] = json.dumps(md, ensure_ascii=False)
            if tags is None and category:
                upd["tags"] = json.dumps([category], ensure_ascii=False)
            if upd:
                set_clause = ", ".join(f"{k} = :{k}" for k in upd)
                upd["hid"] = hid
                conn.execute(text(f"UPDATE herbs SET {set_clause} WHERE id = :hid"), upd)
                updated += 1
        if updated:
            logging.getLogger(__name__).info(f"m0004 遗留药材标签回填：更新 {updated} 条")



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


@migration(
    "0004",
    "吸收游离脚本 scripts/migrate_herb_tags.py：药材库多维标签列(grade/meridians/directions/tags/contraindication)纳入版本化迁移",
)
def m0004() -> None:
    # 通过受控、版本追踪的 _add_column 补列，替代 scripts/ 下的游离裸 ALTER
    # （flavors 已由 0001 以 JSON 形式补齐，此处不再重复；
    #  contraindication 模型已声明，补齐旧库缺失；meridians/directions 等模型同步声明，保证 ORM 与库一致）
    _add_column("herbs", "grade", "TEXT")
    _add_column("herbs", "meridians", "TEXT")
    _add_column("herbs", "directions", "TEXT")
    _add_column("herbs", "tags", "TEXT")
    _add_column("herbs", "contraindication", "TEXT")
    # 遗留数据回填（仅极老库存在源列时生效，通常为空操作）
    _backfill_herb_tags()


@migration(
    "0005",
    "腧穴字典扩展列：出处/部位/主治/刺法（接入 acupoint_tag 字典驱动，支持三体系混排）",
)
def m0005() -> None:
    # 受控、版本追踪的补列；acupoints 模型同步声明，保证 ORM 与库一致
    _add_column("acupoints", "source", "VARCHAR(100)")       # 来源/出处（针灸大成/董氏奇穴/倪海厦·针灸/通用）
    _add_column("acupoints", "region", "VARCHAR(50)")        # 部位（头面/上肢/下肢…及董氏分区）
    _add_column("acupoints", "indications", "TEXT")           # 主治病症
    _add_column("acupoints", "needling_method", "TEXT")       # 针刺方法/操作要点


@migration(
    "0006",
    "库存抽象重构：新增 stock_items/stock_batches/stock_transactions，迁 herb_inventory/inventory_transactions 数据并删除旧表",
)
def m0006() -> None:
    from sqlalchemy import text as _t
    from datetime import datetime as _dt

    insp = inspect(engine)
    # 已迁移(旧表不存在)或全新库：跳过
    if "herb_inventory" not in insp.get_table_names():
        return
    from app.database import SessionLocal
    from app.models.herb import Herb
    from app.models.stock import StockItem, StockBatch, StockTransaction

    db = SessionLocal()
    try:
        # 1) 药材 -> 物品(类型=中药, 单位=g)
        herb_to_item: dict = {}
        for h in db.query(Herb).all():
            si = StockItem(
                item_type="中药", name=h.name, spec=h.grade, unit="g",
                sell_price=h.price, herb_id=h.id, min_stock=h.min_stock, is_active=True,
            )
            db.add(si)
            db.flush()
            herb_to_item[h.id] = si.id

        # 2) 批次 -> 批次
        inv_to_batch: dict = {}
        inv_rows = db.execute(_t(
            "SELECT id, herb_id, batch_number, quantity, unit_price, sale_price, "
            "purchase_date, expiry_date, supplier, min_stock, location, status "
            "FROM herb_inventory"
        )).fetchall()
        for r in inv_rows:
            (iid, hid, bn, qty, up, sp, pd, ed, sup, msk, loc, st) = r
            item_id = herb_to_item.get(hid)
            if item_id is None:
                continue
            sb = StockBatch(
                item_id=item_id, batch_number=bn, quantity=qty or 0, unit_price=up,
                sale_price=sp, purchase_date=pd, expiry_date=ed, supplier=sup,
                min_stock=msk, location=loc, status=st or "正常",
            )
            db.add(sb)
            db.flush()
            inv_to_batch[iid] = sb.id

        # 3) 处方批次引用重映射
        for old_id, new_id in inv_to_batch.items():
            db.execute(
                _t("UPDATE prescription_items SET inventory_id=:nid WHERE inventory_id=:oid"),
                {"nid": new_id, "oid": old_id},
            )

        # 4) 流水 -> 流水
        txn_rows = db.execute(_t(
            "SELECT herb_id, transaction_type, quantity, before_quantity, after_quantity, "
            "reference_id, note, operator, created_at FROM inventory_transactions"
        )).fetchall()
        for r in txn_rows:
            (hid, ttype, qty, before, after, ref, note, operator, created) = r
            item_id = herb_to_item.get(hid)
            if item_id is None:
                continue
            if ttype == "出库":
                ref_type = "处方" if ref else "手动"
            elif ttype == "入库":
                ref_type = "手动"
            else:
                ref_type = ttype  # 损耗
            if isinstance(created, str):
                try:
                    created = _dt.fromisoformat(created.replace(" ", "T"))
                except Exception:
                    created = None
            db.add(StockTransaction(
                item_id=item_id, batch_id=None, transaction_type=ttype,
                quantity=qty, before_quantity=before, after_quantity=after,
                reference_id=ref, reference_type=ref_type, operator=operator,
                note=note, created_at=created,
            ))
        db.commit()
    finally:
        db.close()

    # 5) 删除旧表
    with engine.begin() as conn:
        conn.execute(_t("DROP TABLE IF EXISTS herb_inventory"))
        conn.execute(_t("DROP TABLE IF EXISTS inventory_transactions"))


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
