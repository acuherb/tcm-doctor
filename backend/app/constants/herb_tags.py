"""药材标签维度与受控词表（按《神农本草经》三品 + 倪海厦重视的性味归经毒性）

设计原则：
- 受控维度（三品 / 四气 / 五味 / 归经 / 升降浮沉）的候选项「由数据字典接管」：
  以 DictionaryTerm(term_type='herb_tag', category=维度中文名) 存储，可在「字典管理」页增删；
- 本常量仅保留「有哪些维度、中文名、是否多选、默认词表（作为字典为空时的回退与种子）」；
- 通用标签 tags 为自由标注（主治证型 / 经方常用 / 产地 / 炮制），不强制词表；
- 四气（nature）允许多变体，列为单值但不强约束，词表仅作下拉建议。
"""
from typing import Any

# 受控维度：key -> {label 中文名, multi 是否多选, options 默认词表(种子/回退)}
HERB_TAG_DIMENSIONS: dict[str, dict[str, Any]] = {
    "grade": {"label": "三品", "multi": False, "options": ["上品", "中品", "下品"]},
    "nature": {
        "label": "四气",
        "multi": False,
        "options": ["大寒", "寒", "微寒", "凉", "平", "微温", "温", "热", "大热"],
    },
    "flavors": {"label": "五味", "multi": True, "options": ["辛", "甘", "酸", "苦", "咸", "淡", "涩"]},
    "meridians": {
        "label": "归经",
        "multi": True,
        "options": ["心", "肝", "脾", "肺", "肾", "胃", "大肠", "小肠", "膀胱", "三焦", "胆", "心包"],
    },
    "directions": {"label": "升降浮沉", "multi": True, "options": ["升", "降", "浮", "沉"]},
}

# 维度中文名 -> key（用于把数据字典按 category 归类回维度）
HERB_TAG_DIMENSION_BY_LABEL: dict[str, str] = {v["label"]: k for k, v in HERB_TAG_DIMENSIONS.items()}

# 仅对固定小词表的维度做清洗（nature 允许多变体，留作自由）
_CONTROLLED = ("grade", "flavors", "meridians", "directions")


def sanitize_herb_tags(data: dict, allowed: dict | None = None) -> dict:
    """清洗药材标签：对受控维度剔除不在词表内的值，多值维度合并为去重列表。

    - allowed 为可选 dict(key -> set/list)，通常来自数据字典(DictionaryTerm)；
      提供时以数据字典为权威；某维度词表为空时不做剔除，避免误清空已有数据。
    - allowed 为 None 时回退到常量默认词表（兼容离线/未播种场景）。
    """
    for dim, spec in HERB_TAG_DIMENSIONS.items():
        if dim not in _CONTROLLED or dim not in data or data[dim] is None:
            continue
        vals = data[dim] if isinstance(data[dim], list) else [data[dim]]
        if allowed is not None:
            allowed_set = set(allowed.get(dim) or [])
        else:
            allowed_set = set(spec.get("options", []))
        if not allowed_set:
            continue  # 词表为空 -> 不剔除，保留原值
        cleaned: list[Any] = []
        for v in vals:
            if v in allowed_set and v not in cleaned:
                cleaned.append(v)
        data[dim] = cleaned if spec["multi"] else (cleaned[0] if cleaned else None)
    return data
