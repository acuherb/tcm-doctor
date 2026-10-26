"""导入倪海厦腧穴字典（合并两数据源）

- acupoint_index.md : 提供定位/功效/类型（部分正经）
- zhenjiu_164.txt  : 补齐全部十四正经 + 任督脉 + 奇穴

运行: cd tcm-doctor/backend && python3 seed_acupoints.py
"""
import os
import re
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_INDEX = "/home/debian/TCM/ni-haisha-tcm-skill/knowledge/acupoints/acupoint_index.md"
SRC_ZHENJIU = "/home/debian/TCM/nihaixia/references/audit/zhenjiu_164.txt"
DB = os.path.join(HERE, "tcm_doctor.db")

MERIDIAN_RE = re.compile(r"^##\s+分*细胞*$")

# 过滤非具体穴位的分组
SKIP_GROUPS = {"重要特定穴速记", "总计"}


def clean(text: str) -> str:
    text = text.strip().strip("*")
    text = re.sub(r"\[\[([^\]]+)\]\]\([^)]*\)", r"\1", text)
    return text.strip()


def parse_index(path):
    """返回 { name: (meridian, location, efficacy, point_type) }"""
    out = {}
    meridian = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^##\s+(.+)$", line)
            if m:
                meridian = m.group(1).strip()
                continue
            if not line.strip().startswith("|"):
                continue
            cells = line.split("|")
            if len(cells) < 6 or "--" in line or "穴名" in line:
                continue
            name = clean(cells[1])
            if not name:
                continue
            out[name] = (meridian, clean(cells[2]), clean(cells[3]), clean(cells[4]))
    return out


def parse_zhenjiu(path):
    """返回 [(name, meridian)]，覆盖十四经 + 任督 + 奇穴"""
    out = []
    group = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^##\s*(.+)$", line)
            if m:
                group = m.group(1).replace("（", "(").replace("）", ")")
                group = re.sub(r"\s*\(\s*\d+\s*项\s*\)\s*$", "", group).strip()
                if group in SKIP_GROUPS:
                    group = None
                continue
            if group is None or line.isdigit() or line.startswith("#") or line.startswith(">"):
                continue
            # 去掉注释(水沟、八风 etc.)；跳过特定穴速记词条
            name = clean(line.split("(")[0].strip())
            if "穴" in group and not re.search(r"[经脉任督]$", group):
                pass
            if not name:
                continue
            out.append((name, group))
    return out


def main():
    detail = parse_index(SRC_INDEX)
    zhenjiu = parse_zhenjiu(SRC_ZHENJIU)

    # 合并：以 zhenjiu 覆盖面为准，能匹配到 detail 者补全信息
    points = {}
    for name, meridian in zhenjiu:
        d = detail.get(name)
        if d:
            points[name] = (d[0], d[1], d[2], d[3])
        else:
            points[name] = (meridian, None, None, None)
    # 确保 index 里存在但 zhenjiu 未列出的也纳入
    for name, d in detail.items():
        if name not in points:
            points[name] = d

    db = sqlite3.connect(DB)
    # 幂等重建：穴位库以本脚本为权威数据源，复用 seed 时整表重建
    db.execute("DELETE FROM acupoints")
    inserted = updated = skipped = 0
    for name, (meridian, location, efficacy, ptype) in points.items():
        db.execute(
            "insert into acupoints(name,meridian,location,efficacy,point_type,is_active,created_at) "
            "values(?,?,?,?,?,1,datetime('now'))",
            (name, meridian or "未分类", location, efficacy, ptype),
        )
        inserted += 1
    db.commit()

    total = db.execute("select count(*) from acupoints").fetchone()[0]
    with_detail = db.execute("select count(*) from acupoints where location is not null").fetchone()[0]
    print(f"合并数据: index详情={len(detail)} + zhenjiu={len(zhenjiu)} => 去重后 {len(points)} 穴")
    print(f"本次: 入库={inserted}  穴位库总数={total}  带定位详情={with_detail}")
    print("按归经分组:")
    for mer, cnt in db.execute("select meridian,count(*) from acupoints group by meridian").fetchall():
        print(f"  {mer}: {cnt}")


if __name__ == "__main__":
    main()