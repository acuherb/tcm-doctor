"""操作日志可读性回归。

挂号收费模块上线后，日志里出现过「新增registration/详情/call」这样的半英文动作，
以及显式审计与中间件自动采集各写一条的重复记录。这里锁死统一后的行为：
动作名全中文、关键业务动作可读、每个请求只留一条、历史数据读取时自动规范化。
"""
import json
import uuid

from app.database import SessionLocal
from app.main import _extract_target
from app.models.log import OperationLog
from app.utils.action_labels import display_action, resolve_action


def test_registration_and_billing_actions_are_readable():
    cases = [
        ("POST", "/api/v1/registration", "挂号登记"),
        ("GET", "/api/v1/registration/queue", "查看挂号队列"),
        ("GET", "/api/v1/registration/options", "查看挂号选项"),
        ("GET", "/api/v1/registration/12", "查看挂号详情"),
        ("PATCH", "/api/v1/registration/12", "更新挂号状态"),
        ("POST", "/api/v1/registration/12/call", "叫号接诊"),
        ("POST", "/api/v1/registration/12/complete", "完成就诊"),
        ("POST", "/api/v1/registration/12/revert", "撤销就诊状态"),
        ("POST", "/api/v1/billing/charges", "开具收费单"),
        ("GET", "/api/v1/billing/charges", "查看收费单"),
        ("GET", "/api/v1/billing/charges/8", "查看收费单详情"),
        ("GET", "/api/v1/billing/charges/stats/summary", "查看收费汇总"),
        ("POST", "/api/v1/billing/charges/8/pay", "收款"),
        ("POST", "/api/v1/billing/charges/8/refund", "退费"),
        ("POST", "/api/v1/billing/charges/8/cancel", "作废收费单"),
    ]
    for method, path, expected in cases:
        assert resolve_action(method, path) == expected, (method, path, resolve_action(method, path))
    # 常规业务路径不得再出现接口前缀或裸英文动词
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        for path in ("/api/v1/patients/3", "/api/v1/prescriptions/5", "/api/v1/stock/items/2"):
            action = resolve_action(method, path)
            assert "api/v1" not in action
            assert action.startswith(("查看", "新增", "修改", "删除"))


def test_display_action_normalizes_legacy_values():
    # 历史落库的路径 / 半英文动作：按 endpoint 重新解析成当前口径
    assert display_action("/api/v1/registration/12/call", "POST",
                          "/api/v1/registration/12/call") == "叫号接诊"
    assert display_action("新增registration/详情/call", "POST",
                          "/api/v1/registration/12/call") == "叫号接诊"
    # 旧版中间件只落业务名词：补上请求方法对应的动词
    assert display_action("患者", "POST") == "新增患者"
    assert display_action("收费单", "DELETE", "/api/v1/billing/charges/8") == "删除收费单"
    # 显式审计的完整动作原样保留
    assert display_action("撤销就诊状态", "POST") == "撤销就诊状态"
    assert display_action("登录失败", "POST") == "登录失败"


def test_extract_target_shows_patient_and_fee():
    body = json.dumps({"new_patient": {"name": "张三"}, "registration_fee": 20, "paid": 20}).encode()
    assert _extract_target(body) == "张三 ¥20"
    body = json.dumps({"patient_id": 7, "registration_fee": 0}).encode()
    assert _extract_target(body) == "患者 #7 ¥0"
    # 敏感字段不会进入日志对象摘要
    body = json.dumps({"new_patient": {"name": "李四", "phone": "13800138000"}, "paid": 30}).encode()
    assert "13800138000" not in (_extract_target(body) or "")


def test_registration_writes_one_readable_log(client, auth_headers):
    """一次挂号只留一条日志，动作、患者、金额都能直接看懂。"""
    name = f"日志可读_{uuid.uuid4().hex[:6]}"
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": name}, "registration_fee": 20,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    s = SessionLocal()
    try:
        rows = (s.query(OperationLog)
                .filter(OperationLog.target.like(f"%{name}%"))
                .all())
        assert len(rows) == 1, [(x.action, x.target) for x in rows]
        assert rows[0].action == "挂号登记"
        assert "¥20" in (rows[0].target or "")
        assert rows[0].method == "POST" and rows[0].status_code == 200
    finally:
        s.close()


def test_log_meta_and_csv_use_readable_action(client, auth_headers):
    r = client.get("/api/v1/system/logs/meta", headers=auth_headers)
    assert r.status_code == 200
    actions = r.json()["actions"]
    assert actions and all(isinstance(a, dict) and a["label"] and a["value"] for a in actions)
    assert any(a["label"] == "挂号登记" for a in actions)

    csv_resp = client.get("/api/v1/system/logs/export", headers=auth_headers)
    assert csv_resp.status_code == 200
    text = csv_resp.content.decode("utf-8-sig")
    assert "挂号登记" in text
    assert "registration" not in text.split("\n", 1)[0]  # 表头全中文
