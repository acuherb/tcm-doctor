"""采购入库幂等：双击/网络重试不得重复增加批次数量、入库流水与采购成本。"""
import uuid

from app.database import SessionLocal
from app.models.stock import PurchaseOrder, StockBatch, StockItem


def _new_item() -> int:
    db = SessionLocal()
    try:
        item = StockItem(name=f"幂等物品_{uuid.uuid4().hex[:8]}", item_type="中药材", unit="g")
        db.add(item)
        db.commit()
        return item.id
    finally:
        db.close()


def _payload(item_id: int, request_id: str) -> dict:
    return {
        "request_id": request_id,
        "order_date": "2026-01-01",
        "items": [{
            "item_id": item_id, "quantity": 10, "unit_price": 2.5,
            "batch_number": f"BATCH-{request_id}",
        }],
    }


def test_same_request_id_only_imports_once(client, auth_headers):
    item_id = _new_item()
    body = _payload(item_id, f"REQ-{uuid.uuid4().hex[:8]}")

    r1 = client.post("/api/v1/stock/purchases", json=body, headers=auth_headers)
    assert r1.status_code == 200, r1.text
    r2 = client.post("/api/v1/stock/purchases", json=body, headers=auth_headers)
    assert r2.status_code == 200, r2.text

    assert r2.json()["id"] == r1.json()["id"]
    assert r1.json()["order_no"] == f"PO-{body['request_id']}"

    db = SessionLocal()
    try:
        assert db.query(PurchaseOrder).filter(
            PurchaseOrder.order_no == r1.json()["order_no"]
        ).count() == 1
        batches = db.query(StockBatch).filter(StockBatch.item_id == item_id).all()
        assert len(batches) == 1
        assert float(batches[0].quantity) == 10  # 不是 20
    finally:
        db.close()


def test_different_request_ids_create_separate_orders(client, auth_headers):
    """换键后允许下一张采购单，且不带 request_id 的旧客户端仍可用。"""
    item_id = _new_item()
    a = f"REQ-{uuid.uuid4().hex[:8]}"
    b = f"REQ-{uuid.uuid4().hex[:8]}"

    r1 = client.post("/api/v1/stock/purchases", json=_payload(item_id, a), headers=auth_headers)
    r2 = client.post("/api/v1/stock/purchases", json=_payload(item_id, b), headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]

    old_style = _payload(item_id, b)
    old_style.pop("request_id")
    r3 = client.post("/api/v1/stock/purchases", json=old_style, headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["order_no"].startswith("PO")
