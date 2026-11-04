# -*- coding: utf-8 -*-
"""校验各经方药味是否都已收录进授权药材库（避免个别生僻药名开方时选不到）。

数据来源：
  - 授权药材库 : app/data/herbs_extended.json （正名 + 异名）
  - 经方数据   : _seed_jingfang.py 中 add() / add_jg() 的 herbs 元组
用法：
  python _check_herbs_coverage.py
"""
import json, os, re

BACKEND = os.path.dirname(os.path.abspath(__file__))
HERB_JSON = os.path.join(BACKEND, "app", "data", "herbs_extended.json")
FANG_FILE = os.path.join(BACKEND, "_seed_jingfang.py")

# ---------- 1. 授权药材库 ----------
with open(HERB_JSON, encoding="utf-8") as f:
    herb_data = json.load(f)

LIB_NAMES = set()          # 正名
LIB_ALIASES = {}           # 异名 -> 正名
for h in herb_data:
    name = h.get("name")
    LIB_NAMES.add(name)
    for a in h.get("aliases") or []:
        LIB_ALIASES[a] = name

# 炮制变体 / 同名异写映射（命中映射说明库内其实已有正名，只是缺该写法）
# value = 库内正名；None 表示这只是"写法归一"，需在库中补正名+异名
VARIANT_MAP = {
    "炙甘草": "甘草", "生甘草": "甘草", "甘草梢": "甘草",
    "制附子": "附子", "炮附子": "附子", "黑顺片": "附子", "熟附片": "附子",
    "附子": "附子",
    "白芍药": "白芍", "赤芍药": "赤芍", "芍药": "白芍",
    "木防己": "防己", "汉防己": "防己",
    "冬瓜子": "冬瓜仁", "冬瓜仁": "冬瓜仁",
    "瓜蒌根": None,           # 库内无"天花粉/瓜蒌根"，需新增
    "天花粉": None,
    "茵陈蒿": "茵陈",          # 库内茵陈正名，异名含"茵陈蒿"（兜底）
    "生地黄": "生地黄", "熟地": "熟地黄", "干地黄": "生地黄",
    "川贝母": "贝母", "浙贝母": "贝母",
    "丹皮": "牡丹皮", "粉丹皮": "牡丹皮",
    "元胡": "延胡索", "延胡索": "延胡索",
    "苁蓉": "肉苁蓉",
    "牛旁子": "牛蒡子",        # 常见错别字
    "山芋": "山药", "淮山药": "山药",
    "锁阳": None,
    "生甘草": "甘草",
}

def in_library(h):
    """返回 (是否收录, 命中正名)。命中正名/异名即视为收录。"""
    if h in LIB_NAMES:
        return True, h
    if h in LIB_ALIASES:
        return True, LIB_ALIASES[h]
    return False, None

# ---------- 2. 解析经方药味 ----------
with open(FANG_FILE, encoding="utf-8") as f:
    src = f.read()

# 删除形如 add_jg("名","效","主","用",[...]) 或 add("名","源","经","效","主","用",[...]) 的行末注释
# add(…)：name 是第 1 个字符串；add_jg(…)：name 是第 1 个字符串
formulas = []  # (name, [herbs...])
# 逐行匹配 add / add_jg 调用（跨多行的调用，name 一定在本行）
for m in re.finditer(r"add(?:_jg)?\(\s*\"([^\"]+)\"", src):
    name = m.group(1)
    # 从该位置起，截取到 add(...) 匹配的括号结束
    start = m.start()
    # 括号配对
    depth = 0
    i = src.find("(", start)
    j = i
    while j < len(src):
        ch = src[j]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    block = src[i:j + 1]
    # 提取所有 ("药名", 剂量, ...) 元组
    herbs = re.findall(r"\(\s*\"([^\"]+)\"\s*,\s*[\d.]+", block)
    # 过滤掉非药材字段的括号（如 "——" 占位、空数组不产生匹配，安全）
    formulas.append((name, herbs))

