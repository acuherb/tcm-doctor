"""处方 ORM 模型"""
import hashlib
import json
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, Integer, Numeric, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.config import settings, get_signing_secret, LEGACY_SIGNING_SECRET


class ClassicFormula(Base):
    """经典方剂库"""
    __tablename__ = "classic_formulas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="方名")
    aliases: Mapped[dict | None] = mapped_column(JSON, comment="别名")
    source: Mapped[str | None] = mapped_column(String(100), comment="出处: 伤寒论/金匮要略/...")
    composition: Mapped[dict] = mapped_column(JSON, nullable=False, comment="组成")
    efficacy: Mapped[str | None] = mapped_column(Text, comment="功效")
    indications: Mapped[str | None] = mapped_column(Text, comment="主治")
    usage: Mapped[str | None] = mapped_column(Text, comment="用法")
    modifications: Mapped[dict | None] = mapped_column(JSON, comment="加减变化")

    def __repr__(self):
        return f"<ClassicFormula(id={self.id}, name='{self.name}')>"


def _canonical_prescription(p: "Prescription") -> dict:
    """处方临床内容的规范化表示（不含 status / 签名 / 时间戳等非临床字段）。

    用于生成防篡改内容哈希；规范化保证相同临床内容得到相同哈希。
    """
    items = sorted(
        (
            {
                "herb_name": it.herb_name,
                "dose": float(it.dose) if it.dose is not None else None,
                "special_method": it.special_method,
                "is_king_herb": bool(it.is_king_herb),
                "note": it.note,
                "inventory_id": it.inventory_id,
                "price": float(it.price) if it.price is not None else None,
            }
            for it in (p.items or [])
        ),
        key=lambda x: (x["herb_name"] or ""),
    )
    acupoints = sorted(
        (
            {
                "acupoint_name": a.acupoint_name,
                "technique": a.technique,
                "retention": a.retention,
                "sequence": a.sequence,
                "note": a.note,
            }
            for a in (p.acupoints or [])
        ),
        key=lambda x: (x["sequence"] or 0, x["acupoint_name"] or ""),
    )
    injections = sorted(
        (
            {
                "drug_name": j.drug_name,
                "spec": j.spec,
                "dose": j.dose,
                "usage": j.usage,
                "frequency": j.frequency,
                "note": j.note,
            }
            for j in (p.injections or [])
        ),
        key=lambda x: (x["drug_name"] or ""),
    )
    return {
        "id": p.id,
        "patient_id": p.patient_id,
        "visit_id": p.visit_id,
        "formula_name": p.formula_name,
        "is_classic": bool(p.is_classic),
        "classic_formula_id": p.classic_formula_id,
        "acupoint_formula_id": p.acupoint_formula_id,
        "preparation_method": p.preparation_method,
        "administration": p.administration,
        "doses": p.doses,
        "prescription_type": p.prescription_type,
        "acupoint_formula_name": p.acupoint_formula_name,
        "acupoint_technique": p.acupoint_technique,
        "treatment_frequency": p.treatment_frequency,
        "treatment_days": p.treatment_days,
        "acupuncture_fee": float(p.acupuncture_fee) if p.acupuncture_fee is not None else None,
        "doctor_notes": p.doctor_notes,
        "items": items,
        "acupoints": acupoints,
        "injections": injections,
    }


