"""导入倪海厦 skill 全部内容到医籍文库

数据源: /home/debian/TCM/nihaixia   (参考目录，只读取不改动)
入库到: tcm-doctor/backend/tcm_doctor.db 的 knowledge_entries 表

规则:
- 每个 markdown 文件按 `##`/`###` 章节切分，一个章节 = 一条知识条目
- 无章节标题的文件整文件成一条
- 按 (source, title) 做 upsert：已存在则更新内容，否则新增（幂等可重放）
- category 按文件模块语义归类；source 统一为「倪海厦·<摘自>」

运行: cd tcm-doctor/backend && python3 seed_nihaixia.py
"""
import os
import re
import sqlite3
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
NHAIXIA = "/home/debian/TCM/nihaixia"
DB = os.path.join(HERE, "tcm_doctor.db")

# 每个文件 → (category, source标签, 是否切章节)
FILE_RULES = {
    # 主技能文档
    "SKILL.md": ("倪海厦体系", "倪海厦·总纲", True),
    # modules 模块
    "modules/01_shanghan_sun.md": ("伤寒论", "倪海厦·伤寒论", True),
    "modules/02_shanghan_other.md": ("伤寒论", "倪海厦·伤寒论", True),
    "modules/03_yian.md": ("医案", "倪海厦·医案", True),
    "modules/04_jingui.md": ("金匮要略", "倪海厦·金匮要略", True),
    "modules/05_huangdi_neijing.md": ("内经", "倪海厦·黄帝内经", True),
    "modules/06_liangdong.md": ("倪海厦", "倪海厦·人纪系列", True),
    "modules/07_bimen_hantang.md": ("倪海厦", "倪海厦·人纪系列", True),
    "modules/08_huangdi_detail.md": ("内经", "倪海厦·黄帝内经", True),
    "modules/09_zhenjiu_bencao.md": ("针灸", "倪海厦·针灸", True),
    "modules/10_fuyang_luntan.md": ("扶阳", "倪海厦·扶阳论坛", True),
    "modules/11_zhongjing_xinfa.md": ("经方", "倪海厦·经方心法", True),
    "modules/12_stanford_jingfang.md": ("经方", "倪海厦·经方讲座", True),
    "modules/13_shanghan_quebing.md": ("伤寒论", "倪海厦·伤寒论", True),
    "modules/14_yijinjing_bidu.md": ("内经", "倪海厦·易经筋必读", True),
    # references/distilled 提炼
    "references/distilled/01-six-meridian-formulas.md": ("六经", "倪海厦·六经方剂", True),
    "references/distilled/02-acupuncture-quick-ref.md": ("针灸", "倪海厦·针灸速查", True),
    "references/distilled/03-clinical-experience.md": ("临床经验", "倪海厦·临床经验", True),
    "references/distilled/04-acupuncture-highlights.md": ("针灸", "倪海厦·针灸精要", True),
    "references/distilled/05-clinical-dose-quickref.md": ("剂量", "倪海厦·剂量速查", True),
    "references/distilled/06-clinical-dose-c99.md": ("剂量", "倪海厦·剂量精华", True),
    # cases 医案
    "cases/00_merged_table.md": ("医案", "倪海厦·医案合辑", True),
    "cases/01_cancer.md": ("医案", "倪海厦·医案·癌症", True),
    "cases/02_cardiovascular.md": ("医案", "倪海厦·医案·心血管", True),
    "cases/03_metabolic.md": ("医案", "倪海厦·医案·代谢", True),
    "cases/04_autoimmune.md": ("医案", "倪海厦·医案·自身免疫", True),
    "cases/05_neurological.md": ("医案", "倪海厦·医案·神经", True),
    "cases/06_other.md": ("医案", "倪海厦·医案·其他", True),
}

# markdown 标题：## 或 ### 开头段
HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")


def split_by_headings(text):
    """按 ##/### 章节切分，返回 [(title, body)]"""
    blocks = []
    cur_title = None
    cur_lines = []
    last_lvl = None

    def flush():
        nonlocal cur_title
        if cur_title and cur_lines:
            body = "\n".join(cur_lines).strip()
            if body:
                blocks.append((cur_title, body))
        elif cur_title and not cur_lines:
            pass
        cur_lines.clear()
        cur_title = None

    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            lvl = len(m.group(1))
            if cur_title and (last_lvl is None or lvl <= last_lvl):
                flush()
            # 保留子标题在当前块内
            if last_lvl is not None and lvl > last_lvl:
                cur_lines.append(line)
                continue
            flush()
            cur_title = m.group(2).strip()
            last_lvl = lvl
            continue
        if cur_title is not None:
            cur_lines.append(line)
        # 文件内首个标题前的内容（前言）忽略，避免垃圾条目
    flush()
    return blocks


def parse_file(filepath):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    blocks = split_by_headings(content)
    if not blocks:
        title = os.path.splitext(os.path.basename(filepath))[0]
        blocks = [(title, content.strip())]
    return blocks


def collect_all():
    """生成 (category, source, title, content) 列表"""
    out = []
    for rel, (category, source, use_heading) in FILE_RULES.items():
        filepath = os.path.join(NHAIXIA, rel)
        if not os.path.exists(filepath):
            continue
        if use_heading:
            blocks = parse_file(filepath)
        else:
            with open(filepath, encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                continue
            blocks = [(os.path.splitext(os.path.basename(rel))[0], content)]
        # 去重同一文件内的重复标题
        seen = set()
        for i, (title, body) in enumerate(blocks, 1):
            key = title
            if title in seen:
                key = f"{title}（{i}）"
            seen.add(title)
            out.append((category, source, key, body))
    return out


def upsert(db, source, title, category, content):
    cur = db.execute(
        "SELECT id FROM knowledge_entries WHERE source=? AND title=?",
        (source, title),
    )
    row = cur.fetchone()
    count_ok = False
    if row:
        db.execute(
            "UPDATE knowledge_entries SET category=?, content=? WHERE id=?",
            (category, content, row[0]),
        )
        return "updated"
    db.execute(
        "INSERT INTO knowledge_entries (title, category, source, content, created_at) VALUES (?,?,?,?,?)",
        (title, category, source, content, datetime.now().isoformat(sep=" ")),
    )
    return "added"


def main():
    conn = sqlite3.connect(DB)
    try:
        items = collect_all()
        stats = {"added": 0, "updated": 0, "skipped": 0}
        by_cat = {}
        for category, source, title, content in items:
            if not title or not content:
                stats["skipped"] += 1
                continue
            result = upsert(conn, source, title, category, content)
            stats[result] += 1
            by_cat[category] = by_cat.get(category, 0) + 1
        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM knowledge_entries").fetchone()[0]
        print(f"解析条目: {len(items)}")
        print(f"本次: 新增={stats['added']} 更新={stats['updated']} 跳过={stats['skipped']}")
        print(f"医籍文库条目总数: {total}")
        print("按分类:")
        for cat, n in sorted(by_cat.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {n}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()