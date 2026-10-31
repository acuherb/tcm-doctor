"""初始化数据 — 首次启动时导入药材、配伍禁忌、经典方剂、知识条目、默认用户"""
import hashlib
import secrets
import json
import sys
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app.models.herb import Herb
from app.models.prescription import ClassicFormula
from app.models.acupuncture import AcupointFormula
from app.models.knowledge import KnowledgeEntry
from app.models.user import User

DATA_DIR = Path(__file__).parent / "data"

# 顶层 seed 脚本（腧穴/字典）位于 backend 根目录，需加入 path 以便导入
sys.path.insert(0, str(Path(__file__).parent.parent))
from seed_dictionaries import seed_dictionaries
from seed_acupoints import seed_acupoints


def seed_herbs(db: Session) -> int:
    """导入中药材字典（按名称幂等：仅新增缺失药材，并为已有药材同步异名）"""
    # 优先使用扩展版数据
    data_file = DATA_DIR / "herbs_extended.json"
    if not data_file.exists():
        data_file = DATA_DIR / "herbs.json"

    if not data_file.exists():
        return 0

    with open(data_file, "r", encoding="utf-8") as f:
        herbs = json.load(f)

    existing = {h.name: h for h in db.query(Herb).all()}
    added_count = 0
    for h in herbs:
        name = h["name"]
        herb = existing.get(name)
        if herb is None:
            herb = Herb(
                name=name,
                aliases=h.get("aliases"),
                category=h.get("category"),
                nature=h.get("nature"),
                flavor=h.get("flavor"),
                meridian_tropism=h.get("meridian_tropism"),
                grade=h.get("grade"),
                flavors=h.get("flavors") or _split_flavor(h.get("flavor")),
                meridians=h.get("meridians") or _split_meridian(h.get("meridian_tropism")),
                directions=h.get("directions"),
                tags=h.get("tags") or ([h["category"]] if h.get("category") else None),
                efficacy=h.get("efficacy"),
                dosage_min=h.get("dosage_min"),
                dosage_max=h.get("dosage_max"),
                toxicity=h.get("toxicity", "无毒"),
                pregnancy_contraindicated=h.get("pregnancy_contraindicated", False),
                storage_condition=h.get("storage_condition"),
            )
            db.add(herb)
            existing[name] = herb
            added_count += 1
        else:
            # 同步异名，保证后续补的异名（如炙甘草→甘草）能进入既有记录
            herb.aliases = h.get("aliases")

    db.commit()
    return added_count


_FLAVOR_CHARS = set("辛甘酸苦咸淡涩")
_MERIDIANS = {"心", "肝", "脾", "肺", "肾", "胃", "大肠", "小肠", "膀胱", "三焦", "胆", "心包"}


def _split_flavor(s) -> list[str] | None:
    """旧字段 flavor 字符串（如‘辛苦’）拆分为五味字符数组"""
    if not s:
        return None
    fl = [c for c in str(s) if c in _FLAVOR_CHARS]
    return fl or None


def _split_meridian(s) -> list[str] | None:
    """旧字段 meridian_tropism 字符串拆分为十二经数组"""
    if not s:
        return None
    parts = [p.strip() for p in str(s).replace("、", ",").replace("，", ",").replace("/", ",").split(",") if p.strip()]
    md = [m for m in parts if m in _MERIDIANS]
    return md or None


def seed_classic_formulas(db: Session) -> int:
    """导入经典方剂（增量：按方名去重，只添加新方剂）"""
    data_file = DATA_DIR / "classic_formulas.json"
    if not data_file.exists():
        return db.query(ClassicFormula).count()

    with open(data_file, "r", encoding="utf-8") as f:
        formulas = json.load(f)

    # 获取已有方名集合
    existing_names = {n for (n,) in db.query(ClassicFormula.name).all()}

    added = 0
    for f_data in formulas:
        if f_data["name"] in existing_names:
            continue
        formula = ClassicFormula(
            name=f_data["name"],
            aliases=f_data.get("aliases"),
            source=f_data.get("source"),
            composition=f_data["composition"],
            efficacy=f_data.get("efficacy"),
            indications=f_data.get("indications"),
            usage=f_data.get("usage"),
            modifications=f_data.get("modifications"),
        )
        db.add(formula)
        existing_names.add(f_data["name"])
        added += 1

    if added:
        db.commit()

    total = db.query(ClassicFormula).count()
    if added:
        print(f"[Seed] 经典方剂新增 {added} 首，共 {total} 首")
    return total


