"""按患者聚合完整病历，供导出（JSON）与打印（自包含 HTML）使用。

设计要点：
- 一次查询把一个患者的全部留存信息组装成自包含文档，便于转诊、归档、换机带走。
- 只做读取，不修改任何数据；敏感个人信息需经 patient:read 权限（由路由校验）。
- 舌象/面色/化验单图片为 base64，体积大且非必需，默认不导出（include_images=true 时含）。
- HTML 打印视图对全部文本做转义，避免病历内容里的 HTML 造成注入。
"""
from __future__ import annotations

import html
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.inquiry import InquiryRecord
from app.models.prescription import (
    Prescription, PrescriptionItem, AcupointPrescription, PrescriptionInjection,
)
from app.models.followup import FollowUp
from app.models.followup_reminder import FollowUpReminder

FORMAT_VERSION = 1
IMAGE_FIELDS = ("tongue_image", "face_image", "lab_report_images")


def _value(v):
    """把 ORM 值转成 JSON 可序列化形态。"""
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _row(obj, drop_images: bool = False) -> dict:
    out: dict = {}
    for c in obj.__table__.columns:
        if drop_images and c.name in IMAGE_FIELDS:
            continue
        out[c.name] = _value(getattr(obj, c.name))
    return out


def build_record(db: Session, patient_id: int, include_images: bool = False) -> dict | None:
    """组装单个患者的完整病历；患者不存在返回 None。"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        return None

    patient_d = _row(patient)
    # 体质结论存在 constitution_score(JSON) 里，单独展开便于阅读
    cs = patient.constitution_score or {}
    constitution = {
        "type": patient.constitution_type,
        "scores": cs.get("scores") if isinstance(cs, dict) else None,
        "primary_type": cs.get("primary_type") if isinstance(cs, dict) else None,
        "secondary_types": cs.get("secondary_types") if isinstance(cs, dict) else [],
        "findings": cs.get("findings") if isinstance(cs, dict) else [],
        "suggestion": cs.get("suggestion") if isinstance(cs, dict) else "",
    }

    visits = (
        db.query(Visit).filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.asc(), Visit.id.asc()).all()
    )
    prescriptions = (
        db.query(Prescription).filter(Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.asc(), Prescription.id.asc()).all()
    )
    rx_ids = [r.id for r in prescriptions]
    items_by_rx: dict[int, list] = {i: [] for i in rx_ids}
    for model in (PrescriptionItem, AcupointPrescription, PrescriptionInjection):
        if not rx_ids:
            break
        for row in db.query(model).filter(model.prescription_id.in_(rx_ids)).all():
            items_by_rx.setdefault(row.prescription_id, []).append(
                {"category": model.__tablename__, **_row(row)}
            )

    rx_d = [
        {**_row(r), "details": items_by_rx.get(r.id, [])}
        for r in prescriptions
    ]
    visit_ids = {v.id for v in visits}
    visit_d = [
        {
            **_row(v, drop_images=not include_images),
            "prescriptions": [r for r in rx_d if r["visit_id"] == v.id],
            "image_included": include_images,
        }
        for v in visits
    ]
    # 历史数据可能出现「处方归属患者与就诊归属患者不一致」，单独列出以免导出时静默丢处方
    unlinked_d = [r for r in rx_d if r["visit_id"] not in visit_ids]

    inquiries = (
        db.query(InquiryRecord).filter(InquiryRecord.patient_id == patient_id)
        .order_by(InquiryRecord.created_at.asc(), InquiryRecord.id.asc()).all()
    )
    followups = (
        db.query(FollowUp).filter(FollowUp.patient_id == patient_id)
        .order_by(FollowUp.followup_date.asc(), FollowUp.id.asc()).all()
    )
    reminders = (
        db.query(FollowUpReminder).filter(FollowUpReminder.patient_id == patient_id)
        .order_by(FollowUpReminder.due_date.asc(), FollowUpReminder.id.asc()).all()
    )

    return {
        "meta": {
            "format_version": FORMAT_VERSION,
            "exported_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "clinic_name": settings.clinic_name or "",
            "doctor_name": settings.doctor_name or "",
            "include_images": include_images,
            "disclaimer": "本病历由系统导出，仅供留存与转诊参考，不构成临床诊疗依据。",
        },
        "patient": patient_d,
        "constitution": constitution,
        "visits": visit_d,
        "unlinked_prescriptions": unlinked_d,
        "inquiries": [_row(i) for i in inquiries],
        "followups": [_row(f) for f in followups],
        "reminders": [_row(r) for r in reminders],
        "summary": {
            "visits": len(visit_d),
            "prescriptions": len(rx_d),
            "inquiries": len(inquiries),
            "followups": len(followups),
            "reminders": len(reminders),
        },
    }


def summarize_prior_history(record: dict, max_visits: int = 10, max_followups: int = 8) -> str:
    """生成供 AI 辨证参考的「既往病史与疗效回顾」文本（不含图片，限条数，控制 token）。

    用于把患者历史辨证/处方/随访疗效喂给 AI，让其在复诊时对比证型/舌脉变化、
    沿用有效思路、规避既往无效或不适方案。无既往记录时返回空串。
    """
    visits = record.get("visits") or []
    followups = record.get("followups") or []
    if not visits and not followups:
        return ""

    lines = ["【既往病史与疗效回顾】（供本次辨证参考，请结合对比，勿直接复述）"]
    for v in (visits[-max_visits:] if len(visits) > max_visits else visits):
        parts = [f"- {v.get('visit_date') or ''} {v.get('visit_type') or '就诊'}"]
        if v.get("chief_complaint"):
            parts.append(f"主诉：{v['chief_complaint']}")
        if v.get("tcm_disease") or v.get("tcm_syndrome"):
            parts.append(f"病名/证型：{v.get('tcm_disease') or '—'}/{v.get('tcm_syndrome') or '—'}")
        if v.get("treatment_method"):
            parts.append(f"治法：{v['treatment_method']}")
        rxs = v.get("prescriptions") or []
        rx_texts = []
        for r in rxs:
            herbs = [d for d in r.get("details", []) if d.get("category") == "prescription_items"]
            h = "、".join(f"{d.get('herb_name')}{d.get('dose') or ''}" for d in herbs[:8])
            rx_texts.append((r.get("formula_name") or "自拟方") + (f"（{h}）" if h else ""))
        if rx_texts:
            parts.append("处方：" + "；".join(rx_texts))
        ai = (v.get("ai_analysis") or "")[:200]
        if ai:
            parts.append(f"辨证摘要：{ai}")
        lines.append("｜".join(parts))

    if followups:
        lines.append("疗效随访：")
        for f in (followups[-max_followups:] if len(followups) > max_followups else followups):
            lines.append(
                f"- {f.get('followup_date') or ''} 改善：{f.get('improvement') or '—'}｜反馈：{f.get('feedback') or '—'}"
            )
    return "\n".join(lines)


# ── 打印视图 ──

_FIELD_LABELS = {
    "name": "姓名", "gender": "性别", "birth_date": "出生日期", "phone": "电话",
    "id_card": "身份证号", "address": "住址", "height": "身高(cm)", "weight": "体重(kg)",
    "allergy_history": "过敏史", "medical_history": "既往史", "notes": "备注",
    "constitution_type": "体质", "tags": "标签", "note": "备注",
    "chief_complaint": "主诉", "present_illness": "现病史",
    "observation": "望诊", "auscultation": "闻诊", "inquiry": "问诊", "palpation": "切诊",
    "tongue_body": "舌质", "tongue_coat": "舌苔", "pulse": "脉象",
    "tcm_disease": "中医病名", "tcm_syndrome": "证型", "treatment_method": "治法",
    "ai_analysis": "AI 辅助辨证", "doctor_notes": "医嘱",
    "visit_date": "就诊日期", "visit_type": "就诊类型",
    "formula_name": "方名", "doses": "剂数", "status": "状态",
    "preparation_method": "煎法", "administration": "服法",
    "prescription_type": "处方类型", "doctor_name": "开方医师",
    "herb_name": "药材", "dose": "剂量(g)", "special_method": "特殊煎法",
    "followup_date": "随访日期", "improvement": "改善程度", "feedback": "效果反馈",
    "due_date": "应回访日期", "source_type": "提醒来源", "answers": "十问答案",
    "result": "评估结果", "primary_type": "主偏性画像", "created_at": "记录时间",
    "acupoint_formula_name": "针灸方案", "acupoint_technique": "针法/治法",
    "treatment_frequency": "操作频次", "treatment_days": "疗程天数",
    "acupoint_name": "穴名", "technique": "针法", "retention": "留针", "sequence": "施针顺序",
    "drug_name": "药品", "spec": "规格", "usage": "用法", "frequency": "频次",
    "is_king_herb": "君药", "price": "单价", "total_price": "总价",
    "treatment_type": "治疗类型",
}


def _esc(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)
    return html.escape(str(v), quote=True)


def _fields_html(d: dict, keys: list[str]) -> str:
    rows = []
    for k in keys:
        if k not in d or d[k] in (None, "", [], {}):
            continue
        label = _FIELD_LABELS.get(k, k)
        val = _esc(d[k])
        rows.append(
            f'<tr><th>{html.escape(label)}</th><td>{val}</td></tr>'
        )
    return "".join(rows)


_DETAIL_SKIP = {"id", "prescription_id", "category", "herb_id", "acupoint_id", "inventory_id"}
_DETAIL_LABELS = {
    "prescription_items": "中药方",
    "acupoint_prescriptions": "针灸配穴",
    "prescription_injections": "针剂",
}


def _rx_html(r: dict) -> str:
    """单张处方（含药味 / 配穴 / 针剂明细）的打印片段。"""
    out = [
        f"<h3>处方：{_esc(r.get('formula_name') or '自拟方')} ｜ #{_esc(r.get('id'))}</h3>",
        "<table>",
        _fields_html(r, [
            "prescription_type", "doses", "preparation_method", "administration",
            "status", "doctor_name", "doctor_notes", "acupoint_formula_name",
            "acupoint_technique", "treatment_frequency", "treatment_days", "created_at",
        ]),
        "</table>",
    ]
    details = r.get("details", [])
    herbs = [d for d in details if d.get("category") == "prescription_items"]
    if herbs:
        out.append("<table><tr><th>药材</th><th>剂量(g)</th><th>特殊煎法</th><th>君药</th><th>备注</th></tr>")
        for d in herbs:
            out.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    _esc(d.get("herb_name")), _esc(d.get("dose")),
                    _esc(d.get("special_method")),
                    "是" if d.get("is_king_herb") else "", _esc(d.get("note")),
                )
            )
        out.append("</table>")
    for d in details:
        category = d.get("category")
        if category == "prescription_items":
            continue
        kv = " ｜ ".join(
            f"{_FIELD_LABELS.get(k, k)}={_esc(v)}"
            for k, v in d.items() if k not in _DETAIL_SKIP and v not in (None, "", [], {})
        )
        out.append(f"<div class='pre'>{_esc(_DETAIL_LABELS.get(category, category))}：{kv}</div>")
    return "".join(out)


def _images_html(v: dict) -> str:
    """仅在 include_images=true 时渲染；只接受 data:image/ 开头的本地内嵌图，防止注入外链。"""
    imgs: list[tuple[str, str]] = []
    for key, label in (("tongue_image", "舌象"), ("face_image", "面色")):
        src = v.get(key)
        if isinstance(src, str) and src.startswith("data:image/"):
            imgs.append((label, src))
    labs = v.get("lab_report_images")
    candidates = labs.values() if isinstance(labs, dict) else labs if isinstance(labs, list) else []
    for idx, src in enumerate(candidates, 1):
        if isinstance(src, str) and src.startswith("data:image/"):
            imgs.append((f"化验单 {idx}", src))
    if not imgs:
        return ""
    out = ["<div class='imgs'>"]
    for label, src in imgs:
        out.append(
            f"<figure><img src='{html.escape(src, quote=True)}' alt='{html.escape(label)}'>"
            f"<figcaption>{html.escape(label)}</figcaption></figure>"
        )
    out.append("</div>")
    return "".join(out)


def render_html(record: dict) -> str:
    """把病历渲染为自包含、可直接浏览器打印(A4)的 HTML。"""
    p = record["patient"]
    meta = record["meta"]
    clinic = _esc(meta.get("clinic_name") or "中医诊所")

    parts = [
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>",
        f"<title>病历 - {_esc(p.get('name'))}</title>",
        "<style>",
        "@page { size: A4; margin: 16mm; }",
        "body { font-family: 'Noto Serif SC','Songti SC',serif; color:#2c1810; margin:0; font-size:13px; line-height:1.7; }",
        "h1 { font-size:20px; text-align:center; margin:0 0 4px; letter-spacing:4px; }",
        ".sub { text-align:center; color:#8a7a68; font-size:12px; margin-bottom:14px; }",
        "h2 { font-size:15px; border-left:4px solid #8c6a46; padding-left:8px; margin:20px 0 8px; }",
        "h3 { font-size:13px; margin:12px 0 4px; color:#6b4f34; }",
        "table { width:100%; border-collapse:collapse; margin-bottom:8px; }",
        "th,td { border:1px solid #d9cdbb; padding:5px 8px; text-align:left; vertical-align:top; word-break:break-word; }",
        "th { width:96px; background:#f7f2ea; font-weight:600; white-space:nowrap; }",
        ".pre { white-space:pre-wrap; }",
        ".imgs { display:flex; flex-wrap:wrap; gap:10px; margin:8px 0; }",
        ".imgs figure { margin:0; width:130px; }",
        ".imgs img { width:100%; height:auto; border:1px solid #d9cdbb; }",
        ".imgs figcaption { font-size:11px; text-align:center; color:#8a7a68; }",
        ".foot { margin-top:24px; font-size:11px; color:#8a7a68; border-top:1px solid #d9cdbb; padding-top:8px; }",
        "@media print { .noprint { display:none; } }",
        ".noprint { text-align:center; margin:14px 0; }",
        ".noprint button { padding:8px 20px; font-size:14px; cursor:pointer; }",
        "</style></head><body>",
        "<div class='noprint'><button onclick='window.print()'>打印 / 另存为 PDF</button></div>",
        f"<h1>{clinic} · 完整病历</h1>",
        f"<div class='sub'>患者：{_esc(p.get('name'))} ｜ 导出时间：{_esc(meta.get('exported_at'))} ｜ 共 {record['summary']['visits']} 次就诊</div>",
    ]

    parts.append("<h2>一、患者基本信息</h2><table>")
    parts.append(_fields_html(p, [
        "name", "gender", "birth_date", "phone", "id_card", "address",
        "height", "weight", "allergy_history", "medical_history",
        "constitution_type", "tags", "notes",
    ]))
    parts.append("</table>")

    c = record.get("constitution") or {}
    if c.get("type") or c.get("primary_type") or c.get("scores"):
        parts.append("<h2>二、体质辨识</h2><table>")
        parts.append(
            f"<tr><th>主要体质</th><td>{_esc(c.get('primary_type') or c.get('type'))}</td></tr>"
            f"<tr><th>兼夹体质</th><td>{_esc(c.get('secondary_types'))}</td></tr>"
            f"<tr><th>体质评分</th><td>{_esc(c.get('scores'))}</td></tr>"
            f"<tr><th>辨识依据</th><td>{_esc(c.get('findings'))}</td></tr>"
            f"<tr><th>调养建议</th><td>{_esc(c.get('suggestion'))}</td></tr>"
        )
        parts.append("</table>")

    parts.append("<h2>三、就诊记录</h2>")
    if not record["visits"]:
        parts.append("<p>（暂无就诊记录）</p>")
    for idx, v in enumerate(record["visits"], 1):
        parts.append(f"<h3>第 {idx} 诊 ｜ {_esc(v.get('visit_date'))} ｜ {_esc(v.get('visit_type'))}</h3>")
        parts.append("<table>")
        parts.append(_fields_html(v, [
            "chief_complaint", "present_illness", "observation", "auscultation",
            "inquiry", "palpation", "tongue_body", "tongue_coat", "pulse",
            "tcm_disease", "tcm_syndrome", "treatment_method", "ai_analysis", "doctor_notes",
        ]))
        parts.append("</table>")
        parts.append(_images_html(v))
        for r in v.get("prescriptions", []):
            parts.append(_rx_html(r))

    unlinked = record.get("unlinked_prescriptions") or []
    if unlinked:
        parts.append("<h3>其他处方（未关联到本患者就诊记录）</h3>")
        for r in unlinked:
            parts.append(_rx_html(r))

    if record["inquiries"]:
        parts.append("<h2>四、问诊十问</h2>")
        for i in record["inquiries"]:
            parts.append(f"<h3>{_esc(i.get('created_at'))}</h3><table>")
            parts.append(_fields_html(i, ["primary_type", "answers", "result"]))
            if i.get("notes"):
                parts.append(f"<tr><th>自填补充</th><td>{_esc(i.get('notes'))}</td></tr>")
            parts.append("</table>")

    if record["followups"]:
        parts.append("<h2>五、疗效随访</h2><table>")
        parts.append("<tr><th>日期</th><th>治疗类型</th><th>改善程度</th><th>效果反馈</th></tr>")
        for f in record["followups"]:
            parts.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    _esc(f.get("followup_date")), _esc(f.get("treatment_type")),
                    _esc(f.get("improvement")), _esc(f.get("feedback")),
                )
            )
        parts.append("</table>")

    if record["reminders"]:
        parts.append("<h2>六、复诊提醒</h2><table>")
        parts.append("<tr><th>应回访日期</th><th>来源</th><th>状态</th><th>复诊建议</th></tr>")
        for r in record["reminders"]:
            parts.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    _esc(r.get("due_date")), _esc(r.get("source_type")),
                    _esc(r.get("status")), _esc(r.get("note")),
                )
            )
        parts.append("</table>")

    parts.append(
        f"<div class='foot'>{_esc(meta.get('disclaimer'))}　医师署名：{_esc(meta.get('doctor_name')) or '—'}</div>"
    )
    parts.append("</body></html>")
    return "".join(parts)
