#!/usr/bin/env python3
"""把『模板/』下从应用导出的扁平 list JSON 归一化为 templates/examples/<type>.example.json。

- 按文件名关键字 / 结构识别类型 (herbs/classic_formulas/acupoint_formulas/acupoints/knowledge)
- 剥离服务端字段 (id/created_at/updated_at/vector_id)
- 写成 {type, version, items} 的规范模板格式（与导入端点、examples 一致）
- 校验每条都有自然键 (name/title)，缺则告警

用法:
    python3 scripts/sync_templates.py
    python3 scripts/sync_templates.py --src 模板 --dst templates/examples
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "模板"
DST = REPO / "templates" / "examples"

# 文件名关键字 -> 类型
NAME_MAP = {
    "中药材": "herbs",
    "中药方库": "classic_formulas",
    "针灸穴位": "acupoints",
    "针灸方库": "acupoint_formulas",
    "医籍文库": "knowledge",
}
TYPE_KEY = {
    "herbs": "name",
    "classic_formulas": "name",
    "acupoint_formulas": "name",
    "acupoints": "name",
    "knowledge": "title",
}
SKIP_KEYS = {"id", "created_at", "updated_at", "vector_id"}
VERSION = 1


def detect_type(path: Path) -> Optional[str]:
    name = path.stem
    for kw, t in NAME_MAP.items():
        if kw in name:
            return t
    # 结构兜底识别
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(d, list) and d and isinstance(d[0], dict):
        keys = set(d[0].keys())
        if "meridian" in keys:
            return "acupoints"
        if "composition" in keys:
            return "classic_formulas"
        if "technique" in keys:
            return "acupoint_formulas"
        if "title" in keys and "content" in keys:
            return "knowledge"
        return "herbs"
    return None


def normalize(items: list) -> list:
    out = []
    for it in items:
        if isinstance(it, dict):
            out.append({k: v for k, v in it.items() if k not in SKIP_KEYS})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--dst", type=Path, default=DST)
    args = ap.parse_args()

    if not args.src.is_dir():
        print(f"源目录不存在: {args.src}", file=sys.stderr)
        return 1
    args.dst.mkdir(parents=True, exist_ok=True)

    files = sorted(args.src.glob("*.json"))
    if not files:
        print(f"{args.src} 下没有 JSON 文件")
        return 1

    total = 0
    for f in files:
        t = detect_type(f)
        if not t:
            print(f"跳过（无法识别类型）: {f.name}")
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"跳过（解析失败 {e}）: {f.name}")
            continue
        items = data if isinstance(data, list) else data.get("items")
        if not isinstance(items, list):
            print(f"跳过（无 items/list）: {f.name}")
            continue

        key = TYPE_KEY[t]
        cleaned = normalize(items)
        missing = sum(1 for it in cleaned if not it.get(key))
        out = {"type": t, "version": VERSION, "items": cleaned}
        dst = args.dst / f"{t}.example.json"
        dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        total += len(cleaned)
        flag = f"  ⚠ 缺自然键 {missing} 条" if missing else ""
        print(f"{f.name:38s} -> {t:18s} 条目 {len(cleaned):5d}{flag}")

    print(f"\n完成：共归一化 {total} 条到 {args.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