def compute_prescription_hash(p: "Prescription") -> str:
    """对处方临床内容生成 SHA-256 哈希（防篡改基线）。

    规范化序列化后哈希，确保相同内容恒定产出，便于后续校验是否被改动。
    """
    canonical = json.dumps(
        _canonical_prescription(p), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_signature(content_hash: str, signed_by: str, signed_at: str, secret: str) -> str:
    """电子签名令牌：将内容哈希与签名人/时间绑定，杜绝事后伪造或挪用到其它处方。"""
    payload = f"{content_hash}|{signed_by}|{signed_at}|{secret}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Prescription(Base):
    """处方记录"""
    __tablename__ = "prescriptions"
    __table_args__ = (
        Index("idx_prescriptions_patient", "patient_id"),
        Index("idx_prescriptions_visit", "visit_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(Integer, ForeignKey("visits.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    formula_name: Mapped[str | None] = mapped_column(String(100), comment="方名")
    is_classic: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否经典方")
    classic_formula_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("classic_formulas.id", ondelete="SET NULL"))
    acupoint_formula_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("acupoint_formulas.id", ondelete="SET NULL"), comment="关联针灸方库")
    preparation_method: Mapped[str] = mapped_column(String(50), default="水煎服", comment="煎法")
    administration: Mapped[str | None] = mapped_column(String(100), comment="服法")
    doses: Mapped[int] = mapped_column(Integer, default=7, comment="剂数")
    doctor_notes: Mapped[str | None] = mapped_column(Text, comment="医嘱")
    total_price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="总价")
    prescription_type: Mapped[str] = mapped_column(String(20), default="药方", comment="处方类型: 药方/针方/针剂/混合")
    # 针灸方顶层字段（可与药方共存于同一张处方）
    acupoint_formula_name: Mapped[str | None] = mapped_column(String(100), comment="针灸方案名")
    acupoint_technique: Mapped[str | None] = mapped_column(String(50), comment="针灸针法/治法")
    treatment_frequency: Mapped[str | None] = mapped_column(String(20), comment="操作频次: 每日/隔日/每周...")
    treatment_days: Mapped[int | None] = mapped_column(Integer, comment="疗程天数")
    acupuncture_fee: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="针灸费用(元)")
    status: Mapped[str] = mapped_column(String(20), default="已开", comment="状态")
    reviewed_by: Mapped[int | None] = mapped_column(Integer, comment="审核人")
    doctor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), comment="开方医师账号")
    doctor_name: Mapped[str | None] = mapped_column(String(50), comment="开方医师姓名快照（账号改名前打印仍正确）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # 乐观锁
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", comment="乐观锁版本号")

    # ── 电子签名与防篡改 ──
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="内容哈希(防篡改校验基线)")
    signed_by: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="电子签名医师姓名")
    signed_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="电子签名医师ID")
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="电子签名时间")
    signature: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="电子签名令牌(绑定内容哈希+签名人+时间)")

    # 关系
    visit: Mapped["Visit"] = relationship(back_populates="prescriptions")
    items: Mapped[list["PrescriptionItem"]] = relationship(back_populates="prescription", cascade="all, delete-orphan")
    acupoints: Mapped[list["AcupointPrescription"]] = relationship(back_populates="prescription", cascade="all, delete-orphan")
    injections: Mapped[list["PrescriptionInjection"]] = relationship(back_populates="prescription", cascade="all, delete-orphan")

    __mapper_args__ = {"version_id_col": version}

    # ── 防篡改 / 签名 派生状态（基于当前字段实时计算，无需额外存储） ──
    @property
    def content_hash_current(self) -> str:
        """按当前字段实时重算的内容哈希"""
        return compute_prescription_hash(self)

    @property
    def tampered(self) -> bool:
        """内容是否被篡改：已建立基线(content_hash 非空)但当前重算不一致 → 被改动过。

        存量未签名处方 content_hash 为空，无法判定，返回 False（不误报）。
        """
        if not self.content_hash:
            return False
        return self.content_hash_current != self.content_hash

    @property
    def signed(self) -> bool:
        """是否已电子签名（签名人与令牌齐全）"""
        return bool(self.signed_by and self.signature)

    @property
    def signature_valid(self) -> bool:
        """签名是否有效：令牌与「内容哈希+签名人+时间」重新计算一致。

        若签名后内容被改动（content_hash 变化），令牌将不匹配 → 失效，需重新签名。
        """
        if not self.signed:
            return False
        args = (self.content_hash, self.signed_by, (self.signed_at.isoformat() if self.signed_at else ""))
        if self.signature == compute_signature(*args, get_signing_secret()):
            return True
        # 兼容旧版本用公开默认常量签发的存量处方，避免升级后签名集体失效
        return self.signature == compute_signature(*args, LEGACY_SIGNING_SECRET)

    def __repr__(self):
        return f"<Prescription(id={self.id}, formula='{self.formula_name}', status='{self.status}')>"


class PrescriptionItem(Base):
    """处方药味明细"""
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prescription_id: Mapped[int] = mapped_column(Integer, ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False)
    herb_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("herbs.id", ondelete="SET NULL"), nullable=True)
    herb_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="药材名(冗余)")
    dose: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, comment="剂量(g)")
    special_method: Mapped[str | None] = mapped_column(String(20), comment="特殊煎法")
    is_king_herb: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否君药")
    note: Mapped[str | None] = mapped_column(String(100), comment="备注")
    inventory_id: Mapped[int | None] = mapped_column(Integer, comment="关联库存批次(指向 stock_batches.id，开方选批次取价/发药出货依据)")
    price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="该味记账单价(元/g)，开方时按批次售价或药材参考价确定")

    prescription: Mapped["Prescription"] = relationship(back_populates="items")

    def __repr__(self):
        return f"<PrescriptionItem(herb='{self.herb_name}', dose={self.dose}g)>"


class AcupointPrescription(Base):
    """处方针灸配穴细目"""
    __tablename__ = "acupoint_prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prescription_id: Mapped[int] = mapped_column(Integer, ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False)
    acupoint_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("acupoints.id", ondelete="SET NULL"), comment="穴位ID(允许手输，可为空)")
    acupoint_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="穴名(冗余)")
    technique: Mapped[str | None] = mapped_column(String(50), comment="针法：毫针泻法/补法/温灸...")
    retention: Mapped[str | None] = mapped_column(String(20), comment="留针时间")
    sequence: Mapped[int] = mapped_column(Integer, default=1, comment="施针顺序")
    note: Mapped[str | None] = mapped_column(String(100), comment="备注")

    prescription: Mapped["Prescription"] = relationship(back_populates="acupoints")

    def __repr__(self):
        return f"<AcupointPrescription(acupoint='{self.acupoint_name}', technique='{self.technique}')>"


class PrescriptionInjection(Base):
    """处方针剂细目"""
    __tablename__ = "prescription_injections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prescription_id: Mapped[int] = mapped_column(Integer, ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False)
    drug_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="药品名称")
    spec: Mapped[str | None] = mapped_column(String(50), comment="规格")
    dose: Mapped[str | None] = mapped_column(String(50), comment="用量")
    usage: Mapped[str | None] = mapped_column(String(50), comment="用法: 肌注/静滴/皮试...")
    frequency: Mapped[str | None] = mapped_column(String(30), comment="频次")
    note: Mapped[str | None] = mapped_column(String(100), comment="备注")

    prescription: Mapped["Prescription"] = relationship(back_populates="injections")

    def __repr__(self):
        return f"<PrescriptionInjection(drug='{self.drug_name}', dose='{self.dose}')>"