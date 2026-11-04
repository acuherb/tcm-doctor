"""药材列表五味筛选：多选五味须「全部具备」(AND)，而非命中任一(OR)。

本测试自给自足，不依赖外部种子数据（app/data/herbs.json 已被 gitignore，
CI 干净克隆里没有药材），由 fixture 自行造桂枝 / 甘草两条样本。
"""
import pytest
from app.models.herb import Herb


@pytest.fixture(autouse=True)
def ensure_test_herbs(db_session):
    """保证存在用于筛选断言的样本药材（不依赖 app/data 种子文件）。"""
    existing = {name for (name,) in db_session.query(Herb.name).all()}
    to_add = []
    if "桂枝" not in existing:
        to_add.append(Herb(name="桂枝", flavors=["辛", "甘"]))
    if "甘草" not in existing:
        to_add.append(Herb(name="甘草", flavors=["甘"]))
    if to_add:
        db_session.add_all(to_add)
        db_session.commit()


def test_flavors_filter_and_semantics(client, auth_headers):
    """同时选 辛+甘 时，只返回同时具备两味的药材（如桂枝），不含仅甘的甘草。"""
    r = client.get(
        "/api/v1/herbs",
        params=[("flavors", "辛"), ("flavors", "甘")],
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    names = {h["name"] for h in r.json()}
    assert "桂枝" in names
    assert "甘草" not in names
    assert "麻黄" not in names


def test_flavors_filter_all_selected_returns_empty(client, auth_headers):
    """选齐全部五味时，无药能同时具备五味，结果应为空集。"""
    all_flavors = ["辛", "甘", "酸", "苦", "咸"]
    params = [("flavors", f) for f in all_flavors]
    r = client.get("/api/v1/herbs", params=params, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_flavors_filter_single_flavor(client, auth_headers):
    """单选某一味仍正常返回该味的药材。"""
    r = client.get("/api/v1/herbs", params=[("flavors", "甘")], headers=auth_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()) > 0
    assert all("甘" in h["flavors"] for h in r.json())
