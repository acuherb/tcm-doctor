"""数据模板：把药材 / 中药方库 / 针灸方库 / 穴位 / 知识库等内容数据导出为可导入的 JSON 模板，
并支持从 JSON 模板（用户上传或内置）批量导入。

设计：内容数据不入库（见 .gitignore），默认安装为「纯框架」，用户按需导入模板。
内置模板文件位于 app/data/（herbs*.json / classic_formulas.json / acupoint_formulas.json /
acupoints.json / knowledge_entries.json + books/*.json），本地存在时可在前端一键「导入内置模板」。
"""
import json
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.herb import Herb
from app.models.prescription import ClassicFormula
from app.models.acupuncture import Acupoint, AcupointFormula
from app.models.knowledge import KnowledgeEntry

DATA_DIR = Path(__file__).parent / "data"

# 每种模板：模型、自然键（幂等 upsert 依据）、跳过列（id/时间戳/外部引用）、内置文件路径。
# 新增内容类型只需在此登记一项，导出/导入/内置加载自动生效。
TEMPLATE_TYPES: dict = {
    "herbs": {
        "label": "药材字典",
        "model": Herb,
        "key": "name",
        "skip": {"id", "created_at"},
        "bundled": [DATA_DIR / "herbs_extended.json", DATA_DIR / "herbs.json"],
    },
    "classic_formulas": {
        "label": "中药方库",
        "model": ClassicFormula,
        "key": "name",
        "skip": {"id", "created_at"},
        "bundled": [DATA_DIR / "classic_formulas.json"],
    },
    "acupoint_formulas": {
        "label": "针灸方库",
        "model": AcupointFormula,
        "key": "name",
        "skip": {"id", "created_at"},
        "bundled": [DATA_DIR / "acupoint_formulas.json"],
    },
    "acupoints": {
        "label": "穴位",
        "model": Acupoint,
        "key": "name",
        "skip": {"id", "created_at"},
        "bundled": [DATA_DIR / "acupoints.json"],
    },
    "knowledge": {
        "label": "知识库",
        "model": KnowledgeEntry,
        "key": "title",
        # 跳过 vector_id：ChromaDB 向量指针与模板无关，导入后由语义检索重建
        "skip": {"id", "created_at", "vector_id"},
        "bundled": [DATA_DIR / "knowledge_entries.json", *sorted(DATA_DIR.glob("books/*.json"))],
    },
}


def list_types(db: Session) -> list:
    """列出可导入的模板类型、当前条数及内置模板是否可用（前端据此显示状态/按钮）。"""
    out = []
    for t, spec in TEMPLATE_TYPES.items():
        out.append(
            {
                "type": t,
                "label": spec["label"],
                "key": spec["key"],
                "count": db.query(spec["model"]).count(),
                "bundled_available": any(p.exists() for p in spec["bundled"]),
            }
        )
    return out


def _read_bundled(spec: dict) -> list:
    """读取内置模板文件，合并为条目列表（兼容 {items:[...]} 或直接 [...]）。"""
    items: list = []
    for p in spec["bundled"]:
        if not p.exists():
            continue
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            items.extend(data)
        elif isinstance(data, dict) and "items" in data:
            items.extend(data["items"])
    return items


def export_template(db: Session, type_: str) -> dict:
    """把当前库中某类型数据导出为模板 JSON（不含 id/时间戳/外部引用）。"""
    spec = TEMPLATE_TYPES[type_]
    model = spec["model"]
    skip = spec["skip"]
    cols = [c.name for c in model.__table__.columns if c.name not in skip]
    rows = db.query(model).all()
    items = []
    for r in rows:
        items.append({c: getattr(r, c) for c in cols})
    return {"type": type_, "label": spec["label"], "version": 1, "items": items}


def import_items(db: Session, type_: str, items: list, dry_run: bool = False) -> dict:
    """从模板条目批量导入，按自然键幂等 upsert（已存在则更新，不存在则新增）。

    返回新增/更新/跳过计数与少量错误摘要，便于前端回显。
    dry_run=True 时只做内存预检（统计新增/更新/跳过），**绝不写入、不提交**，
    用于导入前确认，避免误冲知识库；深层约束冲突会在真实提交时由数据库校验。
    """
    spec = TEMPLATE_TYPES[type_]
    model = spec["model"]
    key = spec["key"]
    skip = spec["skip"]
    cols = [c.name for c in model.__table__.columns if c.name not in skip]
    existing = {getattr(o, key): o for o in db.query(model).all()}

    added = updated = skipped = 0
    errors: list = []
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            skipped += 1
            continue
        kv = it.get(key)
        if not kv:
            skipped += 1
            errors.append(f"第{idx + 1}条缺少「{key}」")
            continue
        data = {c: it[c] for c in cols if c in it}
        obj = existing.get(kv)
        try:
            if obj is None:
                added += 1
                if dry_run:
                    existing[kv] = True  # 占位，使同批重复键计为「更新」，与真实导入计数一致
                else:
                    new_obj = model(**data)
                    db.add(new_obj)
                    existing[kv] = new_obj
            else:
                updated += 1
                if not dry_run:
                    for c, v in data.items():
                        setattr(obj, c, v)
        except IntegrityError:
            db.rollback()
            skipped += 1
            errors.append(f"「{kv}」写入失败（数据冲突）")
        except Exception as e:  # 单条脏数据不应中断整批
            db.rollback()
            skipped += 1
            errors.append(f"「{kv}」解析失败：{e}")

    if not dry_run:
        db.commit()
    return {
        "created": added,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
    }
