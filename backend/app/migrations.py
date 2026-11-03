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
        # 幂等护栏：若上一轮迁移已部分落库（旧表仍在但 StockItem 已建），复用而非重复创建，
        # 避免「数据已提交、删表前崩溃」导致重启重跑时造出重复库存数据。
        existing_by_herb = {
            si.herb_id: si.id
            for si in db.query(StockItem).filter(StockItem.herb_id.isnot(None)).all()
        }

        # 1) 药材 -> 物品(类型=中药, 单位=g)
        herb_to_item: dict = {}
        new_herbs: list = []
        for h in db.query(Herb).all():
            if h.id in existing_by_herb:
                herb_to_item[h.id] = existing_by_herb[h.id]
                continue
            si = StockItem(
                item_type="中药", name=h.name, spec=h.grade, unit="g",
                sell_price=h.price, herb_id=h.id, min_stock=h.min_stock, is_active=True,
            )
            db.add(si)
            db.flush()
            herb_to_item[h.id] = si.id
            new_herbs.append(h.id)

        # 2) 批次 -> 批次（仅新建物品才建批次，复用物品不再重复造）
        inv_to_batch: dict = {}
        inv_rows = db.execute(_t(
            "SELECT id, herb_id, batch_number, quantity, unit_price, sale_price, "
            "purchase_date, expiry_date, supplier, min_stock, location, status "
            "FROM herb_inventory"
        )).fetchall()
        for r in inv_rows:
            (iid, hid, bn, qty, up, sp, pd, ed, sup, msk, loc, st) = r
            item_id = herb_to_item.get(hid)
            if item_id is None or hid not in new_herbs:
                continue
            # 注：批次只保留进价(unit_price)，售价以物品级 sell_price 为准，故不映射 sale_price
            sb = StockBatch(
                item_id=item_id, batch_number=bn, quantity=qty or 0, unit_price=up,
                purchase_date=pd, expiry_date=ed, supplier=sup,
                min_stock=msk, location=loc, status=st or "正常",
            )
            db.add(sb)
            db.flush()
            inv_to_batch[iid] = sb.id

        # 3) 处方批次引用重映射（覆盖写，重复执行无害）
        for old_id, new_id in inv_to_batch.items():
            db.execute(
                _t("UPDATE prescription_items SET inventory_id=:nid WHERE inventory_id=:oid"),
                {"nid": new_id, "oid": old_id},
            )

        # 4) 流水 -> 流水（仅新建物品才建流水）
        if new_herbs:
            txn_rows = db.execute(_t(
                "SELECT herb_id, transaction_type, quantity, before_quantity, after_quantity, "
                "reference_id, note, operator, created_at FROM inventory_transactions"
            )).fetchall()
            for r in txn_rows:
                (hid, ttype, qty, before, after, ref, note, operator, created) = r
                item_id = herb_to_item.get(hid)
                if item_id is None or hid not in new_herbs:
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
        # 数据迁移一次性提交
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # 5) 删除旧表（独立步骤：即便此处失败，重启后 existing_by_herb 护栏也会阻止重复造数）
    with engine.begin() as conn:
        conn.execute(_t("DROP TABLE IF EXISTS herb_inventory"))
        conn.execute(_t("DROP TABLE IF EXISTS inventory_transactions"))


@migration(
    "0011",
    "库存选项自定义颜色：为 stock_options 补 color 列，供类别/单位标签着色",
)
def m0011() -> None:
    _add_column("stock_options", "color", "VARCHAR(20)")


@migration(
    "0010",
    "库存选项种子：注入默认类别(中药/针灸针/艾灸耗材/外治耗材/其他)与单位(g/盒/支/根/贴/包)",
)
def m0010() -> None:
    from app.database import SessionLocal
    from app.models.stock import StockOption

    db = SessionLocal()
    try:
        if db.query(StockOption).count() == 0:
            defaults = [
                ("category", "中药"), ("category", "针灸针"), ("category", "艾灸耗材"),
                ("category", "外治耗材"), ("category", "其他"),
                ("unit", "g"), ("unit", "盒"), ("unit", "支"), ("unit", "根"), ("unit", "贴"), ("unit", "包"),
            ]
            for opt_type, name in defaults:
                db.add(StockOption(opt_type=opt_type, name=name, is_active=True))
            db.commit()
            logging.getLogger(__name__).info("已注入默认库存选项(类别/单位)")
    finally:
        db.close()


