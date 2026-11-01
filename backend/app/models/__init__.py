"""ORM 模型导出 — 确保所有模型被导入以便 Alembic 检测"""
from app.models.dictionaries import DictionaryTerm
from app.models.patient import Patient
from app.models.followup import FollowUp
from app.models.followup_reminder import FollowUpReminder
from app.models.visit import Visit
from app.models.inquiry import InquiryRecord
from app.models.herb import Herb
from app.models.stock import (
    StockItem, StockBatch, StockTransaction, Supplier, PurchaseOrder, PurchaseItem,
)
from app.models.prescription import ClassicFormula, Prescription, PrescriptionItem
from app.models.knowledge import KnowledgeEntry
from app.models.conversation import Conversation, Message
from app.models.acupuncture import Acupoint, AcupointFormula
from app.models.user import User, AuthToken

__all__ = [
    "DictionaryTerm",
    "Patient",
    "FollowUp",
    "FollowUpReminder",
    "Visit",
    "InquiryRecord",
    "Herb",
    "StockItem",
    "StockBatch",
    "StockTransaction",
    "Supplier",
    "PurchaseOrder",
    "PurchaseItem",
    "ClassicFormula",
    "Prescription",
    "PrescriptionItem",
    "KnowledgeEntry",
    "Conversation",
    "Message",
    "Acupoint",
    "AcupointFormula",
    "User",
    "AuthToken",
]