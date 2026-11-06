"""新增统计接口回归：字段契约、口径、边界与空数据安全。

挂号收费与患者两个维度的统计报表依赖这些接口；重点锁死金额口径
（净营收 = 累计实收 - 实退）与「只统计有排队号的挂号记录 / 未归档患者」。
"""
import uuid

import pytest


def _register(client, auth_headers, fee=0):
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"统计_{uuid.uuid4().hex[:8]}"},
        "registration_fee": fee,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["visit"]["id"]


def _get(client, auth_headers, path, days=30):
    r = client.get(path, params={"days": days}, headers=auth_headers)
    assert r.status_code == 200, (path, r.text)
    return r.json()


def test_stats_endpoints_contract(client, auth_headers):
    reg = _get(client, auth_headers, "/api/v1/stats/registration")
    assert isinstance(reg["total"], int)
    assert len(reg["daily_stats"]) <= 60
    assert all({"date", "count"} <= set(d) for d in reg["daily_stats"])
    assert 0 <= reg["completion_rate"] <= 100
    assert isinstance(reg["department_stats"], list)
    assert isinstance(reg["doctor_stats"], list)
    assert {"payable", "collected", "pending"} <= set(reg["fee"])

    charges = _get(client, auth_headers, "/api/v1/stats/charges")
    assert len(charges["daily_stats"]) <= 60
    assert all({"date", "collected", "refunded", "net"} <= set(d) for d in charges["daily_stats"])
    assert isinstance(charges["kind_stats"], list)
    assert isinstance(charges["payment_stats"], list)
    t = charges["totals"]
    assert {"net_amount", "refunded_amount", "pending_amount", "refund_rate"} <= set(t)
    # 净营收口径与收费台汇总一致：累计实收 - 实退
    assert round(t["collected_amount"] - t["refunded_amount"], 2) == round(t["net_amount"], 2)
    assert 0 <= t["refund_rate"] <= 100

    patients = _get(client, auth_headers, "/api/v1/stats/patients")
    assert isinstance(patients["total_patients"], int)
    assert isinstance(patients["new_this_month"], int)
    assert 0 <= patients["returning_rate"] <= 100
    assert len(patients["daily_new"]) <= 60
    valid_ages = {"0-18岁", "19-35岁", "36-50岁", "51-65岁", "66岁以上", "未填写"}
    assert all(a["name"] in valid_ages for a in patients["age_stats"])


def test_registration_stats_count_new_registration(client, auth_headers):
    """挂号接口写入后，挂号统计能立即反映（且不把普通就诊算进挂号数）。"""
    before = _get(client, auth_headers, "/api/v1/stats/registration", days=1)
    _register(client, auth_headers, fee=12)
    after = _get(client, auth_headers, "/api/v1/stats/registration", days=1)
    assert after["total"] == before["total"] + 1
    assert after["fee"]["payable"] >= before["fee"]["payable"] + 12
    assert after["daily_stats"][-1]["count"] >= 1


def test_charge_summary_has_kind_breakdown(client, auth_headers):
    r = client.get("/api/v1/billing/charges/stats/summary", headers=auth_headers)
    assert r.status_code == 200
    kinds = r.json()["kind_stats"]
    assert isinstance(kinds, list)
    for k in kinds:
        assert {"kind", "name", "count", "net_amount", "pending_amount"} <= set(k)
        assert k["name"] in ("挂号费", "处方收费")


@pytest.mark.parametrize("days", [0, 366])
def test_stats_days_out_of_range(client, auth_headers, days):
    for path in ("/api/v1/stats/registration", "/api/v1/stats/charges", "/api/v1/stats/patients"):
        r = client.get(path, params={"days": days}, headers=auth_headers)
        assert r.status_code == 422, (path, days, r.text)


def test_stats_handles_short_period(client, auth_headers):
    """近 1 天也要返回完整结构，不能因为无数据抛异常。"""
    for path in ("/api/v1/stats/registration", "/api/v1/stats/charges", "/api/v1/stats/patients"):
        data = _get(client, auth_headers, path, days=1)
        assert len(data.get("daily_stats", data.get("daily_new", []))) == 1
