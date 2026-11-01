"""穴位字典重构（acupoint_tag）相关测试：维度聚合接口 + 新字段落库

直接复用 conftest 的 client / auth_headers / db_session 夹具（带管理员 token），
与全局鉴权中间件（require_admin_for_writes）保持一致。
"""
from app.main import app  # noqa: F401  确保 app 被引用
from app.database import SessionLocal
from app.models.acupuncture import Acupoint


def test_acupoint_tag_meta_dimensions(client, auth_headers):
    """/acupoints/tags/meta 返回 来源/归经/部位/类型 四维度（种子已写入 54 条 acupoint_tag）。"""
    r = client.get("/api/v1/acupoints/tags/meta", headers=auth_headers)
    assert r.status_code == 200, r.text
    dims = r.json()["dimensions"]
    assert set(dims.keys()) == {"source", "meridian", "region", "point_type"}
    assert dims["source"]["label"] == "来源"
    opts = dims["source"]["options"]
    assert len(opts) == 4
    # options 现为 {value,label,description,color} 对象
    assert all({"value", "label", "description", "color"} <= set(o.keys()) for o in opts)
    def has(dimension, name):
        return any(o["value"] == name for o in dims[dimension]["options"])
    assert has("meridian", "董氏奇穴")
    assert has("region", "一一部位")
    assert has("point_type", "特效穴")


def test_acupoint_create_with_new_fields(client, auth_headers, db_session):
    """新增穴位能正确落库 source/region/indications/needling_method 等新字段。"""
    payload = {
        "name": "测试穴X", "meridian": "足阳明胃经", "region": "下肢",
        "source": "针灸大成", "point_type": "合穴",
        "location": "测试定位", "efficacy": "测试功效",
        "indications": "胃痛、腹胀", "needling_method": "直刺1寸",
    }
    r = client.post("/api/v1/acupoints", json=payload, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert data["source"] == "针灸大成"
    assert data["region"] == "下肢"
    assert data["indications"] == "胃痛、腹胀"
    assert data["needling_method"] == "直刺1寸"

    # 列表筛选：按分部（meridian+region）过滤
    q = client.get("/api/v1/acupoints", params={"meridian": "足阳明胃经", "region": "下肢"}, headers=auth_headers)
    names = [a["name"] for a in q.json()]
    assert "测试穴X" in names

    # 清理
    db_session.query(Acupoint).filter(Acupoint.name == "测试穴X").delete()
    db_session.commit()
