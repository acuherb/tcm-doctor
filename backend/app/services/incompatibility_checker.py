"""处方安全检查 — 仅超剂量 / 毒性 / 孕妇禁忌（按《神农本草经》三品标注）

说明：十八反·十九畏已不再做硬性校验，提醒以《本经》三品（上/中/下品）与毒性、孕妇禁忌为准。
"""
from sqlalchemy.orm import Session
from app.models.herb import Herb


def check_dosage_limits(herb_id: int, dose: float, db: Session) -> dict | None:
    """
    检查药材剂量是否超限（按《本经》毒性标注提醒）。

    返回: None 表示安全，或 {"herb_name", "max_dose", "actual_dose", "toxicity", "grade"}
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
            "grade": herb.grade,
        }
    return None


def check_pregnancy_contraindications(herb_ids: list[int], db: Session) -> list[str]:
    """检查孕妇禁忌药材（结合《本经》三品与毒性标注提醒）"""
    herbs = db.query(Herb).filter(
        Herb.id.in_(herb_ids),
        Herb.pregnancy_contraindicated == True,
    ).all()
    msgs = []
    for h in herbs:
        grade_note = f"（《本经》{h.grade}）" if h.grade else ""
        msgs.append(f"⚠️ {h.name} 孕妇禁用{grade_note}（毒性: {h.toxicity}）")
    return msgs