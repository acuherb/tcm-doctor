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
            if col.name == "version":
                # 乐观锁版本列由专用迁移(0018)以 NOT NULL DEFAULT 1 补齐；
                # 此处若建成可空列，会因 version_id_col 的 `version = NULL` 判定导致所有 UPDATE 失效。
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


@migration(
    "0018",
    "索引与健壮性：补齐高频查询索引，并为患者/就诊/处方/随访加乐观锁 version 列",
)
def m0018() -> None:
    """存量库补齐：

    1) 高频过滤/排序列的索引（新库已由模型 __table_args__ 经 create_all 建好，此处幂等补齐）：
       - visits(patient_id, visit_date)  病历聚合按患者+日期排序
       - prescriptions(patient_id, visit_id)  按患者/就诊查方
       - followups(patient_id, visit_id)
       - inquiry_records(patient_id, visit_id)
       - conversations(patient_id, last_message_at)
       - patients(deleted_at)  软删除过滤
    2) 乐观锁 version 列：NOT NULL DEFAULT 1，配合 ORM version_id_col 在并发编辑时做版本校验，
       冲突由全局异常处理器转 409。必须 NOT NULL（否则 version_id_col 的 `version = NULL` 判定会让 UPDATE 全部失效）。
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    # 1) 索引（CREATE INDEX IF NOT EXISTS 在 SQLite 3.9+ / Postgres 9.5+ 均支持）
    index_cmds = [
        ("idx_visits_patient_date", "visits", "patient_id, visit_date"),
        ("idx_prescriptions_patient", "prescriptions", "patient_id"),
        ("idx_prescriptions_visit", "prescriptions", "visit_id"),
        ("idx_followups_patient", "followups", "patient_id"),
        ("idx_followups_visit", "followups", "visit_id"),
        ("idx_inquiry_patient", "inquiry_records", "patient_id"),
        ("idx_inquiry_visit", "inquiry_records", "visit_id"),
        ("idx_conversations_patient", "conversations", "patient_id"),
        ("idx_conversations_last_msg", "conversations", "last_message_at"),
        ("idx_patients_deleted_at", "patients", "deleted_at"),
    ]
    with engine.begin() as conn:
        for idx_name, table, cols in index_cmds:
            if table not in existing_tables:
                continue
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({cols})"
            ))

    # 2) version 列：仅对存在的存量表补齐；新库已由 create_all 建好（_sync 会跳过该列）
    #    注意：必须每表重新 inspect（不可复用上面的 insp）。SQLite 方言对 ALTER ADD COLUMN
    #    不做 info-cache 失效，复用缓存会误判后续表仍缺列而重复 ADD COLUMN；SQLite 对重名列
    #    的 ADD COLUMN 是静默无效果的，导致 visits/prescriptions/followups 的 version 列停留在
    #    可空无默认值的状态，旧数据 version 为 NULL → ORM 乐观锁 UPDATE 变成 `version IS NULL`
    #    永远匹配不到（或直接报缺少绑定参数），进而处方编辑/回填/签名全部失败。
    #    因此这里对「列已存在」的情况再做两步兜底：补默认值 + 回填 NULL。
    version_tables = [t for t in ("patients", "visits", "prescriptions", "followups") if t in existing_tables]
    for t in version_tables:
        if "version" not in {c["name"] for c in inspect(engine).get_columns(t)}:
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE {t} ADD COLUMN version INTEGER NOT NULL DEFAULT 1"
                ))
            continue
        # 历史库：列已存在但可能可空/无默认值，且存量行 version 为 NULL —— 就地修正。
        # SQLite 不支持 ALTER COLUMN SET DEFAULT / SET NOT NULL，只能回填 NULL 值；
        # 新写入仍由 ORM 的 server_default=1 保证，因此这里以「回填」为主。
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                try:
                    conn.execute(text(f"ALTER TABLE {t} ALTER COLUMN version SET DEFAULT 1"))
                    conn.execute(text(f"ALTER TABLE {t} ALTER COLUMN version SET NOT NULL"))
                except Exception as e:
                    logging.getLogger(__name__).warning(
                        "m0018: 为 %s.version 补默认值/非空约束失败（不影响 NULL 回填）—— %s", t, e
                    )
            conn.execute(text(f"UPDATE {t} SET version = 1 WHERE version IS NULL"))


@migration(
    "0019",
    "处方电子签名与防篡改：新增内容哈希/签名列，并为存量处方回填哈希基线",
)
def m0019() -> None:
    """存量库补齐签名/哈希列（新库已由 create_all 建好；_sync_model_columns 也会补列，这里幂等兜底），
    并为已有处方回填 content_hash 基线，使其后续被篡改时可被检出。
    """
    from sqlalchemy.orm import sessionmaker, joinedload
    from app.models.prescription import Prescription, compute_prescription_hash

    insp = inspect(engine)
    existing = {c["name"] for c in insp.get_columns("prescriptions")}
    new_cols = {
        "content_hash": "VARCHAR(64)",
        "signed_by": "VARCHAR(50)",
        "signed_by_id": "INTEGER",
        "signed_at": "TIMESTAMP",
        "signature": "VARCHAR(64)",
    }
    with engine.begin() as conn:
        for col, ctype in new_cols.items():
            if col in existing:
                continue
            conn.execute(text(f"ALTER TABLE prescriptions ADD COLUMN {col} {ctype}"))
        # 兜底：早期版本的 m0018 因 Inspector 缓存问题未能给本表补上 NOT NULL DEFAULT 1，
        # 存量行 version 可能为 NULL。乐观锁的 `WHERE version = NULL` 永远匹配不到，
        # 后续任何处方 UPDATE（编辑/发药/签名）都会失败，故在回填前先修正。
        conn.execute(text("UPDATE prescriptions SET version = 1 WHERE version IS NULL"))

    # 回填：为存量处方建立内容哈希基线（之后任何内容改动都可被 verify 检出）。
    # 用 Core UPDATE 而非 ORM 赋值：ORM 的 version_id_col 会给每行追加乐观锁条件，
    # 对版本号缺失/不一致的存量行会抛 StatementError 或 StaleDataError，迁移不应依赖业务乐观锁。
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        rows = (
            s.query(Prescription)
            .options(
                joinedload(Prescription.items),
                joinedload(Prescription.acupoints),
                joinedload(Prescription.injections),
            )
            .filter(Prescription.content_hash.is_(None))
            .all()
        )
        updates = [{"pid": p.id, "h": compute_prescription_hash(p)} for p in rows]
        s.rollback()
        if updates:
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE prescriptions SET content_hash = :h WHERE id = :pid"),
                    updates,
                )
    finally:
        s.close()


@migration(
    "0020",
    "索引补齐：patients(name/phone) 加速患者检索/去重",
)
def m0020() -> None:
    """存量库补齐患者姓名/电话索引（新库已由模型 __table_args__ 经 create_all 建好）。"""
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    if "patients" not in existing_tables:
        return
    with engine.begin() as conn:
        for idx_name, cols in (
            ("idx_patients_name", "name"),
            ("idx_patients_phone", "phone"),
        ):
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON patients({cols})"))


@migration(
    "0021",
    "乐观锁脏数据修复：回填 patients/visits/prescriptions/followups 中为 NULL 的 version",
)
def m0021() -> None:
    """修复早期 m0018 留下的 version=NULL 脏数据。

    背景：旧版 m0018 里复用了同一个 Inspector 缓存来判断「表是否缺 version 列」，
    SQLite 方言对 ALTER ADD COLUMN 不失效 info-cache，导致第一张表之后的
    visits / prescriptions / followups 被重复 `ADD COLUMN version INTEGER`
    （SQLite 对重名列静默无效），version 列于是停留在「可空、无默认值」。
    存量行 version 为 NULL 时，ORM 乐观锁生成的 `WHERE version = NULL` 永远不匹配，
    表现为启动期回填报「缺少绑定参数 prescriptions_version」，或任意编辑报 409/500。

    该迁移幂等：只对仍存在 NULL 的表做回填，已修复的库为空操作。
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    for t in ("patients", "visits", "prescriptions", "followups"):
        if t not in existing_tables:
            continue
        cols = {c["name"] for c in inspect(engine).get_columns(t)}
        if "version" not in cols:
            continue
        with engine.begin() as conn:
            result = conn.execute(text(f"UPDATE {t} SET version = 1 WHERE version IS NULL"))
            if result.rowcount:
                logging.getLogger(__name__).warning(
                    "m0021: %s 回填 %d 行 version=NULL -> 1", t, result.rowcount
                )