@migration(
    "0009",
    "兜底补齐进销存财务列(条码/供应商/金额)：防止 m0007 版本已登记但补列体未生效导致列缺失",
)
def m0009() -> None:
    """兜底迁移：确保库存三表的财务/条码/供应商列一定存在。

    背景：m0007 负责补这些列，但某些现网库在 m0007 版本号被登记时，
    实际执行的补列体与该版本号不符（迁移体曾被改写），导致列长期缺失、
    库存接口在运行时报 'no such column'。此处用全新版本号强制补齐，幂等。
    """
    _add_column("stock_items", "barcode", "VARCHAR(40)")
    _add_column("stock_items", "default_supplier_id", "INTEGER")
    _add_column("stock_batches", "barcode", "VARCHAR(40)")
    _add_column("stock_batches", "supplier_id", "INTEGER")
    _add_column("stock_transactions", "unit_cost", "NUMERIC(10,2)")
    _add_column("stock_transactions", "unit_price", "NUMERIC(10,2)")
    _add_column("stock_transactions", "cost_amount", "NUMERIC(14,2)")
    _add_column("stock_transactions", "revenue_amount", "NUMERIC(14,2)")

    from app.database import SessionLocal
    from app.models.stock import StockItem, StockBatch, StockTransaction

    db = SessionLocal()
    try:
        items = db.query(StockItem).filter(StockItem.barcode.is_(None)).all()
        for it in items:
            it.barcode = f"IT{it.id:08d}"
        batches = db.query(StockBatch).filter(StockBatch.barcode.is_(None)).all()
        for b in batches:
            b.barcode = f"BA{b.id:08d}"
        if items or batches:
            db.commit()

        txns = db.query(StockTransaction).filter(StockTransaction.cost_amount.is_(None)).all()
        if txns:
            item_sell = {
                i.id: float(i.sell_price)
                for i in db.query(StockItem).all() if i.sell_price is not None
            }
            batch_cost = {
                b.id: float(b.unit_price)
                for b in db.query(StockBatch).all() if b.unit_price is not None
            }
            for t in txns:
                uc = batch_cost.get(t.batch_id) if t.batch_id else None
                q = float(t.quantity)
                if t.transaction_type == "入库":
                    t.unit_cost = uc
                    t.cost_amount = (q * uc) if uc is not None else None
                    t.revenue_amount = 0.0
                elif t.transaction_type in ("出库", "损耗", "盘点", "调整"):
                    t.unit_cost = uc
                    t.cost_amount = (-q * uc) if uc is not None else None
                    if t.reference_type == "处方":
                        sell = item_sell.get(t.item_id)
                        t.unit_price = sell
                        t.revenue_amount = (q * sell) if sell is not None else 0.0
                    else:
                        t.revenue_amount = 0.0
            db.commit()
    finally:
        db.close()


@migration(
    "0007",
    "进销存财务化：为已有表补充金额列/条码列(suppliers/purchase_* 由 create_all 新建)，并回填流水成本收入与生成条码",
)
def m0007() -> None:
    # 已存在表补列（create_all 不会给存量表加列）；全新库这些列已由 create_all 创建，_add_column 会自动跳过
    _add_column("stock_items", "barcode", "VARCHAR(40)")
    _add_column("stock_items", "default_supplier_id", "INTEGER")
    _add_column("stock_batches", "barcode", "VARCHAR(40)")
    _add_column("stock_batches", "supplier_id", "INTEGER")
    _add_column("stock_transactions", "unit_cost", "NUMERIC(10,2)")
    _add_column("stock_transactions", "unit_price", "NUMERIC(10,2)")
    _add_column("stock_transactions", "cost_amount", "NUMERIC(14,2)")
    _add_column("stock_transactions", "revenue_amount", "NUMERIC(14,2)")

    from app.database import SessionLocal
    from app.models.stock import StockItem, StockBatch, StockTransaction

    db = SessionLocal()
    try:
        # 1) 为缺失条码的物品/批次生成条码（IT/BAnnnnnnnn）
        items = db.query(StockItem).filter(StockItem.barcode.is_(None)).all()
        for it in items:
            it.barcode = f"IT{it.id:08d}"
        batches = db.query(StockBatch).filter(StockBatch.barcode.is_(None)).all()
        for b in batches:
            b.barcode = f"BA{b.id:08d}"
        if items or batches:
            db.commit()

        # 2) 回填流水金额（仅 cost_amount 为空的历史行）
        txns = db.query(StockTransaction).filter(StockTransaction.cost_amount.is_(None)).all()
        if txns:
            item_sell = {
                i.id: float(i.sell_price)
                for i in db.query(StockItem).all() if i.sell_price is not None
            }
            batch_cost = {
                b.id: float(b.unit_price)
                for b in db.query(StockBatch).all() if b.unit_price is not None
            }
            for t in txns:
                uc = batch_cost.get(t.batch_id) if t.batch_id else None
                q = float(t.quantity)
                if t.transaction_type == "入库":
                    t.unit_cost = uc
                    t.cost_amount = (q * uc) if uc is not None else None
                    t.revenue_amount = 0.0
                elif t.transaction_type in ("出库", "损耗", "盘点", "调整"):
                    t.unit_cost = uc
                    t.cost_amount = (-q * uc) if uc is not None else None
                    if t.reference_type == "处方":
                        sell = item_sell.get(t.item_id)
                        t.unit_price = sell
                        t.revenue_amount = (q * sell) if sell is not None else 0.0
                    else:
                        t.revenue_amount = 0.0
            db.commit()
    finally:
        db.close()


