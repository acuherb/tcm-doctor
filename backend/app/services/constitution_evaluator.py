"""倪海厦经方家问诊十问 → 阴阳/六经偏性推理引擎。

替代原王琦九种体质量表（统计百分比）。采集经方家问诊十问，按倪师判据
将症状映射到寒热/虚实/脏腑/六经，输出偏性画像与临床指向，不做百分比。
"""

# ── 问诊十问判据 ─────────────────────────────────────────────
# hits: 命中时累加的关键词与点数（寒/热/阳虚/阴虚/表阳/心阳/肾阳/脾虚/肝/肺/胃热/血虚/痰饮…）
# meridian: 主归经（六经）
# note: 倪师判据原文解读

QUESTIONS = [
    {
        "key": "sleep", "title": "1. 问睡眠",
        "topic": "你的睡眠如何？是否一觉到天亮？是否每天定时会醒？如果会醒，是几点？是否多梦？",
        "options": [
            {"key": "normal", "label": "一觉到天亮，睡眠安稳", "hits": {}, "meridian": None, "note": "睡眠正常"},
            {"key": "wake_incomplete", "label": "断续睡眠、睡不安稳", "hits": {"肝": 1, "血虚": 1}, "meridian": "厥阴", "note": "肝不藏血或心血虚，魂魄不归心"},
            {"key": "wake_1_3", "label": "持续在1-3点醒来", "hits": {"肝": 2}, "meridian": "厥阴", "note": "肝阴实形成过程中或已成"},
            {"key": "wake_3_5", "label": "持续在3-5点醒来", "hits": {"肺": 2}, "meridian": "太阴", "note": "肺阴实形成过程中或已成"},
            {"key": "dreamy", "label": "多梦纷纭", "hits": {"肝": 1, "血虚": 1}, "meridian": "厥阴", "note": "魂不安藏，心血/肝血不足"},
        ],
    },
    {
        "key": "appetite", "title": "2. 问胃口",
        "topic": "你感觉饿吗？有欲望想吃什么特别的食物或味道吗？还是不饿、完全没胃口？",
        "options": [
            {"key": "normal", "label": "有食欲，食之有味", "hits": {}, "meridian": None, "note": "食欲正常"},
            {"key": "huge", "label": "胃口过大、食不知饱", "hits": {"胃热": 2, "热": 1}, "meridian": "阳明", "note": "阳明腑热"},
            {"key": "no", "label": "没胃口、完全不饿", "hits": {"脾虚": 2}, "meridian": "太阴", "note": "脾脏受损"},
            {"key": "tasteless", "label": "食之无味", "hits": {"脾虚": 1}, "meridian": "太阴", "note": "脾(胰)脏受损"},
            {"key": "no_desire_food", "label": "默默不欲饮食、心烦喜呕", "hits": {"少阳": 2}, "meridian": "少阳", "note": "少阳枢机不利，胆热犯胃"},
        ],
    },
    {
        "key": "stool", "title": "3. 问大便",
        "topic": "你便秘吗？每天有大便吗？大便颜色是什么？是下利吗？很臭还是无味？",
        "options": [
            {"key": "normal", "label": "每日一次，成形，软硬适中", "hits": {}, "meridian": None, "note": "大便正常"},
            {"key": "loose", "label": "大便稀溏", "hits": {"痰饮": 1, "脾虚": 1}, "meridian": "太阴", "note": "中焦肠道有水饮"},
            {"key": "hard", "label": "大便干硬、便秘", "hits": {"胃热": 1, "热": 1}, "meridian": "阳明", "note": "阳明腑实"},
            {"key": "undigested", "label": "下利清谷(有未消化食物)", "hits": {"脾虚": 2, "阳虚": 1}, "meridian": "太阴", "note": "脾阳虚"},
        ],
    },
    {
        "key": "urine", "title": "4. 问小便",
        "topic": "小便什么颜色？频尿吗？还是尿不出来？还是没有尿意？平均一天几次？",
        "options": [
            {"key": "normal", "label": "小便淡黄，通畅", "hits": {}, "meridian": None, "note": "小便正常"},
            {"key": "yellow", "label": "小便黄或深黄", "hits": {"胃热": 1, "热": 1}, "meridian": "阳明", "note": "肠道仍有燥屎"},
            {"key": "clear", "label": "小便清白、量多", "hits": {"寒": 1, "阳虚": 1}, "meridian": "少阴", "note": "里有寒，小肠热度不够"},
        ],
    },
    {
        "key": "thirst", "title": "5. 问口渴",
        "topic": "你很渴吗？如渴想喝什么温度的水？如不渴会忘记喝水吗？还是再怎么喝也不能止渴？",
        "options": [
            {"key": "normal", "label": "时而有口渴，正常饮水", "hits": {}, "meridian": None, "note": "口渴正常"},
            {"key": "no_thirst", "label": "不渴，经常忘记喝水", "hits": {"痰饮": 1}, "meridian": "太阴", "note": "水饮停上焦或胃中仍有不洁食物"},
            {"key": "unquenchable", "label": "口渴，怎么喝都不解渴", "hits": {"胃热": 2, "热": 1}, "meridian": "阳明", "note": "阳明经热，或肾阳虚以致金不能生水"},
            {"key": "cold_water", "label": "口渴，想喝冰水", "hits": {"热": 1}, "meridian": "阳明", "note": "里有热"},
            {"key": "warm_water", "label": "口渴，想喝温水", "hits": {"寒": 1}, "meridian": "少阴", "note": "里有寒"},
            {"key": "bitter_dry", "label": "口苦咽干、不想多饮", "hits": {"少阳": 2}, "meridian": "少阳", "note": "少阳胆火上炎，枢机不利"},
        ],
    },
    {
        "key": "hot_cold", "title": "6. 问寒热",
        "topic": "平时觉得身体很热还是很冷？手脚冰冷吗？睡时身体寒热如何？",
        "options": [
            {"key": "normal", "label": "脚温，睡时无特别感觉", "hits": {}, "meridian": None, "note": "寒热正常"},
            {"key": "cold_feet", "label": "手脚冰冷", "hits": {"心阳": 2, "阳虚": 1}, "meridian": "少阴", "note": "心阳不足，心脏移到小肠之热不足"},
            {"key": "cold_all", "label": "睡时全身冰冷", "hits": {"阳虚": 2, "寒": 1}, "meridian": "少阴", "note": "阳虚"},
            {"key": "hot_upper_cold_lower", "label": "上热下寒", "hits": {"阴阳分格": 2}, "meridian": "厥阴", "note": "阴阳分格"},
            {"key": "mingled", "label": "寒热并结", "hits": {"寒": 1, "热": 1, "阴阳分格": 1}, "meridian": "厥阴", "note": "阴阳相抟"},
            {"key": "alternating", "label": "寒热往来、忽冷忽热，口苦咽干", "hits": {"少阳": 2}, "meridian": "少阳", "note": "少阳枢机不利，半表半里，宜和解"},
            {"key": "hot_all", "label": "全身燥热(长期低烧)", "hits": {"阳不入阴": 2, "阴虚": 1}, "meridian": "厥阴", "note": "阳不入阴"},
        ],
    },
    {
        "key": "sweat", "title": "7. 问汗",
        "topic": "你容易出汗吗？会半夜盗汗吗？会时常流汗不止吗？还是不出汗的身体呢？",
        "options": [
            {"key": "normal", "label": "天热或运动易出汗", "hits": {}, "meridian": None, "note": "汗出正常"},
            {"key": "constant", "label": "汗流不止、动不动就出汗", "hits": {"表阳": 2, "阳虚": 1}, "meridian": "太阳", "note": "表阳虚，不能固表"},
            {"key": "night", "label": "半夜盗汗", "hits": {"表阳": 1, "阴虚": 1}, "meridian": "太阳", "note": "表阳虚，不能固表"},
            {"key": "none", "label": "不怎么出汗、无汗", "hits": {"心阳": 1}, "meridian": "少阴", "note": "心脏功能受损，心不主五液"},
        ],
    },
    {
        "key": "energy", "title": "8. 问体力精神",
        "topic": "精神好吗？还是一直疲惫？早上起床精神奕奕还是无法起床？精神能集中吗？",
        "options": [
            {"key": "normal", "label": "精神好，精力充沛", "hits": {}, "meridian": None, "note": "体力正常"},
            {"key": "tired", "label": "精力不足、容易疲惫", "hits": {"肾阳": 1, "阳虚": 1}, "meridian": "少阴", "note": "天阳不足，肺阳无法下达至肾"},
            {"key": "aortic_listless", "label": "全身疲乏、难以起床", "hits": {"肾阳": 2, "阳虚": 1}, "meridian": "少阴", "note": "先天肾阳不足，故觉全身疲乏"},
        ],
    },
    {
        "key": "sexual", "title": "9. 问性功能",
        "topic": "性功能好吗？男性晨起是否有阳反应？女性乳房是否敏感？",
        "options": [
            {"key": "normal", "label": "晨起有阳反应，性功能正常", "hits": {}, "meridian": None, "note": "性功能正常"},
            {"key": "low", "label": "性功能减退、晨起无阳反应", "hits": {"肾阳": 2}, "meridian": "少阴", "note": "肾阳不足"},
        ],
    },
    {
        "key": "menses", "title": "10. 问女子月经",
        "topic": "无论有无月经，详细说明月经情形：延后还是提前？痛不痛？生过小孩吗？",
        "options": [
            {"key": "na", "label": "不适用 / 无月经(男性或已绝经)", "hits": {}, "meridian": None, "note": "不涉及"},
            {"key": "regular", "label": "月经规律，无不适", "hits": {}, "meridian": None, "note": "月经正常"},
            {"key": "early", "label": "月经提前", "hits": {"热": 1}, "meridian": "阳明", "note": "里热，经期提前是热证"},
            {"key": "late", "label": "月经延后", "hits": {"寒": 1}, "meridian": "少阴", "note": "里寒，经期延后是寒证(心阳不足)"},
            {"key": "pain", "label": "痛经或有瘀血块", "hits": {"寒": 1}, "meridian": "少阴", "note": "里寒现象"},
        ],
    },
]

