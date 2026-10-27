"""腧穴字典种子 — 幂等导入（按穴名去重，绝不删除既有数据）

说明：
- 本脚本仅从 backend/app/data/acupoints.json 读取一份「常用腧穴精选」作为开箱数据。
- 如需完整 361 穴，请扩充/替换该 JSON 后重新运行（或调用 seed_acupoints(db)）。
- 与 seed_dictionaries.py 类似，设计为可被 app/seed.py 的 seed_all() 调用。
"""
import json
from pathlib import Path

from app.database import SessionLocal
from app.models.acupuncture import Acupoint


DATA_DIR = Path(__file__).parent / "app" / "data"


def seed_acupoints(db) -> int:
    """幂等导入常用腧穴：按穴名去重，只添加新穴，不影响用户已录入的腧穴"""
    data_file = DATA_DIR / "acupoints.json"
    if not data_file.exists():
        return 0
    with open(data_file, "r", encoding="utf-8") as f:
        points = json.load(f)

    existing = {n for (n,) in db.query(Acupoint.name).all()}
    added = 0
    for p in points:
        name = p["name"]
        if name in existing:
            continue
        db.add(Acupoint(
            name=name,
            meridian=p.get("meridian"),
            location=p.get("location"),
            efficacy=p.get("efficacy"),
            point_type=p.get("point_type"),
            notes=p.get("notes"),
        ))
        existing.add(name)
        added += 1
    if added:
        db.commit()
    return added


def main():
    db = SessionLocal()
    try:
        n = seed_acupoints(db)
        print(f"[Seed] 腧穴字典新增 {n} 个")
    finally:
        db.close()


if __name__ == "__main__":
    main()
