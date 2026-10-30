"""ORM 模型导出 — 确保所有模型被导入以便 Alembic 检测"""
from app.models.dictionaries import DictionaryTerm
from app.models.patient import Patient
from app.models.followup import FollowUp
from app.models.followup_reminder import FollowUpReminder
from app.models.visit import Visit
from app.models.inquiry import InquiryRecord
from app.models.herb import Herb, HerbInventory, InventoryTransaction
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
    "HerbInventory",
    "InventoryTransaction",
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