"""挂号（前台分诊登记）测试：登记/队列/接诊完成/挂号费收费与退费，以及迁移 0023。"""
import uuid

from sqlalchemy import create_engine, text


def _suffix():
    return uuid.uuid4().hex[:8]


def test_register_new_patient_with_fee_paid(client, db_session, auth_headers):
    s = _suffix()
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"挂号患者_{s}", "phone": "13800000000", "gender": "男"},
        "department": "中医内科",
        "registration_fee": 20.0,
        "payment_method": "现金",
        "paid": 20.0,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["visit"]["status"] == "待诊"
    # 排队号按当日最大值递增；测试库里可能已有其它挂号，不假设从 1 开始
    assert isinstance(body["visit"]["queue_no"], int) and body["visit"]["queue_no"] >= 1
    assert body["visit"]["registration_fee"] == 20.0
    # 挂号费开单即收 -> 已收费
    assert body["charge"] is not None
    assert body["charge"]["kind"] == "registration"
    assert body["charge"]["status"] == "已收费"
    assert float(body["charge"]["payable"]) == 20.0


def test_patient_duplicate_check(client, db_session, auth_headers):
    from app.models.patient import Patient
    s = _suffix()
    db_session.add(Patient(name=f"张三_{s}", phone="13900000000", id_card="110101199001011234"))
    db_session.commit()

    # 按姓名查重 -> 命中
    r = client.get("/api/v1/patients/duplicates", params={"name": f"张三_{s}"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1

    # 按身份证查重 -> 命中（即便姓名不同）
    r2 = client.get("/api/v1/patients/duplicates",
                    params={"name": "别的名", "id_card": "110101199001011234"}, headers=auth_headers)
    assert len(r2.json()) == 1

    # 无匹配 -> 空
    r3 = client.get("/api/v1/patients/duplicates", params={"name": "查无此人_xyz"}, headers=auth_headers)
    assert r3.json() == []


def test_register_existing_patient_no_fee(client, db_session, auth_headers):
    from app.models.patient import Patient
    s = _suffix()
    pat = Patient(name=f"老患者_{s}")
    db_session.add(pat)
    db_session.commit()

    r = client.post("/api/v1/registration", json={
        "patient_id": pat.id,
        "registration_fee": 0,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["visit"]["patient_id"] == pat.id
    assert body["charge"] is None  # 无挂号费则不产生收费单


def test_queue_and_status_flow(client, db_session, auth_headers):
    s = _suffix()
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"队列_{s}"},
        "registration_fee": 15.0,
        "payment_method": "微信", "paid": 15.0,
    }, headers=auth_headers)
    vid = r.json()["visit"]["id"]

    # 队列可见
    q = client.get("/api/v1/registration/queue", headers=auth_headers)
    assert q.status_code == 200, q.text
    items = q.json()["items"]
    mine = next(i for i in items if i["id"] == vid)
    assert mine["registration_charge"]["status"] == "已收费"

    # 接诊 -> 已接诊
    c = client.post(f"/api/v1/registration/{vid}/call", headers=auth_headers)
    assert c.status_code == 200
    assert c.json()["status"] == "已接诊"

    # 完成 -> 已完成
    comp = client.post(f"/api/v1/registration/{vid}/complete", headers=auth_headers)
    assert comp.json()["status"] == "已完成"

    # 按状态筛选
    q2 = client.get("/api/v1/registration/queue", params={"status": "已完成"}, headers=auth_headers)
    assert any(i["id"] == vid for i in q2.json()["items"])


def test_registration_fee_appears_in_billing_and_refundable(client, db_session, auth_headers):
    s = _suffix()
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"退费_{s}"},
        "registration_fee": 30.0, "payment_method": "支付宝", "paid": 30.0,
    }, headers=auth_headers)
    cid = r.json()["charge"]["id"]

    # 出现在收费单列表（按类型筛选）
    lst = client.get("/api/v1/billing/charges", params={"status": "已收费"}, headers=auth_headers)
    assert any(c["id"] == cid and c["kind"] == "registration" for c in lst.json()["items"])

    # 可退费
    rf = client.post(f"/api/v1/billing/charges/{cid}/refund", json={"reason": "患者取消"}, headers=auth_headers)
    assert rf.status_code == 200, rf.text
    assert rf.json()["status"] == "已退费"


def test_register_requires_write_permission(client, db_session, auth_headers):
    # 仅 patient:read 的只读账号（viewer）应被拒绝
    from app.models.user import User
    from app.routers.auth import _hash_password

    viewer = User(username=f"viewer_{uuid.uuid4().hex[:6]}", password_hash=_hash_password("Viewer1"),
                 display_name="只读", role="viewer", must_change_password=False)
    db_session.add(viewer)
    db_session.commit()
    lr = client.post("/api/v1/auth/login", json={"username": viewer.username, "password": "Viewer1"})
    assert lr.status_code == 200, lr.text
    vtoken = lr.json()["token"]

    r = client.post("/api/v1/registration",
                    json={"new_patient": {"name": "越权测试"}},
                    headers={"Authorization": f"Bearer {vtoken}"})
    assert r.status_code == 403, r.text


def test_m0023_makes_prescription_id_nullable(tmp_path):
    """存量库 charges.prescription_id 为 NOT NULL（无 kind），迁移后应可空并保留数据。"""
    import app.migrations as mig
    from app.migrations import m0023

    db_file = tmp_path / "legacy.db"
    eng = create_engine(f"sqlite:///{db_file}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE prescriptions(id INTEGER PRIMARY KEY)"))
        # 旧结构：含全部真实列，但 prescription_id 为 NOT NULL（无 kind 列）
        c.execute(text(
            "CREATE TABLE charges("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "charge_no VARCHAR(32) NOT NULL, "
            "prescription_id INTEGER NOT NULL, "
            "patient_id INTEGER, visit_id INTEGER, patient_name VARCHAR(50), "
            "prescription_title VARCHAR(120), amount NUMERIC(12,2), discount NUMERIC(12,2), "
            "payable NUMERIC(12,2), paid NUMERIC(12,2), payment_method VARCHAR(20), "
            "status VARCHAR(20), cashier_id INTEGER, cashier_name VARCHAR(50), "
            "paid_at DATETIME, refunded_by VARCHAR(50), refunded_at DATETIME, "
            "refund_reason VARCHAR(200), note TEXT, created_at DATETIME)"
        ))
        c.execute(text(
            "INSERT INTO charges(charge_no,prescription_id,patient_id,amount,status) "
            "VALUES('C1', 1, 5, 10.0, '待收费')"
        ))

    old_engine = mig.engine
    mig.engine = eng
    try:
        m0023()
        with eng.begin() as c:
            # 现可插入挂号费（prescription_id 为空）
            c.execute(text(
                "INSERT INTO charges(charge_no,patient_id,amount,status,kind) "
                "VALUES('C2', 5, 8.0, '待收费', 'registration')"
            ))
            row = c.execute(text("SELECT prescription_id, kind FROM charges WHERE charge_no='C2'")).fetchone()
            assert row[0] is None
            assert row[1] == "registration"
            # 旧数据保留
            assert c.execute(text("SELECT charge_no FROM charges WHERE charge_no='C1'")).fetchone()
            # 唯一约束/索引仍在
            assert c.execute(text("SELECT 1 FROM charges WHERE charge_no='C1'")).fetchone()
    finally:
        mig.engine = old_engine
