"""十问辨证结论的接口契约与「概念统一」回归。

覆盖：体系标记 / 归一化浮点得分能穿过 Pydantic schema、按主经模糊筛选、
统计按主经归并、以及有/无 API Key 两条辨证分支共用同一套规则基线。
"""
import asyncio
import re
import sys
import uuid
from types import SimpleNamespace

from app.routers.stats import (
    HISTORY_CONSTITUTION_BUCKET,
    MERIDIAN_NAMES,
    OTHER_SYNDROME_BUCKET,
    SYNDROME_BUCKETS,
    _syndrome_of,
)
from app.services.ai_diagnosis_service import DiagnosisService
from app.services.constitution_evaluator import evaluate_constitution


def _patient(client, auth_headers):
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"辨证_{uuid.uuid4().hex[:8]}"},
        "registration_fee": 0,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    v = r.json()["visit"]
    return v["patient_id"], v["id"]


SHAOYIN_ANSWERS = {
    "sleep": "normal", "appetite": "normal", "stool": "normal",
    "urine": "clear", "thirst": "warm_water", "hot_cold": "cold_feet",
    "sweat": "normal", "energy": "tired", "sexual": "normal", "menses": "na",
}


def test_submit_and_get_constitution_contract(client, auth_headers):
    pid, vid = _patient(client, auth_headers)
    payload = {"answers": SHAOYIN_ANSWERS, "notes": {}, "visit_id": vid}
    r = client.post(f"/api/v1/patients/{pid}/constitution", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["system"] == "六经偏性（倪海厦十问）"
    assert data["primary_meridians"] == ["少阴"]
    # 归一化得分是浮点；schema 若退回 dict[str,int] 这里会 500 或丢精度
    assert any(isinstance(v, float) for v in data["scores"].values())
    assert data["detail"]["decision"] == "determined"
    assert data["detail"]["primary_meridians"] == data["primary_meridians"]

    got = client.get(f"/api/v1/patients/{pid}/constitution", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["system"] == data["system"]
    assert got.json()["primary_type"] == data["primary_type"]


def test_patient_list_filters_by_meridian(client, auth_headers):
    """患者列表的「证候偏性」筛选按主经模糊匹配，而非旧的九种体质精确等值。"""
    pid, vid = _patient(client, auth_headers)
    r = client.post(f"/api/v1/patients/{pid}/constitution", json={
        "answers": SHAOYIN_ANSWERS, "notes": {}, "visit_id": vid,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    listed = client.get("/api/v1/patients", params={"constitution_type": "少阴"}, headers=auth_headers)
    assert listed.status_code == 200
    assert any(p["id"] == pid for p in listed.json()["items"])


def test_patient_stats_merges_syndrome_by_meridian(client, auth_headers):
    pid, vid = _patient(client, auth_headers)
    client.post(f"/api/v1/patients/{pid}/constitution", json={
        "answers": SHAOYIN_ANSWERS, "notes": {}, "visit_id": vid,
    }, headers=auth_headers)
    r = client.get("/api/v1/stats/patients", params={"days": 30}, headers=auth_headers)
    assert r.status_code == 200
    stats = r.json()["syndrome_stats"]
    allowed = set(MERIDIAN_NAMES) | set(SYNDROME_BUCKETS) | {
        HISTORY_CONSTITUTION_BUCKET, OTHER_SYNDROME_BUCKET,
        "历史记录(未标注体系)", "未评估",
    }
    assert all(s["name"] in allowed for s in stats)
    assert any(s["name"] == "少阴" and s["count"] >= 1 for s in stats)


def test_llm_branch_shares_rule_baseline(monkeypatch):
    """配置 API Key 时也必须注入与规则引擎相同的十问基线，避免两条分支口径分裂。"""
    import app.services.ai_diagnosis_service as mod

    monkeypatch.setattr(mod, "settings", SimpleNamespace(deepseek_api_key="test-key"))
    svc = DiagnosisService()
    captured: dict = {}

    async def fake_call(messages, use_vision=False, usage_ctx=None):
        captured["messages"] = messages
        return "证型：少阴。\n\n```json\n{\"formulas\": []}\n```\n⚠️ 本分析由AI辅助生成，仅供参考。"

    monkeypatch.setattr(svc, "_call_deepseek", fake_call)
    monkeypatch.setattr(svc, "_check_safety_in_reply", lambda reply, db: [])
    ten_answers = {"answers": SHAOYIN_ANSWERS, "notes": {}}
    asyncio.run(svc.analyze(chief_complaint="畏寒肢冷", ten_aspects="十问摘要",
                            ten_answers=ten_answers, db=None))
    joined = "\n".join(str(m) for m in captured["messages"])
    assert "十问六经偏性（规则引擎基线）" in joined
    assert "辨证口径约束" in joined
    rule = evaluate_constitution(SHAOYIN_ANSWERS)
    assert rule["primary_type"] in joined
    assert "景岳全书" in joined and "王琦九种体质" in joined  # 体系隔离条款


def test_syndrome_buckets_match_patient_filter_options():
    """统计归并桶必须与患者列表「证候偏性」下拉选项同口径。"""
    def patient(label, score=None):
        return SimpleNamespace(constitution_type=label, constitution_score=score)

    assert _syndrome_of(patient("平和(无明显偏颇)", {"detail": {"decision": "balanced"}})) == ["平和"]
    assert _syndrome_of(patient("偏性初见(需四诊合参)", {"detail": {"decision": "insufficient"}})) == ["需四诊合参"]
    assert _syndrome_of(patient("证候未定(需四诊合参)", {"detail": {"decision": "undetermined"}})) == ["需四诊合参"]
    assert _syndrome_of(patient("少阴·阳气虚", {"primary_meridians": ["少阴"]})) == ["少阴"]
    assert _syndrome_of(patient("少阴+太阴 合病", {"primary_meridians": ["少阴", "太阴"]})) == ["少阴", "太阴"]
    assert _syndrome_of(patient("阳虚质", {"scores": {}})) == [HISTORY_CONSTITUTION_BUCKET]
    assert _syndrome_of(patient("旧长标签", {"scores": {}})) == [OTHER_SYNDROME_BUCKET]
    assert _syndrome_of(patient(None, None)) == []
    # 旧数据把 detail 写成非字典时不能抛异常，仍按主标签归并
    assert _syndrome_of(patient("少阴·阳气虚", {"detail": "legacy"})) == ["少阴"]
    assert set(SYNDROME_BUCKETS) == {"平和", "需四诊合参"}


def test_balanced_patient_is_filterable_and_counted_as_pinghe(client, auth_headers):
    """筛「平和」能查到、统计也落在「平和」桶：筛选/统计/UI 三者不能各说各话。"""
    pid, vid = _patient(client, auth_headers)
    normal = {k: "normal" for k in SHAOYIN_ANSWERS}
    normal["menses"] = "na"
    r = client.post(f"/api/v1/patients/{pid}/constitution", json={
        "answers": normal, "notes": {}, "visit_id": vid,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["detail"]["decision"] == "balanced"

    listed = client.get("/api/v1/patients", params={"constitution_type": "平和"}, headers=auth_headers)
    assert listed.status_code == 200
    assert any(p["id"] == pid for p in listed.json()["items"])

    stats = client.get("/api/v1/stats/patients", params={"days": 30}, headers=auth_headers).json()["syndrome_stats"]
    assert any(s["name"] == "平和" and s["count"] >= 1 for s in stats)


def test_rag_isolation_marks_variant_titles():
    """另一体系条目标题被改写/带括号时仍要隔离，且不能误伤景岳医案。"""
    import app.services.ai_diagnosis_service as mod

    assert mod._is_other_system("问诊十问歌")
    assert mod._is_other_system("问诊十问歌(景岳全书)")
    assert mod._is_other_system("体质学说(王琦九种体质)")
    assert mod._is_other_system("王琦九种体质辨识")
    assert mod._is_other_system("自定标题", "……王琦九种体质：平和质、阳虚质")
    assert not mod._is_other_system("张景岳—肾阳虚医案", "……右归丸")
    assert not mod._is_other_system("伤寒论—少阳病")


def test_rag_context_puts_other_system_last(monkeypatch):
    """SQL / 向量两路召回都打标，另一体系条目后置且附带体系提示。"""
    import app.services.ai_diagnosis_service as mod

    class FakeQuery:
        def filter(self, *args, **kwargs): return self
        def limit(self, n): return self
        def all(self):
            return [
                SimpleNamespace(title="体质学说(王琦九种体质)", category="经典理论", content="王琦九种体质：平和质……"),
                SimpleNamespace(title="伤寒论—少阳病", category="条文", content="少阳之为病，口苦咽干目眩也。"),
            ]

    class FakeDB:
        def query(self, model): return FakeQuery()

    fake_vector = SimpleNamespace(search=lambda q, top_k=5: [
        {"title": "问诊十问歌(景岳全书)", "category": "诊疗规范", "content": "一问寒热二问汗……"},
        {"title": "伤寒论—太阳病", "category": "条文", "content": "太阳之为病，脉浮……"},
    ])
    monkeypatch.setitem(sys.modules, "app.services.vector_store", SimpleNamespace(vector_store=fake_vector))

    ctx = asyncio.run(DiagnosisService()._retrieve_context("十问", FakeDB()))
    assert "【体系提示】" in ctx
    assert ctx.count(mod._OTHER_SYSTEM_FLAG) == 2
    assert ctx.index("伤寒论—少阳病") < ctx.index(mod._OTHER_SYSTEM_FLAG)
    assert ctx.index("伤寒论—太阳病") < ctx.index(mod._OTHER_SYSTEM_FLAG)


def test_rule_based_branch_shares_engine_with_llm(monkeypatch):
    """无 Key 分支（诊断页降级）与有 Key 分支注入的基线，必须来自同一规则引擎、同一份十问答案。

    这是「双分支口径一致」的核心契约：六经判定只能有一个真相源 evaluate_constitution，
    两条分支不得各自另算，否则同一患者有无 API Key 会给出不同的证型。
    """
    import app.services.ai_diagnosis_service as mod

    ten_answers = {"answers": SHAOYIN_ANSWERS, "notes": {}}

    # 1) 关掉 Key → 走 _rule_based_analyze
    monkeypatch.setattr(mod, "settings", SimpleNamespace(deepseek_api_key=""))
    svc = DiagnosisService()
    res = asyncio.run(svc.analyze(
        chief_complaint="畏寒肢冷", ten_aspects="十问摘要", ten_answers=ten_answers, db=None))
    rule = evaluate_constitution(SHAOYIN_ANSWERS)

    # 主证与引擎输出同源，而不是分支各自另算
    assert res["tcm_syndrome"] == rule["primary_type"]
    assert "少阴" in res["tcm_syndrome"]
    assert "规则推理引擎" in res["syndrome_analysis"]
    m = re.search(r"主归偏性：(\S+)", res["syndrome_analysis"])
    assert m and m.group(1) == rule["primary_type"]

    # 2) 有 Key 分支注入基线的主证，必须与上一步同源（否则两条分支会分化）
    monkeypatch.setattr(mod, "settings", SimpleNamespace(deepseek_api_key="test-key"))
    captured: dict = {}
    async def fake_call(messages, use_vision=False, usage_ctx=None):
        captured["messages"] = messages
        return "证型：少阴。\n\n```json\n{\"formulas\": []}\n```\n⚠️ 本分析由AI辅助生成，仅供参考。"
    monkeypatch.setattr(svc, "_call_deepseek", fake_call)
    monkeypatch.setattr(svc, "_check_safety_in_reply", lambda reply, db: [])
    asyncio.run(svc.analyze(
        chief_complaint="畏寒肢冷", ten_aspects="十问摘要", ten_answers=ten_answers, db=None))
    joined = "\n".join(str(msg) for msg in captured["messages"])
    assert rule["primary_type"] in joined
    assert res["tcm_syndrome"] in joined  # 两条分支共用同一基线字符串