@migration(
    "0012",
    "多用户权限：users 增加 role/is_active，并按 is_admin 回填管理员角色",
)
def m0012() -> None:
    """为 users 表补充角色与启用状态列。

    role:    admin / doctor / pharmacist / viewer，决定业务模块读写权限；
    is_active: 停用后拒绝登录，并使已发令牌失效。

    回填策略：老库中 is_admin=1 的账号回填为 admin（保持既有权限，避免升级后
    管理员突然失去写权限）；is_admin=0 的统一为 viewer。该迁移由 schema_migrations
    版本表保证仅执行一次，后续管理员手动调整角色不会被覆盖。
    """
    _add_column("users", "role", "VARCHAR(20) NOT NULL DEFAULT 'viewer'")
    _add_column("users", "is_active", "BOOLEAN NOT NULL DEFAULT 1")

    # 仅在列刚补齐后回填一次（版本机制保证本函数不会重复执行）
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET role='admin' WHERE is_admin=1"))


@migration(
    "0013",
    "操作日志增加 target 业务对象摘要列，便于直接看出改动落在哪条数据",
)
def m0013() -> None:
    _add_column("operation_logs", "target", "VARCHAR(300)")


@migration(
    "0014",
    "处方记录开方医师（doctor_id / doctor_name），打印按实际开方人署名",
)
def m0014() -> None:
    _add_column("prescriptions", "doctor_id", "INTEGER")
    _add_column("prescriptions", "doctor_name", "VARCHAR(50)")
    # 存量处方无法可靠还原真实开方人（历史上只存了审核人），保持为空；
    # 打印时回退到诊所唯一的医生账号，多处方暂不臆测，避免署名张冠李戴。


@migration(
    "0015",
    "权限表化：users 增加 permissions 列（逗号分隔权限点），并按角色回填默认权限集",
)
def m0015() -> None:
    """为 users 表补充 permissions 列。

    权限模型由「写死四类角色」升级为「权限点表」：每个账号可逐项勾选权限。
    回填策略：老库中 permissions 为空的账号，按其 role 套用 ROLE_DEFAULT_PERMSET，
    保证升级后各角色权限不变；is_admin=1 的账号视为拥有全部权限（由代码逻辑保证，无需存值）。
    """
    _add_column("users", "permissions", "TEXT NOT NULL DEFAULT ''")

    from app.database import SessionLocal
    from app.models.user import User
    from app.permissions import ROLE_DEFAULT_PERMSET

    db = SessionLocal()
    try:
        users = db.query(User).all()
        for u in users:
            if not u.permissions:
                u.permissions = ",".join(ROLE_DEFAULT_PERMSET.get(u.role, []))
        db.commit()
    finally:
        db.close()



