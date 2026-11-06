"""问诊十问 → 六经偏性推理引擎回归。

锁死旧实现的几个确定性缺陷：命中即 +1 抹平权重、单症即定主经、
并列全取导致 5 经合病、少阳不可达、后缀跨经硬拼、detail 缺主经字段，
以及前端题库与后端判据题库漂移。
"""
import re
from pathlib import Path

from app.services.constitution_evaluator import (
    QUESTIONS, MERIDIAN_ORDER, evaluate_constitution,
)


def _normal_answers() -> dict:
    return {
        q["key"]: next(o["key"] for o in q["options"] if o["key"] in ("normal", "na", "regular"))
        for q in QUESTIONS
    }


def _answers(**overrides) -> dict:
    return {**_normal_answers(), **overrides}


def test_all_normal_is_balanced():
    r = evaluate_constitution(_answers())
    assert r["primary_type"] == "平和(无明显偏颇)"
    assert r["primary_meridians"] == []
    assert r["detail"]["decision"] == "balanced"
    assert all(v == 0 for v in r["scores"].values())


def test_single_abnormal_does_not_set_primary():
    """只有 1 项异常时不得直接定主经，须要求四诊合参。"""
    r = evaluate_constitution(_answers(hot_cold="cold_feet"))
    assert r["primary_meridians"] == []
    assert "四诊合参" in r["primary_type"]
    assert r["detail"]["decision"] == "insufficient"
    assert r["detail"]["abnormal_count"] == 1


def test_scattered_single_hits_are_not_multi_meridian_disease():
    """5 个经各 1 点，旧版会输出 5 经合病；现在应判为证候未定。"""
    r = evaluate_constitution(_answers(
        sleep="wake_1_3", appetite="no", stool="hard", urine="clear", sweat="constant",
    ))
    assert r["primary_meridians"] == []
    assert "四诊合参" in r["primary_type"]
    assert "+" not in r["primary_type"]
    assert r["detail"]["decision"] == "undetermined"


def test_typical_shaoyin_is_determined():
    r = evaluate_constitution(_answers(
        hot_cold="cold_feet", urine="clear", energy="tired",
    ))
    assert r["detail"]["decision"] == "determined"
    assert r["primary_meridians"] == ["少阴"]
    assert r["primary_type"].startswith("少阴·")
    assert r["detail"]["raw_points"]["少阴"] >= 3


def test_shaoyang_is_reachable():
    """旧版 40 个选项无一映射少阳，六经缺一经。"""
    assert any(o.get("meridian") == "少阳" for q in QUESTIONS for o in q["options"])
    r = evaluate_constitution(_answers(
        hot_cold="alternating", thirst="bitter_dry", appetite="no_desire_food",
    ))
    assert r["primary_meridians"] == ["少阳"]
    assert r["scores"]["少阳"] > 0
    assert r["detail"]["decision"] == "determined"


def test_hits_weight_is_not_flattened():
    """2 点判据与 1 点判据对六经得分的贡献必须不同。"""
    strong = evaluate_constitution(_answers(
        hot_cold="cold_feet", urine="clear", energy="aortic_listless",
    ))
    weak = evaluate_constitution(_answers(
        hot_cold="cold_feet", urine="clear", energy="tired",
    ))
    assert strong["detail"]["raw_points"]["少阴"] > weak["detail"]["raw_points"]["少阴"]


def test_scores_are_normalized_by_abnormal_count():
    """归一化后得分不超过单题最大点数；男女「不适用」题数不同仍用同一口径。"""
    male = evaluate_constitution(_answers(
        hot_cold="cold_feet", urine="clear", menses="na", sexual="low",
    ))
    female = evaluate_constitution(_answers(
        hot_cold="cold_feet", urine="clear", menses="late", sexual="low",
    ))
    for r in (male, female):
        assert all(0 <= v <= 3 for v in r["scores"].values())
    assert male["primary_meridians"] == female["primary_meridians"] == ["少阴"]


def test_cold_hot_mixed_is_reflected_in_primary_label():
    """寒热并见时主标签不再单向输出里寒/里热，而是明确标错杂。"""
    r = evaluate_constitution(_answers(
        thirst="cold_water", urine="clear", hot_cold="cold_feet", energy="tired",
    ))
    assert r["detail"]["decision"] == "determined"
    assert "寒热错杂" in r["primary_type"]
    assert "·里寒" not in r["primary_type"] and "·里热" not in r["primary_type"]
    assert any("寒热" in f for f in r["findings"])


def test_combined_meridians_do_not_get_cross_meridian_suffix():
    """合病只列经名，不把 A 经的偏性后缀硬拼到 B 经上。"""
    r = evaluate_constitution(_answers(
        sleep="wake_1_3", appetite="huge", stool="loose", urine="clear",
        thirst="unquenchable", hot_cold="cold_feet", energy="tired",
    ))
    if len(r["primary_meridians"]) > 1:
        assert "合病" in r["primary_type"] or "寒热错杂" in r["primary_type"]
        assert "·" not in r["primary_type"].split()[-1]


def test_detail_exposes_decision_basis():
    r = evaluate_constitution(_answers(hot_cold="cold_feet", urine="clear"))
    d = r["detail"]
    assert d["primary_meridians"] == r["primary_meridians"]
    assert d["scores"] == r["scores"]
    assert d["system"] == r["system"] == "六经偏性（倪海厦十问）"
    assert set(MERIDIAN_ORDER) == set(d["raw_points"])
    assert d["decision"] in ("balanced", "insufficient", "undetermined", "determined")


def test_invalid_keys_and_custom_notes_are_not_silently_dropped():
    r = evaluate_constitution(
        _answers(sleep="not_in_question_bank", appetite="custom"),
        notes={"appetite": "自述饭后腹胀"},
    )
    assert "sleep=not_in_question_bank" in r["detail"]["invalid_answers"]
    assert any("未纳入计分" in f for f in r["findings"])


def test_frontend_and_backend_question_banks_match():
    """前端渲染题库与后端判据题库必须逐题逐选项一致，避免新增判据只改一端。"""
    ts_path = Path(__file__).resolve().parents[2] / "frontend/src/utils/tenAspectsQuestions.ts"
    ts = ts_path.read_text()
    ts_keys = set(re.findall(r"key: '([^']+)'", ts))
    py_keys = {q["key"] for q in QUESTIONS} | {o["key"] for q in QUESTIONS for o in q["options"]}
    assert ts_keys == py_keys, f"仅后端有: {py_keys - ts_keys} / 仅前端有: {ts_keys - py_keys}"
    assert len(QUESTIONS) == 10