# 六经 → 倪师思路提示（接方域）
MERIDIAN_SUGGESTIONS = {
    "太阳": "太阳为表，宜发汗解表、调和营卫，量证选用麻黄汤、桂枝汤等方。",
    "阳明": "阳明主里热，宜清泻阳明、通下府实，量证选用白虎汤、承气辈等方。",
    "少阳": "少阳居半表半里，宜和解枢机，小柴胡汤随证加减。",
    "太阴": "太阴为里寒湿，宜温中健脾、去湿化饮，理中、四逆辈为宗。",
    "少阴": "少阴主心肾水火，宜扶阳抑阴、温补心肾，四逆辈、真武汤等兼顾。",
    "厥阴": "厥阴为阴阳交接，寒热错杂，宜调其枢机、燮理阴阳，乌梅丸类方为要。",
}

# 六经并列时的取舍优先级（慢性虚损更常见的经排前，避免被 dict 顺序主导）
MERIDIAN_TIE_PRIORITY = ["少阴", "太阴", "厥阴", "阳明", "太阳", "少阳"]

# 各经可承载的偏性后缀（用于主标签，后缀必须与本经相符，避免跨经硬拼）
MERIDIAN_SUFFIX = {
    "太阳": ["表阳", "心阳"],
    "阳明": ["胃热", "热", "阴虚"],
    "少阳": ["少阳"],
    "太阴": ["脾虚", "痰饮", "寒", "阳虚"],
    "少阴": ["肾阳", "心阳", "阳虚", "寒"],
    "厥阴": ["阴阳分格", "阳不入阴", "肝", "血虚", "热", "寒"],
}