@migration(
    "0022",
    "收费权限补齐：为存量账号追加 billing 读写并显式化角色默认权限集",
)
def m0022() -> None:
    """新增 /billing 域后的存量账号权限对齐。

    两个问题：
    1) 显式配置过权限的账号不会自动获得 billing 读写（user_permissions 在 permissions
       非空时直接使用，不回退角色默认集）；
    2) permissions 为空的账号虽然后端按角色默认集放行，但前端 auth.can() 只看显式数组，
       会导致「后端可收费、前端看不到收费按钮/菜单」。

    处理：对非管理员账号计算其有效权限集（显式集，或角色默认集），凡含处方/库存写权限者
    追加 billing:read/billing:write，并把结果写回 permissions（空集账号一并显式化）。
    只读账号、管理员不变。幂等：仅补齐缺失权限，不覆盖管理员后续的自定义调整。
    """
    from app.permissions import ROLE_DEFAULT_PERMSET

    insp = inspect(engine)
    if "users" not in set(insp.get_table_names()):
        return
    user_cols = {c["name"] for c in insp.get_columns("users")}
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, role, is_admin, permissions FROM users")).fetchall()
        for row in rows:
            uid = row[0]
            role = row[1]
            is_admin = bool(row[2]) if "is_admin" in user_cols else False
            raw = row[3]
            if is_admin:
                continue  # 超级用户绕过权限表，前端 auth.can() 亦直接放行
            perms = [p for p in (raw or "").split(",") if p]
            effective = perms if perms else list(ROLE_DEFAULT_PERMSET.get(role, []))
            if "prescription:write" not in effective and "stock:write" not in effective:
                continue  # 只读账号不授予收费
            added = [p for p in ("billing:read", "billing:write") if p not in effective]
            if added or not perms:
                conn.execute(
                    text("UPDATE users SET permissions = :p WHERE id = :id"),
                    {"p": ",".join(effective + added), "id": uid},
                )


