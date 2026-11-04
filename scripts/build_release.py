#!/usr/bin/env python3
"""根据『模板/』下从应用导出的内容，构建 GitHub Release 基础数据包 tcm-base-core.zip。

布局（与 templates/manifest.example.json 一致）：
    core/    herbs.json, acupoints.json
    formulas/ classic_formulas.json, acupoint_formulas.json
    books/   knowledge.json
    manifest.json

数据来源是维护者本地『模板/』下的原始导出（扁平 list），本脚本负责归一化
（剥离 id/created_at/updated_at/vector_id）后打包。templates/examples/ 仅保留
最小示例，完整内容只通过本 Release 资产分发，使仓库保持纯框架。

manifest.json 含版本、来源、各层条目数、sha256、依赖关系。
zip 是发布资产，不应提交进 git（已在 .gitignore 忽略 templates/releases/）。

用法:
    python3 scripts/build_release.py
    python3 scripts/build_release.py --version 1.0.0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# 允许以 `python3 scripts/build_release.py` 直接运行，并复用 sync_templates 的归一化逻辑
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_templates import detect_type, normalize  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "模板"
DST = REPO / "templates" / "releases" / "tcm-base-core.zip"
VERSION = 1

LAYERS = [
    {
        "name": "core",
        "label": "核心：药材 + 穴位",
        "depends_on": [],
        "types": ["herbs", "acupoints"],
        "files": ["core/herbs.json", "core/acupoints.json"],
    },
    {
        "name": "formulas",
        "label": "方库：中药方 + 针灸方",
        "depends_on": ["core"],
        "types": ["classic_formulas", "acupoint_formulas"],
        "files": ["formulas/classic_formulas.json", "formulas/acupoint_formulas.json"],
    },
    {
        "name": "books",
        "label": "医籍文库（可选）",
        "depends_on": ["core"],
        "types": ["knowledge"],
        "files": ["books/knowledge.json"],
    },
]


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--dst", type=Path, default=DST)
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    if not args.src.is_dir():
        print(f"源目录不存在: {args.src}", file=sys.stderr)
        return 1

    type_items: dict[str, list] = {}
    for f in sorted(args.src.glob("*.json")):
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
        type_items[t] = normalize(items)

    if not type_items:
        print("没有可打包的内容", file=sys.stderr)
        return 1

    args.dst.parent.mkdir(parents=True, exist_ok=True)

    file_texts: dict[str, str] = {}
    for layer in LAYERS:
        for t, rel in zip(layer["types"], layer["files"]):
            if t not in type_items:
                continue
            payload = json.dumps(
                {"type": t, "version": VERSION, "items": type_items[t]},
                ensure_ascii=False,
                indent=2,
            )
            file_texts[rel] = payload

    layers_out = []
    for layer in LAYERS:
        files = []
        for rel in layer["files"]:
            if rel in file_texts:
                base = rel.split("/")[-1].replace(".json", "")
                files.append(
                    {
                        "file": rel,
                        "count": len(type_items.get(base, [])),
                        "sha256": sha256_of(file_texts[rel]),
                    }
                )
        layers_out.append(
            {
                "name": layer["name"],
                "label": layer["label"],
                "depends_on": layer["depends_on"],
                "types": layer["types"],
                "files": files,
            }
        )

    manifest = {
        "package": "tcm-base",
        "title": "中医基础数据包",
        "version": args.version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "整理自《倪海厦人纪》系列及中医经典，仅供学习交流，不构成临床诊疗依据",
        "schema_version": 1,
        "layers": layers_out,
        "whitelist_note": "仅含参考知识表；patients / prescriptions / stock_batches 等业务数据永不打包。",
    }
    file_texts["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2)

    with zipfile.ZipFile(args.dst, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, text in file_texts.items():
            z.writestr(rel, text)

    print(f"已生成 {args.dst}")
    for layer in layers_out:
        c = sum(f["count"] for f in layer["files"])
        print(f"  {layer['name']:8s} {layer['label']:18s} 条目 {c}")
    print(f"  manifest.json 版本 {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
