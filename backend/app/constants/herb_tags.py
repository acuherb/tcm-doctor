"""药材标签维度与受控词表（按《神农本草经》三品 + 倪海厦重视的性味归经毒性）

设计原则：
- 受控维度（三品 / 四气 / 五味 / 归经 / 升降浮沉）词表固定，写入时清洗，避免字典越填越乱；
- 四气（nature）允许“微寒/大热”等变体，列为单值但不过度强约束；
- 通用标签 tags 为自由标签（功效分类 / 主治证型 / 经方常用 / 产地 / 炮制），不强制词表。
"""
from typing import Any

# 受控维度：multi=False 为单值，True 为多值标签
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

# 通用标签常用建议（非强制）
HERB_COMMON_TAG_SUGGESTIONS: list[str] = [
    "解表药", "清热药", "泻下药", "祛风湿药", "化湿药", "利水渗湿药", "温里药",
    "理气药", "消食药", "止血药", "活血化瘀药", "化痰止咳平喘药", "安神药",
    "平肝息风药", "开窍药", "补虚药", "收涩药", "涌吐药",
]

# 仅对固定小词表的维度做清洗（nature 允许多变体，留作自由）
_CONTROLLED = ("grade", "flavors", "meridians", "directions")


def sanitize_herb_tags(data: dict) -> dict:
    """清洗药材标签：对受控维度剔除不在词表内的值，多值维度合并为去重列表。

    data 为可变的字段字典（如 Pydantic model_dump 的结果）。
    """
    for dim, spec in HERB_TAG_DIMENSIONS.items():
        if dim not in _CONTROLLED or dim not in data or data[dim] is None:
            continue
        vals = data[dim]
        if not isinstance(vals, list):
            vals = [vals]
        allowed = set(spec["options"])
        cleaned: list[Any] = []
        for v in vals:
            if v in allowed and v not in cleaned:
                cleaned.append(v)
        data[dim] = cleaned if spec["multi"] else (cleaned[0] if cleaned else None)
    return data
