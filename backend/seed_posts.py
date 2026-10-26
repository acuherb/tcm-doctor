"""导入 posts（静态博客文章）全部内容到医籍文库

数据源: /home/debian/TCM/posts   (参考目录，只读取不改动)
入库到: tcm-doctor/backend/tcm_doctor.db 的 knowledge_entries 表

规则:
- 每个 markdown 文件 = 一条知识条目（标题取 frontmatter 的 title，正文去 frontmatter）
- 跳过 _index.md（目录首页）与 images/
- 按目录映射到经典名分类（category）+ 出处（source）
- 按 (source, title) 做 upsert：已存在则更新，否则新增（幂等可重放）
- 同一 (source, title) 重复时，title 自动加序号避免互相覆盖

运行:
  cd tcm-doctor/backend && python3 seed_posts.py           # 增量导入
  cd tcm-doctor/backend && python3 seed_posts.py --clear   # 先清空表再导入
"""
import os
import sys
import sqlite3
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
POSTS = "/home/debian/TCM/posts"
DB = os.path.join(HERE, "tcm_doctor.db")

SKIP_DIRS = {"images"}

# 目录 → (category, source)
CATE_MAP = {
    "bencao": ("本草", "神农本草经"),
    "shanghan": ("伤寒论", "伤寒论"),
    "shishimilu": ("石室秘录", "石室秘录"),
    "suwen": ("素问", "素问"),
    "lingshu": ("灵枢经", "灵枢"),
    "waijing": ("黄帝外经", "黄帝外经"),
    "zhenjiu": ("针灸", "针灸"),
    "jingui": ("金匮要略", "金匮要略"),
    "yihua": ("医话", "医话"),
}


def strip_bom(text):
    return text[1:] if text.startswith("\ufeff") else text


def parse_file(filepath):
    """解析 frontmatter，返回 (title, content)。无 frontmatter 则标题取文件名。"""
    with open(filepath, encoding="utf-8") as f:
        text = f.read()
    text = strip_bom(text)
    title = None
    content = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm, rest = parts[1], parts[2]
            for line in fm.splitlines():
                line = line.strip()
                if line.startswith("title:"):
                    val = line.split(":", 1)[1].strip().strip('"').strip("'")
                    title = val or None
            content = rest.lstrip("\n")
    if not title:
        title = os.path.splitext(os.path.basename(filepath))[0]
    content = content.strip()
    return title, content


def collect_all():
    """生成 (category, source, title, content) 列表，处理同名标题"""
    out = []
    for dirname, (category, source) in CATE_MAP.items():
        dirpath = os.path.join(POSTS, dirname)
        if not os.path.isdir(dirpath):
            continue
        files = sorted(
            f for f in os.listdir(dirpath)
            if f.endswith(".md") and f != "_index.md"
        )
        seen = set()
        for fname in files:
            title, content = parse_file(os.path.join(dirpath, fname))
            if not content:
                continue
            key = title
            if key in seen:
                i = 2
                while f"{title}（{i}）" in seen:
                    i += 1
                key = f"{title}（{i}）"
            seen.add(key)
            out.append((category, source, key, content))
    return out


def upsert(db, source, title, category, content):
    cur = db.execute(
        "SELECT id FROM knowledge_entries WHERE source=? AND title=?",
        (source, title),
    )
    row = cur.fetchone()
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
    clear = "--clear" in sys.argv
    conn = sqlite3.connect(DB)
    try:
        if clear:
            n = conn.execute("DELETE FROM knowledge_entries").rowcount
            conn.commit()
            print(f"已清空知识库: {n} 条")
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