@migration(
    "0023",
    "收费单 prescription_id 改为可空（支持挂号费等非处方收费）",
)
def m0023() -> None:
    """新增 挂号费 收费类型后，收费单不再必须绑定处方。

    模型已将 prescription_id 设可为空（新库由 create_all 直接建为可空）；
    存量库该列仍为 NOT NULL，SQLite 不支持 ALTER 改可空，故重建 charges 表：
    去掉 prescription_id 的 NOT NULL 约束，保留全部数据与索引/唯一约束。
    （kind 列由 _sync_model_columns 在迁移前补齐，故重建时已存在。）
    """
    insp = inspect(engine)
    if "charges" not in set(insp.get_table_names()):
        return
    cols = insp.get_columns("charges")
    pid = next((c for c in cols if c["name"] == "prescription_id"), None)
    if pid is None:
        return
    if pid.get("nullable"):
        return  # 新库已可空，无需重建

    has_kind = any(c["name"] == "kind" for c in cols)
    new_cols = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "charge_no VARCHAR(32) NOT NULL",
        "prescription_id INTEGER",
        "patient_id INTEGER",
        "visit_id INTEGER",
        "patient_name VARCHAR(50)",
        "prescription_title VARCHAR(120)",
        "amount NUMERIC(12,2)",
        "discount NUMERIC(12,2)",
        "payable NUMERIC(12,2)",
        "paid NUMERIC(12,2)",
        "payment_method VARCHAR(20)",
        "status VARCHAR(20)",
        "cashier_id INTEGER",
        "cashier_name VARCHAR(50)",
        "paid_at DATETIME",
        "refunded_by VARCHAR(50)",
        "refunded_at DATETIME",
        "refund_reason VARCHAR(200)",
        "note TEXT",
        "created_at DATETIME",
        "kind VARCHAR(20) NOT NULL DEFAULT 'prescription'",
        # 保留 _sync_model_columns 已补进旧表的后续列，避免重建时丢掉退款/作废审计数据
        *[
            f"{name} {sqltype}"
            for name, sqltype in (
                ("overpaid", "NUMERIC(12,2) DEFAULT 0"),
                ("refund_amount", "NUMERIC(12,2) DEFAULT 0"),
                ("cancelled_by", "VARCHAR(50)"),
                ("cancelled_at", "DATETIME"),
                ("cancel_reason", "VARCHAR(200)"),
            )
            if any(c["name"] == name for c in cols)
        ],
        "FOREIGN KEY(prescription_id) REFERENCES prescriptions(id) ON DELETE SET NULL",
    ]
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE charges_new (" + ", ".join(new_cols) + ")"))
        # 只拷贝新表实际存在的列：_sync_model_columns 可能已先补入后续迁移才引入的列
        # （如 overpaid/refund_amount），直接全量 INSERT 会报 "no such column"。
        new_col_names = {c.split()[0] for c in new_cols}
        col_names = [c["name"] for c in cols if c["name"] in new_col_names]
        col_list = ", ".join(col_names)
        # _sync_model_columns 在迁移前补出的 kind 为 NULL，直接插入新表 NOT NULL 列会中断启动；
        # 历史收费单都是处方收费，统一按 prescription 回填。
        select_list = ", ".join(
            "COALESCE(kind, 'prescription')" if c == "kind" else c for c in col_names
        )
        if has_kind:
            conn.execute(text(
                f"INSERT INTO charges_new ({col_list}) SELECT {select_list} FROM charges"
            ))
        else:
            # 极端情况：sync 尚未补 kind（理论不会发生），旧行按 prescription 处理
            conn.execute(text(
                f"INSERT INTO charges_new (id, charge_no, prescription_id, patient_id, visit_id, "
                f"patient_name, prescription_title, amount, discount, payable, paid, payment_method, "
                f"status, cashier_id, cashier_name, paid_at, refunded_by, refunded_at, refund_reason, "
                f"note, created_at) "
                f"SELECT id, charge_no, prescription_id, patient_id, visit_id, patient_name, "
                f"prescription_title, amount, discount, payable, paid, payment_method, status, "
                f"cashier_id, cashier_name, paid_at, refunded_by, refunded_at, refund_reason, note, "
                f"created_at FROM charges"
            ))
        conn.execute(text("DROP TABLE charges"))
        conn.execute(text("ALTER TABLE charges_new RENAME TO charges"))
        # 重建索引/唯一约束
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_charges_no ON charges(charge_no)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_charges_status ON charges(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_charges_created_at ON charges(created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_charges_patient_created ON charges(patient_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_charges_prescription ON charges(prescription_id)"))


@migration(
    "0024",
    "收费单补退款/多收/作废字段并回填；挂号排队号加唯一约束（防并发重号）",
)
def m0024() -> None:
    """P0/P1 修复的数据迁移：
    1) charges 存量库补 overpaid / refund_amount / cancelled_* 列（新库由 create_all 已建好），
       并把历史「已退费」单按实收 paid 回填 refund_amount、把多收差额回填 overpaid，
       让旧数据的统计口径与新逻辑一致。
    2) visits 上 (visit_date, queue_no) 建唯一索引前，先把历史重复号重排，
       避免建索引失败；非挂号就诊 queue_no 为 NULL，SQLite 唯一索引允许多个 NULL。
    """
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    with engine.begin() as conn:
        if "charges" in tables:
            cols = {c["name"] for c in insp.get_columns("charges")}
            extra = [
                ("overpaid", "NUMERIC(12,2)"),
                ("refund_amount", "NUMERIC(12,2)"),
                ("cancelled_by", "VARCHAR(50)"),
                ("cancelled_at", "DATETIME"),
                ("cancel_reason", "VARCHAR(200)"),
            ]
            for name, ddl in extra:
                if name not in cols:
                    conn.execute(text(f"ALTER TABLE charges ADD COLUMN {name} {ddl}"))
            # 旧逻辑：已退费全额退，paid 未清零；按实收回填，退款统计不再用 payable 冒充
            conn.execute(text(
                "UPDATE charges SET refund_amount = COALESCE(paid, 0) "
                "WHERE status = '已退费' AND (refund_amount IS NULL OR refund_amount = 0)"
            ))
            conn.execute(text(
                "UPDATE charges SET overpaid = "
                "CASE WHEN COALESCE(paid,0) > COALESCE(payable,0) "
                "THEN COALESCE(paid,0) - COALESCE(payable,0) ELSE 0 END "
                "WHERE overpaid IS NULL"
            ))
            conn.execute(text("UPDATE charges SET refund_amount = 0 WHERE refund_amount IS NULL"))

        if "visits" in tables:
            vcols = {c["name"] for c in insp.get_columns("visits")}
            if "queue_no" in vcols:
                # 历史重复号：保留每组第一条，其余重排到当日最大号之后
                dups = conn.execute(text(
                    "SELECT visit_date, queue_no, COUNT(*) AS c FROM visits "
                    "WHERE queue_no IS NOT NULL GROUP BY visit_date, queue_no HAVING c > 1"
                )).fetchall()
                for day, qno, _ in dups:
                    ids = [r[0] for r in conn.execute(
                        text("SELECT id FROM visits WHERE visit_date = :d AND queue_no = :q ORDER BY id"),
                        {"d": day, "q": qno},
                    ).fetchall()]
                    mx = conn.execute(
                        text("SELECT COALESCE(MAX(queue_no), 0) FROM visits WHERE visit_date = :d"),
                        {"d": day},
                    ).scalar() or 0
                    for i, vid in enumerate(ids[1:], start=1):
                        conn.execute(
                            text("UPDATE visits SET queue_no = :n WHERE id = :i"),
                            {"n": mx + i, "i": vid},
                        )
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_visits_date_queue "
                    "ON visits(visit_date, queue_no)"
                ))


@migration(
    "0025",
    "收费单：冲正历史重复开单 + 一处方一笔在账（部分唯一索引）",
)
def m0025() -> None:
    """根治「点一次收费还能继续重复收费」：

    1) 冲正存量脏数据：同一处方下若有多张「待收费/已收费」单，保留最早一张，
       其余标记为「已取消」并在 note 写明冲正原因（不删除、不改动真实收款金额，可回溯）。
       被冲正的单不再计入营收统计，账实恢复一致。
    2) 建部分唯一索引，让「一处方只能有一笔在账的钱」由数据库兜底：
       已退费/已取消是终态历史，不占用唯一性，退费后仍可合法重新开单。
    """
    insp = inspect(engine)
    if "charges" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("charges")}
    active_cond = "status IN ('待收费', '已收费')"

    with engine.begin() as conn:
        # 旧数据中 kind 可能为 NULL，统一规范成处方收费，保证索引条件与查询口径一致
        conn.execute(text("UPDATE charges SET kind = 'prescription' WHERE kind IS NULL"))

        dups = conn.execute(text(
            "SELECT prescription_id, COUNT(*) AS c FROM charges "
            f"WHERE prescription_id IS NOT NULL AND kind = 'prescription' AND {active_cond} "
            "GROUP BY prescription_id HAVING c > 1"
        )).fetchall()
        has_cancel_reason = "cancel_reason" in cols
        has_note = "note" in cols
        for pid, _ in dups:
            ids = [r[0] for r in conn.execute(
                text("SELECT id FROM charges WHERE prescription_id = :p "
                     f"AND kind = 'prescription' AND {active_cond} ORDER BY id"),
                {"p": pid},
            ).fetchall()]
            keep = ids[0]
            for extra in ids[1:]:
                old_note = ""
                if has_note:
                    old_note = conn.execute(
                        text("SELECT COALESCE(note, '') FROM charges WHERE id = :i"),
                        {"i": extra},
                    ).scalar() or ""
                note = (old_note + "；" if old_note else "") + \
                    f"重复开单自动冲正（迁移 0025，保留收费单 #{keep}）"
                sets = ["status = '已取消'"]
                params: dict = {"i": extra}
                if has_note:
                    sets.append("note = :note")
                    params["note"] = note
                if has_cancel_reason:
                    sets.append("cancel_reason = :reason")
                    params["reason"] = "重复开单自动冲正（迁移 0025）"
                if "cancelled_by" in cols:
                    sets.append("cancelled_by = '系统迁移'")
                if "cancelled_at" in cols:
                    sets.append("cancelled_at = CURRENT_TIMESTAMP")
                conn.execute(text(f"UPDATE charges SET {', '.join(sets)} WHERE id = :i"), params)

        # 非处方收费（挂号费）同 visit+kind 也只保留一笔在账
        if "visit_id" in cols:
            vdups = conn.execute(text(
                "SELECT visit_id, kind, COUNT(*) AS c FROM charges "
                "WHERE prescription_id IS NULL AND visit_id IS NOT NULL AND "
                f"kind <> 'prescription' AND {active_cond} "
                "GROUP BY visit_id, kind HAVING c > 1"
            )).fetchall()
            for vid, k, _ in vdups:
                ids = [r[0] for r in conn.execute(
                    text("SELECT id FROM charges WHERE prescription_id IS NULL AND visit_id = :v "
                         f"AND kind = :k AND {active_cond} ORDER BY id"),
                    {"v": vid, "k": k},
                ).fetchall()]
                for extra in ids[1:]:
                    sets = ["status = '已取消'"]
                    if has_note:
                        sets.append("note = COALESCE(note, '') || '；重复挂号费开单自动冲正（迁移 0025）'")
                    conn.execute(text(
                        f"UPDATE charges SET {', '.join(sets)} WHERE id = :i"
                    ), {"i": extra})

        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_charges_prescription_active "
            "ON charges(prescription_id) "
            "WHERE kind = 'prescription' AND status IN ('待收费', '已收费')"
        ))


