"""处方安全检查 — 仅超剂量 / 毒性 / 孕妇禁忌（按毒性标注提醒）"""
from sqlalchemy.orm import Session
from app.models.herb import Herb


def check_dosage_limits(herb_id: int, dose: float, db: Session) -> dict | None:
    """
    检查药材剂量是否超限。

    返回: None 表示安全，或 {"herb_name", "max_dose", "actual_dose", "toxicity"}
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
    """检查孕妇禁忌药材（结合毒性标注提醒）"""
    herbs = db.query(Herb).filter(
        Herb.id.in_(herb_ids),
        Herb.pregnancy_contraindicated == True,
    ).all()
    msgs = []
    for h in herbs:
        msgs.append(f"⚠️ {h.name} 孕妇禁用（毒性: {h.toxicity}）")
    return msgs