def seed_acupoint_formulas(db: Session) -> int:
    """导入针灸方库（增量：按方名去重，只添加新针灸方）"""
    data_file = DATA_DIR / "acupoint_formulas.json"
    if not data_file.exists():
        return db.query(AcupointFormula).count()

    with open(data_file, "r", encoding="utf-8") as f:
        formulas = json.load(f)

    existing_names = {n for (n,) in db.query(AcupointFormula.name).all()}

    added = 0
    for f_data in formulas:
        if f_data["name"] in existing_names:
            continue
        formula = AcupointFormula(
            name=f_data["name"],
            aliases=f_data.get("aliases"),
            source=f_data.get("source"),
            efficacy=f_data.get("efficacy"),
            indications=f_data.get("indications"),
            usage=f_data.get("usage"),
            technique=f_data.get("technique"),
            treatment_frequency=f_data.get("treatment_frequency"),
            treatment_days=f_data.get("treatment_days"),
            composition=f_data["composition"],
            notes=f_data.get("notes"),
        )
        db.add(formula)
        existing_names.add(f_data["name"])
        added += 1

    if added:
        db.commit()

    total = db.query(AcupointFormula).count()
    if added:
        print(f"[Seed] 针灸方库新增 {added} 首，共 {total} 首")
    return total


def seed_knowledge(db: Session) -> int:
    """导入知识条目（增量：按标题去重，只添加新条目）
    从 knowledge_entries.json + books/ 目录下所有 JSON 批量加载
    """
    existing_titles = {t for (t,) in db.query(KnowledgeEntry.title).all()}
    added = 0

    # 1. 从主知识库文件加载
    data_file = DATA_DIR / "knowledge_entries.json"
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            entries = json.load(f)
        for e in entries:
            if e["title"] in existing_titles:
                continue
            entry = KnowledgeEntry(
                title=e["title"],
                category=e.get("category"),
                content=e.get("content"),
                source=e.get("source"),
            )
            db.add(entry)
            existing_titles.add(e["title"])
            added += 1

    # 2. 从 books/ 目录批量加载完整医籍
    books_dir = DATA_DIR / "books"
    if books_dir.exists():
        for json_file in sorted(books_dir.glob("*.json")):
            with open(json_file, "r", encoding="utf-8") as f:
                book_entries = json.load(f)
            book_added = 0
            for e in book_entries:
                if e["title"] in existing_titles:
                    continue
                entry = KnowledgeEntry(
                    title=e["title"],
                    category=e.get("category", "条文"),
                    content=e.get("content"),
                    source=e.get("source"),
                )
                db.add(entry)
                existing_titles.add(e["title"])
                added += 1
                book_added += 1
            if book_added:
                print(f"[Seed] {json_file.name} 新增 {book_added} 条")

    if added:
        db.commit()

    total = db.query(KnowledgeEntry).count()
    if added:
        print(f"[Seed] 知识条目共新增 {added} 条，总计 {total} 条")
    return total


def seed_default_user(db: Session) -> int:
    """首次启动创建默认管理员账号 admin / admin123"""
    if db.query(User).filter(User.username == "admin").count() > 0:
        return db.query(User).count()
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", "admin123".encode(), bytes.fromhex(salt), 260_000
    ).hex()
    db.add(User(
        username="admin",
        password_hash=f"{salt}${digest}",
        display_name="管理员",
        is_admin=True,
        must_change_password=True,
    ))
    db.commit()
    print("[Seed] 已创建默认用户: admin / admin123")
    return 1


def seed_guest_user(db: Session) -> int:
    """创建游客账号 guest / guest123 — 仅可浏览，不可增删改"""
    if db.query(User).filter(User.username == "guest").count() > 0:
        return db.query(User).count()
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", "guest123".encode(), bytes.fromhex(salt), 260_000
    ).hex()
    db.add(User(
        username="guest",
        password_hash=f"{salt}${digest}",
        display_name="游客",
        is_admin=False,
        must_change_password=False,
    ))
    db.commit()
    print("[Seed] 已创建游客用户: guest / guest123")
    return 1


def seed_all():
    """执行所有数据初始化"""
    # 确保导入所有模型并创建表（使本函数可独立运行，不依赖调用方已建表）
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        h = seed_herbs(db)
        f = seed_classic_formulas(db)
        af = seed_acupoint_formulas(db)
        k = seed_knowledge(db)
        u = seed_default_user(db)
        g = seed_guest_user(db)
        d = seed_dictionaries(db)
        a = seed_acupoints(db)
        print(f"[Seed] 导入完成: 药材={h}, 经典方={f}, 针灸方={af}, 知识条目={k}, 用户={u+1}, 游客={g}, 字典词条={d[0]}, 腧穴={a}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()