@migration(
    "0026",
    "挂号费在账唯一性 + 存量库索引/就诊状态回填",
)
def m0026() -> None:
    """补齐 create_all 不会为存量表追加的部分：
    1) 挂号费按 (visit_id, kind) 建部分唯一索引（先冲正历史重复，避免建索引失败阻断启动）；
    2) 旧库由 _sync_model_columns 补出的 visits.status 为 NULL，回填「待诊」；
    3) 补建模型 __table_args__ 中新增的索引。
    """
    import logging as _logging
    log = _logging.getLogger(__name__)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    active = "status IN ('待收费', '已收费')"
    with engine.begin() as conn:
        if "charges" in tables:
            cols = {c["name"] for c in insp.get_columns("charges")}
            if {"visit_id", "kind", "status", "prescription_id"} <= cols:
                conn.execute(text("UPDATE charges SET kind = 'prescription' WHERE kind IS NULL"))
                dups = conn.execute(text(
                    "SELECT visit_id, kind, COUNT(*) FROM charges "
                    "WHERE prescription_id IS NULL AND visit_id IS NOT NULL "
                    f"AND kind <> 'prescription' AND {active} "
                    "GROUP BY visit_id, kind HAVING COUNT(*) > 1"
                )).fetchall()
                has_note = "note" in cols
                for vid, kind, _ in dups:
                    ids = [r[0] for r in conn.execute(text(
                        "SELECT id FROM charges WHERE prescription_id IS NULL AND visit_id = :v "
                        f"AND kind = :k AND {active} ORDER BY id"
                    ), {"v": vid, "k": kind}).fetchall()]
                    for extra in ids[1:]:
                        if has_note:
                            conn.execute(text(
                                "UPDATE charges SET status = '已取消', "
                                "note = COALESCE(note, '') || '；重复挂号费开单自动冲正（迁移 0026）' "
                                "WHERE id = :i"
                            ), {"i": extra})
                        else:
                            conn.execute(text("UPDATE charges SET status = '已取消' WHERE id = :i"),
                                         {"i": extra})
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_charges_visit_kind_active "
                    "ON charges(visit_id, kind) WHERE prescription_id IS NULL "
                    f"AND visit_id IS NOT NULL AND kind <> 'prescription' AND {active}"
                ))
        if "visits" in tables:
            if "status" in {c["name"] for c in insp.get_columns("visits")}:
                conn.execute(text("UPDATE visits SET status = '待诊' WHERE status IS NULL OR status = ''"))
            for ddl in (
                "CREATE INDEX IF NOT EXISTS idx_visits_patient_date ON visits(patient_id, visit_date)",
                "CREATE INDEX IF NOT EXISTS idx_visits_registered_at ON visits(registered_at)",
                "CREATE INDEX IF NOT EXISTS idx_visits_status ON visits(status)",
            ):
                try:
                    conn.execute(text(ddl))
                except Exception as e:
                    log.warning("m0026 补建索引失败（不影响其它迁移）: %s", e)
        if "stock_transactions" in tables:
            try:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_stock_transactions_item_created "
                    "ON stock_transactions(item_id, created_at)"
                ))
            except Exception as e:
                log.warning("m0026 补建库存流水索引失败: %s", e)


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