@migration(
    "0016",
    "类别改名同步：库存选项里「中药」已被改成「中药材」时，回填 stock_items.item_type",
)
def m0016() -> None:
    """修复历史遗留的类别名不一致。

    背景：stock_items.item_type 与 stock_options.name 是两套独立存储，早期在
    「库存选项」里重命名类别（中药 -> 中药材）不会回溯更新已有物品，导致物品管理
    按新类别筛选时查不到任何数据，只能逐条手动改。
    此迁移把仍使用旧默认名「中药」的物品统一改为选项表中的现名；若选项表里已不存在
    「中药」且没有「中药材」，说明用户是自建类别，则不动数据。
    """
    from app.database import SessionLocal
    from app.models.stock import StockItem, StockOption

    db = SessionLocal()
    try:
        names = {
            o.name for o in db.query(StockOption).filter(StockOption.opt_type == "category").all()
        }
        if "中药" in names or "中药材" not in names:
            return
        legacy = db.query(StockItem).filter(StockItem.item_type == "中药").all()
        if not legacy:
            return
        for item in legacy:
            item.item_type = "中药材"
        db.commit()
        logging.getLogger(__name__).info("已将 %d 个物品类别由「中药」同步为「中药材」", len(legacy))
    finally:
        db.close()


def _sync_model_columns() -> None:
    """兜底补齐：按 ORM 模型把库里缺失的列补上（幂等）。

    背景：历史上部分列（如 prescription_items.inventory_id）仅通过 create_all
    建表时落地，没有对应的编号迁移；老库在升级时这些列永远不会被补上，
    导致查询时报 'no such column' 进而 500。此处遍历所有已注册模型，缺失即补。

    说明：补列一律按「可空」追加（SQLite 对已有数据的表无法安全追加 NOT NULL 列
    而不带默认值），非空约束交由 ORM 层在新写入时保证，不影响既有数据。
    """
    from app.models import (  # noqa: F401 触发全部模型注册到 Base.metadata
        DictionaryTerm, Patient, FollowUp, FollowUpReminder, Visit, InquiryRecord,
        Herb, StockItem, StockBatch, StockTransaction, StockOption, OperationLog,
        ClassicFormula, Prescription, PrescriptionItem, KnowledgeEntry,
        Conversation, Message, Acupoint, AcupointFormula, User, AuthToken,
    )
    from app.database import Base
    from sqlalchemy import inspect as _inspect

    insp = _inspect(engine)
    existing_tables = set(insp.get_table_names())
    log = logging.getLogger(__name__)
    for table in Base.metadata.tables.values():
        tname = table.name
        if tname not in existing_tables:
            continue
        existing_cols = {c["name"] for c in insp.get_columns(tname)}
        for col in table.columns:
            if col.name in existing_cols:
                continue
            if col.primary_key:
                # 已有数据的表无法安全追加主键列，跳过（极端情况）
                continue
            try:
                try:
                    col_type = col.type.compile(dialect=engine.dialect)
                except Exception:
                    col_type = "TEXT"
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {tname} ADD COLUMN {col.name} {col_type}"))
                log.info("sync_model_columns: 补齐列 %s.%s (%s)", tname, col.name, col_type)
            except Exception as e:  # 单列失败不影响其它列
                log.warning("sync_model_columns: 跳过 %s.%s —— %s", tname, col.name, e)


@migration(
    "0017",
    "诊所品牌入库：把 .env 中的 CLINIC_NAME / CLINIC_LOGO 迁移到 branding_config 表",
)
def m0017() -> None:
    """把 .env 里已有的诊所名称与 Logo 搬进数据库。

    背景：Logo 是 base64 data URL（可达 100KB+），放在 .env 里会导致每次保存配置都
    整文件重写，且 .env 本应只存可手改的部署参数。迁移后品牌信息统一由数据库管理，
    .env 中的旧键由保存接口自动剔除；本迁移仅在目标表为空时写入，避免覆盖用户已改的新值。
    """
    import logging
    from app.config import settings
    from app.database import SessionLocal
    from app.models.branding import BrandingConfig

    if not settings.clinic_name and not settings.clinic_logo:
        return
    db = SessionLocal()
    try:
        if db.query(BrandingConfig).first():
            return
        db.add(BrandingConfig(
            clinic_name=settings.clinic_name or "",
            clinic_logo=settings.clinic_logo or "",
        ))
        db.commit()
        logging.getLogger(__name__).info("已将 .env 中的诊所品牌信息迁移至 branding_config")
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

    # 先补齐缺失列：后续编号迁移（如 m0003 扫描 prescription_items）依赖目标列存在，
    # 否则会在迁移阶段就抛 'no such column' 导致整套迁移中断。
    _sync_model_columns()

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