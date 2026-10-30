"""药材安全辅助检查 — 剂量上限/孕妇禁忌（十八反·十九畏已移除）"""
from sqlalchemy.orm import Session
from app.models.herb import Herb


def check_dosage_limits(herb_id: int, dose: float, db: Session) -> dict | None:
    """
    检查药材剂量是否超限。

    返回: None 表示安全，或 {"herb_name": "...", "max_dose": ..., "actual_dose": ...}
    """
    herb = db.query(Herb).filter(Herb.id == herb_id).first()
    if not herb:
        return None

    if herb.dosage_max and dose > float(herb.dosage_max):
        return {
            "herb_name": herb.name,
            "max_dose": float(herb.dosage_max),
            "actual_dose": dose,
            "toxicity": herb.toxicity,
        }
    return None


def check_pregnancy_contraindications(herb_ids: list[int], db: Session) -> list[str]:
    """检查孕妇禁忌药材"""
    herbs = db.query(Herb).filter(
        Herb.id.in_(herb_ids),
        Herb.pregnancy_contraindicated == True,
    ).all()
    return [f"⚠️ {h.name} 孕妇禁用 (毒性: {h.toxicity})" for h in herbs]