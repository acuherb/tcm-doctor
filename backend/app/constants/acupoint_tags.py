"""穴位属性维度与受控词表（参照 herb_tags 范式）

设计原则：
- 受控维度（来源 / 归经 / 部位）的候选项「由数据字典接管」：
  以 DictionaryTerm(term_type='acupoint_tag', category=维度中文名) 存储，可在「字典管理」页增删；
- 本常量仅保留「有哪些维度、中文名、是否多选、默认词表（作为字典为空时的回退与种子）」；
- 三体系（针灸大成 / 董氏奇穴 / 倪海厦·针灸）混排，所有维度选项均可通过字典自定义，
  未来新增针灸流派无需改动代码。

注意：「类型」不纳入受控维度。五输穴（井荥输经合）的五行属性按「阴经/阳经」两套体系
分别对应，同名类型在不同经络下五行含义不同，无法用固定选项表达，因此 point_type 采用
自由文本录入（如「井穴·木」「荥穴·火」「原穴」），由医生按经络实际填写。
"""
from typing import Any

# 受控维度：key -> {label 中文名, multi 是否多选, options 默认词表(种子/回退)}
ACUPOINT_TAG_DIMENSIONS: dict[str, dict[str, Any]] = {
    "source": {
        "label": "来源",
        "multi": False,
        "options": ["针灸大成", "董氏奇穴", "倪海厦·针灸", "通用"],
    },
    "meridian": {
        "label": "归经",
        "multi": False,
        "options": [
            "手太阴肺经", "手阳明大肠经", "足阳明胃经", "足太阴脾经",
            "手少阴心经", "手太阳小肠经", "足太阳膀胱经", "足少阴肾经",
            "手厥阴心包经", "手少阳三焦经", "足少阳胆经", "足厥阴肝经",
            "任脉", "督脉", "经外奇穴", "董氏奇穴",
        ],
    },
    "region": {
        "label": "部位",
        "multi": False,
        "options": [
            "头面", "上肢", "下肢", "前胸", "后背", "腰骶",
            "一一部位", "二二部位", "三三部位", "四四部位", "五五部位", "六六部位",
            "七七部位", "八八部位", "九九部位", "十十部位", "胸腹部位", "后背部位",
        ],
    },
}

# 维度中文名 -> key（用于把数据字典按 category 归类回维度）
ACUPOINT_TAG_DIMENSION_BY_LABEL: dict[str, str] = {
    v["label"]: k for k, v in ACUPOINT_TAG_DIMENSIONS.items()
}

# 维度顺序（字典管理页 / 弹窗下拉排序用）
ACUPOINT_TAG_ORDER: list[str] = ["来源", "归经", "部位"]