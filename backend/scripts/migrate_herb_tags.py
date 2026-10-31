"""药材库多维标签迁移（幂等）

为 herbs 表新增 grade / flavors / meridians / directions / tags 五列，
并从旧字段回填：
  - flavor（字符串，如“辛苦”）→ flavors（五味字符数组）
  - meridian_tropism（字符串）→ meridians（十二经数组）
  - category（单一分类）→ tags[0]

已存在目标列或目标值非空则跳过，可重复执行。

用法（在 backend/ 目录下）：
    python scripts/migrate_herb_tags.py
"""
import json

from sqlalchemy import text

from app.database import engine

NEW_COLUMNS = {
    "grade": "TEXT",
    "flavors": "TEXT",
    "meridians": "TEXT",
    "directions": "TEXT",
    "tags": "TEXT",
}

FLAVOR_CHARS = set("辛甘酸苦咸淡涩")
MERIDIANS = {"心", "肝", "脾", "肺", "肾", "胃", "大肠", "小肠", "膀胱", "三焦", "胆", "心包"}


def _split_meridian(s) -> list[str]:
    """旧字段 meridian_tropism（如‘归心、肺、膀胱经’）拆分为十二经数组。"""
    if not s:
        return []
    parts = [p.strip() for p in str(s).replace("、", ",").replace("，", ",").replace("/", ",").split(",") if p.strip()]
    out: list[str] = []
    for p in parts:
        tok = p.strip()
        if tok.startswith("归"):
            tok = tok[1:]
        # 去掉「经」及常见前缀限定词（手/足/六经/奇经等）
        tok = tok.replace("经", "").replace("手", "").replace("足", "")
        tok = tok.replace("太阴", "").replace("太阳", "").replace("少阴", "").replace("少阳", "").replace("厥阴", "")
        tok = tok.replace("阳明", "").replace("脉", "").replace("维", "").replace("跷", "")
        tok = tok.strip()
        if tok in MERIDIANS and tok not in out:
            out.append(tok)
    return out


def migrate() -> None:
    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(herbs)")).fetchall()}
        for name, ctype in NEW_COLUMNS.items():
            if name not in cols:
                conn.execute(text(f"ALTER TABLE herbs ADD COLUMN {name} {ctype}"))
                print(f"[migrate] 新增列 herbs.{name}")

        rows = conn.execute(
            text("SELECT id, flavor, meridian_tropism, category, flavors, meridians, tags FROM herbs")
        ).fetchall()

        updated = 0
        for hid, flavor, meridian, category, flavors, meridians, tags in rows:
            updates: dict = {}
            if flavors is None and flavor:
                fl = [c for c in str(flavor) if c in FLAVOR_CHARS]
                if fl:
                    updates["flavors"] = json.dumps(fl, ensure_ascii=False)
            if meridians is None and meridian:
                md = _split_meridian(meridian)
                if md:
                    updates["meridians"] = json.dumps(md, ensure_ascii=False)
            if tags is None and category:
                updates["tags"] = json.dumps([category], ensure_ascii=False)
            if updates:
                set_clause = ", ".join(f"{k} = :{k}" for k in updates)
                updates["hid"] = hid
                conn.execute(text(f"UPDATE herbs SET {set_clause} WHERE id = :hid"), updates)
                updated += 1

        print(f"[migrate] 回填完成：检查 {len(rows)} 条，更新 {updated} 条")
    print("[migrate] 药材库多维标签迁移结束（幂等）")


if __name__ == "__main__":
    migrate()