# ── 判定参数 ────────────────────────────────────────────────
# 旧实现「命中即 +1、max>=1 就定主经、并列全算合病」会把 5 个各 1 点的经判成 5 经合病。
# 医疗场景宁可保守：证据不足时明确要求四诊合参，而不是给出一个看似确定的长标签。
MIN_ABNORMAL_QUESTIONS = 2     # 至少 2 项异常才允许定主证
MIN_MAIN_POINTS = 3            # 主经原始点数下限
MIN_LEAD_GAP = 2               # 主经须领先次名至少 2 点
MAX_PRIMARY_MERIDIANS = 2      # 并列最多取 2 经，避免「全经合病」
MAX_SECONDARY = 2              # 倾向最多列 2 经
SECONDARY_RATIO = 0.5          # 倾向至少达到主经的一半
MERIDIAN_ORDER = ["太阳", "阳明", "少阳", "太阴", "少阴", "厥阴"]

SUFFIX_NAMES = {
    "寒": "里寒", "热": "里热", "阳虚": "阳气虚", "阴虚": "阴液亏", "表阳": "表虚不固",
    "心阳": "心阳不足", "肾阳": "肾阳亏虚", "脾虚": "脾虚", "胃热": "胃家热",
    "痰饮": "痰饮", "血虚": "血虚", "肝": "肝失疏泄", "肺": "肺气失和",
    "阴阳分格": "阴阳分格", "阳不入阴": "阳不入阴", "少阳": "枢机不利",
}

