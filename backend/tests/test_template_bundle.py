"""基础数据包（manifest + 分层依赖 + sha256）与一键导入端点回归测试。"""
import hashlib
import io
import json
import uuid
import zipfile

import pytest

from app import template_bundle
from app.models.herb import Herb
from app.models.acupuncture import Acupoint
from app.models.prescription import ClassicFormula
from app.permissions import resolve_domain


def _payload(type_, items):
    return json.dumps({"type": type_, "version": 1, "items": items}, ensure_ascii=False, indent=2)


def _entry(rel, text):
    return {"file": rel, "count": len(json.loads(text)["items"]),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def make_zip(*, bad_hash=False, unknown_type=False, traversal=False, schema_version=1, flip_order=False):
    tag = uuid.uuid4().hex[:8]
    herbs = _payload("herbs", [{"name": f"QA包药材{tag}{i}", "efficacy": "补气"} for i in range(3)])
    points = _payload("acupoints", [{"name": f"QA包穴位{tag}{i}", "meridian": "足阳明胃经"} for i in range(2)])
    formulas = _payload("classic_formulas", [{"name": f"QA包方剂{tag}", "composition": {}, "efficacy": "x"}])
    texts = {
        "core/herbs.json": herbs,
        "core/acupoints.json": points,
        "formulas/classic_formulas.json": formulas,
    }
    core_files = [_entry("core/herbs.json", herbs), _entry("core/acupoints.json", points)]
    if bad_hash:
        core_files[0]["sha256"] = "0" * 64
    core = {
        "name": "core", "label": "核心", "depends_on": [],
        "types": ["herbs", "acupoints"], "files": core_files,
    }
    formulas_layer = {
        "name": "formulas", "label": "方库", "depends_on": ["core"],
        "types": ["unknown_table" if unknown_type else "classic_formulas"],
        "files": [_entry("formulas/classic_formulas.json", formulas)],
    }
    layers = [formulas_layer, core] if flip_order else [core, formulas_layer]
    manifest = {
        "package": "qa", "title": "QA 数据包", "version": "1.0.0",
        "schema_version": schema_version, "layers": layers,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, text in texts.items():
            z.writestr(rel, text)
        if traversal:
            z.writestr("../evil.json", "[]")
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return buf.getvalue(), tag


def test_plan_dependency_order_and_sha256():
    data, _ = make_zip(flip_order=True)
    plan = template_bundle.build_plan(data)
    # 清单里 formulas 排在 core 前面，执行顺序仍须按依赖把 core 放前面
    assert plan["order"] == ["core", "formulas"], plan["order"]
    assert all(f["sha256_verified"] for f in plan["files"])
    assert sum(f["count"] for f in plan["files"]) == 6
    # 只选 formulas 时自动补上 core 依赖
    selected = template_bundle.build_plan(data, "formulas")
    assert selected["order"] == ["core", "formulas"]


@pytest.mark.parametrize("kwargs", [
    {"bad_hash": True}, {"unknown_type": True}, {"traversal": True}, {"schema_version": 99},
    {"flip_order": True, "bad_hash": True},
])
def test_plan_rejects_bad_packages(kwargs):
    data, _ = make_zip(**kwargs)
    with pytest.raises(template_bundle.BundleError):
        template_bundle.build_plan(data)


def test_bundle_preview_dry_run_and_install(client, db_session, auth_headers):
    data, tag = make_zip(flip_order=True)
    url = "/api/v1/templates/bundle/preview"
    files = {"file": ("qa-bundle.zip", data, "application/zip")}

    preview = client.post(url, files=files, headers=auth_headers)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["dry_run"] is True
    assert body["order"] == ["core", "formulas"]
    assert body["totals"]["added"] == 6
    # 预检绝不落库
    assert db_session.query(Herb).filter(Herb.name.like(f"QA包药材{tag}%")).count() == 0

    install = client.post("/api/v1/templates/bundle/install", files=files, headers=auth_headers)
    assert install.status_code == 200, install.text
    assert install.json()["dry_run"] is False
    assert install.json()["totals"]["added"] == 6
    db_session.expire_all()
    assert db_session.query(Herb).filter(Herb.name.like(f"QA包药材{tag}%")).count() == 3
    assert db_session.query(Acupoint).filter(Acupoint.name.like(f"QA包穴位{tag}%")).count() == 2
    assert db_session.query(ClassicFormula).filter(ClassicFormula.name == f"QA包方剂{tag}").count() == 1

    # 幂等：重复安装只更新不新增
    again = client.post("/api/v1/templates/bundle/install", files=files, headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["totals"]["added"] == 0
    assert again.json()["totals"]["updated"] == 6


def test_bundle_listing_and_templates_domain(client, auth_headers):
    # 此前 /templates 未登记权限域，所有模板接口 fail-closed 403
    assert resolve_domain("/api/v1/templates") == "/templates"
    assert client.get("/api/v1/templates", headers=auth_headers).status_code == 200
    res = client.get("/api/v1/templates/bundles", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "packages" in body and "content" in body and "needs_setup" in body


def test_bundle_rejects_bad_upload(client, auth_headers):
    bad, _ = make_zip(bad_hash=True)
    r = client.post("/api/v1/templates/bundle/preview",
                    files={"file": ("bad.zip", bad, "application/zip")},
                    headers=auth_headers)
    assert r.status_code == 400
    assert "sha256" in r.json()["detail"]
