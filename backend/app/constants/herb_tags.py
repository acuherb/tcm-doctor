"""药材标签维度与受控词表（按《神农本草经》性味）

设计原则：
- 受控维度（四气 / 五味）的候选项「由数据字典接管」：
  以 DictionaryTerm(term_type='herb_tag', category=维度中文名) 存储，可在「字典管理」页增删；
- 本常量仅保留「有哪些维度、中文名、是否多选、默认词表（作为字典为空时的回退与种子）」；
- 四气（nature）允许多变体，列为单值但不强约束，词表仅作下拉建议；
- 三品 / 归经 / 升降浮沉 已按产品决策从药材字典中移除（不再作为维度/筛选/编辑项）。
"""
from typing import Any

# 受控维度：key -> {label 中文名, multi 是否多选, options 默认词表(种子/回退)}
HERB_TAG_DIMENSIONS: dict[str, dict[str, Any]] = {
    "nature": {
        "label": "四气",
        "multi": False,
        "options": ["大寒", "寒", "微寒", "凉", "平", "微温", "温", "热", "大热"],
    },
    "flavors": {"label": "五味", "multi": True, "options": ["辛", "甘", "酸", "苦", "咸", "淡", "涩"]},
}

# 维度中文名 -> key（用于把数据字典按 category 归类回维度）
HERB_TAG_DIMENSION_BY_LABEL: dict[str, str] = {v["label"]: k for k, v in HERB_TAG_DIMENSIONS.items()}

# 仅对固定小词表的维度做清洗（nature 允许多变体，留作自由）
_CONTROLLED = ("flavors",)


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