# 寒热虚实对立调和：同为显著时提示寒热错杂，不再让两者简单累加成单一热/寒
COLD_KEYS = {"寒"}
HOT_KEYS = {"热", "胃热"}

# 寒热/虚实的自然语言标签
LABELS = {
    "寒": "里寒", "热": "里热", "阳虚": "阳气不足", "阴虚": "阴液不足", "表阳": "表阳不固",
    "心阳": "心阳不足", "肾阳": "肾阳不足", "脾虚": "脾虚", "肝": "肝气/肝血失和", "肺": "肺气失和",
    "胃热": "胃家热/腑热", "痰饮": "痰饮水湿", "血虚": "血虚失养", "阴阳分格": "阴阳分格", "阳不入阴": "阳不入阴",
    "少阳": "少阳枢机不利",
}


def evaluate_constitution(answers: dict, notes: dict | None = None) -> dict:
    """问诊十问 → 六经偏性推理。

    与旧版的区别：
    - 选项的 hits 点数真正参与六经计分（不再一律 +1）；
    - 按「异常题数」归一化，男女/不适用题数不同仍可比；
    - 设主证阈值 + 领先差，证据不足时输出「需四诊合参」而不是长串合病；
    - 并列最多 2 经、后缀只在单主经时拼，杜绝跨经硬拼；
    - 寒热并见落地到主标签（寒热错杂），不再只写一句 findings；
    - detail 同步主经/得分/判定依据，供前端与统计使用。
    """
    dims: dict[str, int] = {}          # 寒热虚实脏腑累计点数
    raw: dict[str, int] = {}           # 六经原始点数（按 hits 加权）
    findings: list[str] = []
    notes = notes or {}
    custom_notes: list[str] = []
    invalid_answers: list[str] = []
    abnormal_count = 0
    answered_count = 0
    rank = {m: i for i, m in enumerate(MERIDIAN_TIE_PRIORITY)}

    for q in QUESTIONS:
        value = answers.get(q["key"])
        extra_note = (notes.get(q["key"]) or "").strip()
        if value is not None:
            answered_count += 1

        # 自填描述保留原文，但不自动定性、不计分
        if value == "custom" or (value is None and extra_note):
            if extra_note:
                custom_notes.append(f"《{q['title']}》{extra_note}")
                findings.append(f"《{q['title']}》 自述（未纳入计分）：{extra_note}")
            continue
        if value is None:
            continue
        chosen = next((o for o in q["options"] if o["key"] == value), None)
        if not chosen:
            invalid_answers.append(f"{q['key']}={value}")
            if extra_note:
                findings.append(f"《{q['title']}》 补充（未纳入计分）：{extra_note}")
            continue

        hits = chosen.get("hits") or {}
        for hit, point in hits.items():
            dims[hit] = dims.get(hit, 0) + point
        meridian = chosen.get("meridian")
        weight = sum(hits.values())
        if meridian and weight:
            raw[meridian] = raw.get(meridian, 0) + weight
            abnormal_count += 1
        # 正常选项（无 hits、无归经）不写 findings，也不占异常题数
        if (hits or meridian) and chosen.get("note"):
            findings.append(f"《{q['title']}》 {chosen['note']}")
        if extra_note:
            findings.append(f"《{q['title']}》 补充（未纳入计分）：{extra_note}")

    if invalid_answers:
        findings.append(f"《校验》 {len(invalid_answers)} 项答案不在题库中，未计分：{'、'.join(invalid_answers[:5])}")

    cold, hot = cold_points(dims), hot_points(dims)
    mixed = (cold >= 1 and hot >= 1) or dims.get("阴阳分格", 0) >= 1 or dims.get("阳不入阴", 0) >= 1
    if mixed:
        findings.append("《寒热》 寒热/阴阳错杂，按错杂证处理，不再单向归为里寒或里热。")

    # 按「异常题数」归一化成平均点数(0~3)供前端条块展示：男女/不适用题数不同仍可比；
    # 原始点数另存 detail.raw_points 用于审计与阈值判定
    scores = {m: round(raw.get(m, 0) / max(abnormal_count, 1), 2) for m in MERIDIAN_ORDER}
    ranked_meridians = sorted(
        ((m, raw[m]) for m in MERIDIAN_ORDER if raw.get(m, 0) > 0),
        key=lambda x: (-x[1], rank.get(x[0], 99)),
    )
    top = ranked_meridians[0][1] if ranked_meridians else 0
    second = ranked_meridians[1][1] if len(ranked_meridians) > 1 else 0

    if abnormal_count == 0:
        decision, primary_meridians = "balanced", []
        primary_type = "平和(无明显偏颇)"
    elif abnormal_count < MIN_ABNORMAL_QUESTIONS:
        decision, primary_meridians = "insufficient", []
        primary_type = "偏性初见(需四诊合参)"
        findings.append("《判定》 仅 1 项异常，不足以定六经主证，请结合舌脉四诊。")
    elif top < MIN_MAIN_POINTS or (len(ranked_meridians) > 1 and top - second < MIN_LEAD_GAP):
        decision, primary_meridians = "undetermined", []
        primary_type = "证候未定(需四诊合参)"
        findings.append("《判定》 各经点数分散或偏低，未形成主证，不做合病推断，请结合舌脉四诊。")
    else:
        decision = "determined"
        tied = [m for m, c in ranked_meridians if c == top]
        primary_meridians = sorted(tied, key=lambda m: rank.get(m, 99))[:MAX_PRIMARY_MERIDIANS]
        primary_type = _compose_primary(dims, primary_meridians, mixed)

    secondary_types = [
        m for m, c in ranked_meridians
        if m not in primary_meridians and c >= 2 and c >= top * SECONDARY_RATIO
    ][:MAX_SECONDARY]

    if decision == "determined":
        suggestion = " · ".join(MERIDIAN_SUGGESTIONS[m] for m in primary_meridians)
    elif decision == "balanced":
        suggestion = "四肢五官和缓，阴阳调平，未见明显偏颇。"
    else:
        suggestion = "十问尚未形成可判定的六经主证，请结合舌脉、四诊与病程再定，不宜径投经方。"

    ranked_dims = sorted(dims.items(), key=lambda x: (-x[1], str(x[0])))
    detail = {
        "dims": dict(dims),
        "labels": [LABELS.get(k, k) for k, _ in ranked_dims if k in LABELS],
        "custom_notes": custom_notes,
        "primary_meridians": list(primary_meridians),
        "scores": scores,
        "raw_points": {m: raw.get(m, 0) for m in MERIDIAN_ORDER},
        "answered_count": answered_count,
        "abnormal_count": abnormal_count,
        "invalid_answers": invalid_answers,
        "decision": decision,
        "cold_points": cold,
        "hot_points": hot,
        "system": "六经偏性（倪海厦十问）",
    }

    return {
        "primary_type": primary_type,
        "primary_meridians": list(primary_meridians),
        "scores": scores,
        "secondary_types": secondary_types,
        "findings": findings,
        "suggestion": suggestion,
        "detail": detail,
        # 明确体系，避免与王琦九种体质混用
        "system": "六经偏性（倪海厦十问）",
    }


def _compose_primary(dims: dict[str, int], primary_meridians: list[str],
                     mixed: bool = False) -> str:
    """组合主标签。合病只列经名，不拼后缀，避免把 A 经的维度硬贴到 B 经上。"""
    if not primary_meridians:
        return "平和(无明显偏颇)"
    head = "+".join(primary_meridians) if len(primary_meridians) > 1 else primary_meridians[0]
    if mixed:
        return f"{head}·寒热错杂"
    if len(primary_meridians) > 1:
        return f"{head} 合病"
    allowed = set(MERIDIAN_SUFFIX.get(primary_meridians[0], []))
    ranked = sorted(dims.items(), key=lambda x: (-x[1], str(x[0])))
    suffix = next((SUFFIX_NAMES[k] for k, _ in ranked if k in allowed and k in SUFFIX_NAMES), "")
    return f"{head}·{suffix}" if suffix else head


def cold_points(dims: dict[str, int]) -> int:
    """寒象总点数（仅用于寒热错杂提示，不改动各维度原始点数）。"""
    return sum(v for k, v in dims.items() if k in COLD_KEYS)


def hot_points(dims: dict[str, int]) -> int:
    """热象总点数。"""
    return sum(v for k, v in dims.items() if k in HOT_KEYS)