# ---------- 3. 校验 ----------
missing_by_formula = {}   # name -> [缺药名]
seen_formula = set()
for name, herbs in formulas:
    if not herbs or name in seen_formula:
        continue
    seen_formula.add(name)
    miss = []
    for h in set(herbs):
        ok, _ = in_library(h)
        if not ok and h not in VARIANT_MAP:
            miss.append(h)
    if miss:
        missing_by_formula[name] = sorted(set(miss))

# ---------- 4. 分类汇总 ----------
def categorize(h):
    """返回该缺失药味的建议标签。"""
    if h in VARIANT_MAP:
        # 只有映射到库内已有正名的写法才被排除在缺失列表外，这里只处理 None 映射
        if VARIANT_MAP[h] is None:
            return "同名异写(库内置入正名+异名)"
    return "完全未收录(建议新增药材)"

missing_herb_count = {}
for lst in missing_by_formula.values():
    for h in lst:
        missing_herb_count[h] = missing_herb_count.get(h, 0) + 1

# 使用映射前被排除的写法（炙甘草等）也算"写法缺失"，并统计其实用经方数
write_variants = set()
usage_count = {}          # 药名 -> 出现的经方数
for name, herbs in formulas:
    for h in set(herbs):
        usage_count[h] = usage_count.get(h, 0) + 1
        if h in VARIANT_MAP and VARIANT_MAP[h] is not None and h not in LIB_NAMES and h not in LIB_ALIASES:
            write_variants.add(h)

# 若映射目标是库内也没有的药（如 木防己→防己，而防己未收录），仍按完全未收录统计
def final_status(h):
    """返回 A/B/C 之一。"""
    if h in VARIANT_MAP:
        target = VARIANT_MAP[h]
        if target is not None and (target in LIB_NAMES or target in LIB_ALIASES):
            return "A"
        return "B"
    return "C"

all_issue = set(write_variants) | set(missing_herb_count)

print("=" * 64)
print(f"经方数量（有组成）: {len(formulas)}")
print(f"授权药材库: 正名 {len(LIB_NAMES)} 味, 异名 {len(LIB_ALIASES)} 个")
print(f"含组成但存在选药风险的经方数: {len(missing_by_formula)}")
print("=" * 64)

# 甲类：同名异写（库内已有对应正名，只为"写法"补别名）
same_thing = sorted(h for h in all_issue if final_status(h) == "A")
# 乙类：写法需归一（库内无对应正名，需新增正名）
new_write = sorted(h for h in all_issue if final_status(h) == "B")
# 丙类：完全未收录
truly_missing = sorted(h for h in all_issue if final_status(h) == "C")

if same_thing:
    print("\n【A】同名异写 · 库内已有对应正名，建议仅在药材库补一个异名即可：")
    for h in same_thing:
        print(f"    经方用「{h}」 → 库正名「{VARIANT_MAP[h]}」  (涉及 {usage_count.get(h, 0)} 个经方)")

if new_write:
    print("\n【B】写法归一 · 库内暂无对应正名，建议新增该正名（并合并现有写法）：")
    for h in new_write:
        print(f"    「{h}」 → 建议正名「{VARIANT_MAP[h]}」  (涉及 {usage_count.get(h, 0)} 个经方)")

if truly_missing:
    print(f"\n【C】完全未收录 · 建议在授权药材库新增（共 {len(truly_missing)} 味）：")
    for h in truly_missing:
        print(f"    {h}   (出现在 {usage_count.get(h, 0)} 个经方)")

print("\n" + "=" * 64)
print("按经方列出缺失（A=同名异写 B=需归一 C=完全未收录）:")
for n in sorted(missing_by_formula, key=lambda x: -len(missing_by_formula[x])):
    label = {"A": [], "B": [], "C": []}
    for h in missing_by_formula[n]:
        st = final_status(h)
        if st == "A":
            label["A"].append(f"{h}→{VARIANT_MAP[h]}")
        elif st == "B":
            label["B"].append(h)
        else:
            label["C"].append(h)
    parts = []
    for k in ("C", "B", "A"):
        if label[k]:
            parts.append(k + ":" + "、".join(label[k]))
    print(f"  {n}:  {' | '.join(parts)}")

if not all_issue:
    print("\n校验通过：所有经方药味均已收录进授权药材库。")