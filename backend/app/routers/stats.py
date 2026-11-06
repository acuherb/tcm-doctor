"""统计报表路由"""
from collections import Counter
from datetime import datetime, timedelta, time
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.prescription import Prescription, PrescriptionItem
from app.models.herb import Herb
from app.models.billing import Charge
from app.models.user import User

router = APIRouter(prefix="/stats", tags=["统计报表"])


@router.get("/dashboard", summary="工作台概览数据")
def dashboard_stats(db: Session = Depends(get_db)):
    """工作台首页统计数据"""
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # 今日就诊数（visit_date 存为 YYYY-MM-DD 字符串，用 date() 归一化后按日期比较）
    today_visits = db.query(Visit).filter(
        func.date(Visit.visit_date) == today.isoformat()
    ).count()

    # 患者总数
    total_patients = db.query(Patient).filter(Patient.deleted_at.is_(None)).count()

    # 药品总数
    total_herbs = db.query(Herb).filter(Herb.is_active == True).count()

    # 今日处方数
    today_prescriptions = db.query(Prescription).filter(
        Prescription.created_at.between(today_start, today_end)
    ).count()

    # 待审核处方数
    pending_prescriptions = db.query(Prescription).filter(
        Prescription.status == "已开"
    ).count()

    # 库存预警数（物品级最低库存）
    from app.models.stock import StockItem, StockBatch
    low_stock_count = 0
    items = db.query(StockItem).filter(StockItem.is_active == True, StockItem.min_stock > 0).all()
    for si in items:
        total = float(
            db.query(func.sum(StockBatch.quantity)).filter(
                StockBatch.item_id == si.id, StockBatch.status.in_(["正常", "近效期"])
            ).scalar() or 0
        )
        if total < float(si.min_stock or 0):
            low_stock_count += 1

    # 待回访提醒（应回访日期 <= 今天 且未完成的）
    from app.models.followup_reminder import FollowUpReminder

    due_reminders = (
        db.query(FollowUpReminder)
        .filter(FollowUpReminder.status == "pending", FollowUpReminder.due_date <= today.isoformat())
        .all()
    )
    rpids = {r.patient_id for r in due_reminders}
    rmap = {p.id: p.name for p in db.query(Patient).filter(Patient.id.in_(rpids)).all()} if rpids else {}
    # 排除已删除患者的孤儿提醒（历史删除未级联清理的），避免待办计数/展示指向不存在的患者
    due_reminders = [r for r in due_reminders if r.patient_id in rmap]
    pending_followups = len(due_reminders)
    followup_reminders = [
        {
            "id": r.id,
            "patient_id": r.patient_id,
            "patient_name": rmap.get(r.patient_id),
            "due_date": r.due_date,
            "note": r.note,
            "overdue": r.due_date < today.isoformat(),
        }
        for r in sorted(due_reminders, key=lambda x: x.due_date)[:10]
    ]

    # 最近7天就诊趋势
    seven_days_ago = today - timedelta(days=7)
    visit_trend = []
    for i in range(7):
        day = seven_days_ago + timedelta(days=i)
        count = db.query(Visit).filter(func.date(Visit.visit_date) == day.isoformat()).count()
        visit_trend.append({
            "date": day.strftime("%m-%d"),
            "count": count,
        })

    return {
        "today_visits": today_visits,
        "total_patients": total_patients,
        "total_herbs": total_herbs,
        "today_prescriptions": today_prescriptions,
        "pending_prescriptions": pending_prescriptions,
        "low_stock_count": low_stock_count,
        "pending_followups": pending_followups,
        "followup_reminders": followup_reminders,
        "visit_trend": visit_trend,
    }


@router.get("/visits", summary="就诊统计")
def visit_stats(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: Session = Depends(get_db),
):
    """就诊趋势统计"""
    today = datetime.now().date()
    start_date = datetime.combine(today - timedelta(days=days - 1), datetime.min.time())

    # 每日就诊数：从今天往回取最近 min(days, 60) 天。
    # 旧实现从「days 天前」开始迭代，days=365 时返回的是第 365~306 天，最近数据全缺。
    daily_stats = []
    span = min(days, 60)
    for i in range(span):
        day = today - timedelta(days=span - 1 - i)
        count = db.query(Visit).filter(func.date(Visit.visit_date) == day.isoformat()).count()
        daily_stats.append({"date": day.strftime("%Y-%m-%d"), "count": count})

    # 常见证型统计
    syndrome_stats = db.query(
        Visit.tcm_syndrome,
        func.count(Visit.id),
    ).filter(
        func.date(Visit.visit_date) >= start_date.date().isoformat(),
        func.date(Visit.visit_date) <= today.isoformat(),
        Visit.tcm_syndrome.isnot(None),
    ).group_by(Visit.tcm_syndrome).order_by(func.count(Visit.id).desc()).limit(10).all()

    total_visits = db.query(Visit).filter(
        func.date(Visit.visit_date) >= start_date.date().isoformat(),
        func.date(Visit.visit_date) <= today.isoformat(),
    ).count()
    return {
        "daily_stats": daily_stats,
        "syndrome_stats": [{"name": s, "count": c} for s, c in syndrome_stats if s],
        "total_visits": total_visits,
    }


@router.get("/herbs", summary="用药统计")
def herb_stats(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """用药频次统计"""
    start_date = datetime.now() - timedelta(days=days)

    # 最常用药物 (从处方明细中统计)
    herb_usage = db.query(
        PrescriptionItem.herb_name,
        func.count(PrescriptionItem.id).label("usage_count"),
        func.sum(PrescriptionItem.dose).label("total_dose"),
    ).join(
        Prescription, PrescriptionItem.prescription_id == Prescription.id
    ).filter(
        Prescription.created_at >= start_date,
        Prescription.status != "已取消",
    ).group_by(
        PrescriptionItem.herb_name,
    ).order_by(
        func.count(PrescriptionItem.id).desc(),
    ).limit(limit).all()

    return {
        "herb_usage": [
            {
                "name": h,
                "usage_count": int(c),
                "total_dose": float(t) if t else 0,
            }
            for h, c, t in herb_usage
        ],
        "period_days": days,
    }


@router.get("/prescriptions", summary="处方统计")
def prescription_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """处方统计"""
    start_date = datetime.now() - timedelta(days=days)

    total = db.query(Prescription).filter(
        Prescription.created_at >= start_date,
        Prescription.status != "已取消",
    ).count()

    # 按状态统计
    status_stats = db.query(
        Prescription.status,
        func.count(Prescription.id),
    ).filter(
        Prescription.created_at >= start_date,
        Prescription.status != "已取消",
    ).group_by(Prescription.status).all()

    # 常用方剂统计
    formula_stats = db.query(
        Prescription.formula_name,
        func.count(Prescription.id),
    ).filter(
        Prescription.created_at >= start_date,
        Prescription.formula_name.isnot(None),
    ).group_by(Prescription.formula_name).order_by(
        func.count(Prescription.id).desc()
    ).limit(10).all()

    return {
        "total": total,
        "status_stats": [{"status": s, "count": c} for s, c in status_stats],
        "formula_stats": [{"name": n or "自拟方", "count": c} for n, c in formula_stats],
        "period_days": days,
    }

def _span(days: int):
    """近 days 天（含今天）的日期区间；图表最多展示 60 天，避免 365 天时前端挤成一团。"""
    today = datetime.now().date()
    start = today - timedelta(days=days - 1)
    span = min(days, 60)
    return today, start, [today - timedelta(days=span - 1 - i) for i in range(span)]


def _dec(value) -> Decimal:
    """金额统一量化到分，避免 Decimal / float 混算产生分位漂移。"""
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _top(counter: Counter, limit: int = 8) -> list[dict]:
    return [{"name": k, "count": v} for k, v in counter.most_common(limit)]


def _age_of(birth: str | None, today) -> int | None:
    if not birth:
        return None
    try:
        y, m, d = (int(x) for x in str(birth)[:10].split("-"))
    except Exception:
        return None
    age = today.year - y - ((today.month, today.day) < (m, d))
    return age if 0 <= age <= 120 else None


@router.get("/registration", summary="挂号统计（趋势 / 科室医师 / 完成率 / 挂号费）")
def registration_stats(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """只统计有排队号的挂号记录，口径与挂号台「今日队列」一致。"""
    today, start, axis = _span(days)
    visits = (
        db.query(Visit)
        .filter(
            func.date(Visit.visit_date) >= start.isoformat(),
            func.date(Visit.visit_date) <= today.isoformat(),
            Visit.queue_no.isnot(None),
        )
        .all()
    )
    daily = {d.isoformat(): 0 for d in axis}
    for v in visits:
        key = str(v.visit_date)[:10]
        if key in daily:
            daily[key] += 1
    status = Counter(v.status or "未知" for v in visits)
    department = Counter((v.department or "未分诊") for v in visits)
    doctor_ids = {v.doctor_id for v in visits if v.doctor_id}
    doctor_names = {
        u.id: (u.display_name or u.username)
        for u in db.query(User).filter(User.id.in_(doctor_ids)).all()
    } if doctor_ids else {}
    doctor = Counter(doctor_names.get(v.doctor_id, "未指定医师") for v in visits)

    # 挂号费：应收取就诊快照，实收/待收取收费单，避免把处方收费算进来
    visit_ids = [v.id for v in visits]
    charges = (
        db.query(Charge).filter(Charge.kind == "registration", Charge.visit_id.in_(visit_ids)).all()
        if visit_ids else []
    )
    collected = Decimal("0.00")
    pending = Decimal("0.00")
    for c in charges:
        if c.status == "待收费":
            pending += _dec(c.payable)
        elif c.status in ("已收费", "已退费"):
            collected += _dec(c.paid) - (_dec(c.refund_amount) if c.status == "已退费" else Decimal("0.00"))
    completed = status.get("已完成", 0)
    valid = len(visits) - status.get("已取消", 0)
    return {
        "total": len(visits),
        "daily_stats": [{"date": d, "count": n} for d, n in sorted(daily.items())],
        "status_stats": _top(status, 10),
        "department_stats": _top(department),
        "doctor_stats": _top(doctor),
        "completion_rate": round(completed * 100 / valid, 1) if valid else 0.0,
        "fee": {
            "payable": float(sum((_dec(v.registration_fee) for v in visits), Decimal("0.00"))),
            "collected": float(_dec(collected)),
            "pending": float(_dec(pending)),
        },
    }


@router.get("/charges", summary="收费统计（营收趋势 / 类型 / 支付方式 / 退费率）")
def charge_trend_stats(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """金额口径与 /billing/charges/stats/summary 保持一致：净营收 = 累计实收 - 实退。"""
    today, start, axis = _span(days)
    charges = (
        db.query(Charge)
        .filter(
            Charge.created_at >= datetime.combine(start, time.min),
            Charge.created_at <= datetime.combine(today, time.max),
        )
        .all()
    )
    daily = {d.isoformat(): {"collected": Decimal("0.00"), "refunded": Decimal("0.00")} for d in axis}
    kinds: dict[str, dict] = {}
    payments: dict[str, dict] = {}
    collected = refunded = pending = Decimal("0.00")
    paid_count = refunded_count = pending_count = 0
    for c in charges:
        paid, ref = _dec(c.paid), _dec(c.refund_amount)
        kind = c.kind or "prescription"
        kd = kinds.setdefault(kind, {"count": 0, "net": Decimal("0.00"), "pending": Decimal("0.00")})
        kd["count"] += 1
        if c.status == "待收费":
            pending += _dec(c.payable)
            kd["pending"] += _dec(c.payable)
            pending_count += 1
        elif c.status == "已收费":
            collected += paid
            kd["net"] += paid
            paid_count += 1
        elif c.status == "已退费":
            collected += paid
            refunded += ref
            kd["net"] += paid - ref
            refunded_count += 1
        if c.status in ("已收费", "已退费"):
            pm = c.payment_method or "未填写"
            pe = payments.setdefault(pm, {"count": 0, "amount": Decimal("0.00")})
            pe["count"] += 1
            pe["amount"] += paid - (ref if c.status == "已退费" else Decimal("0.00"))
        if c.created_at:
            key = c.created_at.date().isoformat()
            if key in daily:
                if c.status in ("已收费", "已退费"):
                    daily[key]["collected"] += paid
                if c.status == "已退费":
                    daily[key]["refunded"] += ref
    settled = paid_count + refunded_count
    return {
        "daily_stats": [
            {
                "date": d,
                "collected": float(_dec(v["collected"])),
                "refunded": float(_dec(v["refunded"])),
                "net": float(_dec(v["collected"] - v["refunded"])),
            }
            for d, v in sorted(daily.items())
        ],
        "kind_stats": [
            {
                "kind": k,
                "name": "挂号费" if k == "registration" else "处方收费",
                "count": v["count"],
                "net_amount": float(_dec(v["net"])),
                "pending_amount": float(_dec(v["pending"])),
            }
            for k, v in sorted(kinds.items())
        ],
        "payment_stats": [
            {"name": k, "count": v["count"], "amount": float(_dec(v["amount"]))}
            for k, v in sorted(payments.items(), key=lambda kv: -kv[1]["amount"])
        ],
        "totals": {
            "collected_amount": float(_dec(collected)),
            "refunded_amount": float(_dec(refunded)),
            "net_amount": float(_dec(collected - refunded)),
            "pending_amount": float(_dec(pending)),
            "total_count": len(charges),
            "paid_count": paid_count,
            "refunded_count": refunded_count,
            "pending_count": pending_count,
            "refund_rate": round(refunded_count * 100 / settled, 1) if settled else 0.0,
        },
    }


# 统计归并口径：主经优先，判定状态次之；桶名与患者列表的「证候偏性」筛选项保持一致。
# 注意与 /stats/visits 的 syndrome_stats（就诊证型频次）语义不同，勿混用。
MERIDIAN_NAMES = ("太阳", "阳明", "少阳", "太阴", "少阴", "厥阴")
SYNDROME_BUCKETS = ("平和", "需四诊合参")
HISTORY_CONSTITUTION_BUCKET = "历史九种体质记录"
OTHER_SYNDROME_BUCKET = "其他/待归类"
_DECISION_BUCKETS = {
    "balanced": "平和",
    "insufficient": "需四诊合参",
    "undetermined": "需四诊合参",
    "legacy": "历史记录(未标注体系)",
}


def _syndrome_of(patient) -> list[str]:
    """把患者主标签归并到「六经主经 + 判定状态」桶，兼容早期长标签与九种体质旧数据。"""
    score = patient.constitution_score if isinstance(patient.constitution_score, dict) else {}
    raw_detail = score.get("detail")
    detail = raw_detail if isinstance(raw_detail, dict) else {}
    mains = [m for m in (score.get("primary_meridians") or detail.get("primary_meridians") or [])
             if m in MERIDIAN_NAMES][:2]
    if mains:
        return mains
    decision = detail.get("decision")
    if decision in _DECISION_BUCKETS:
        return [_DECISION_BUCKETS[decision]]

    label = patient.constitution_type or ""
    if not label:
        return []
    if "平和" in label:
        return ["平和"]
    if "需四诊合参" in label:
        return ["需四诊合参"]
    found = [m for m in MERIDIAN_NAMES if m in label][:2]
    if found:
        return found
    if "质" in label:  # 阳虚质/痰湿质等王琦九种体质历史记录，不再混入六经统计
        return [HISTORY_CONSTITUTION_BUCKET]
    return [OTHER_SYNDROME_BUCKET]


@router.get("/patients", summary="患者统计（新增趋势 / 复诊率 / 画像分布）")
def patient_stats(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """只统计未归档患者；复诊率 = 有就诊记录且累计就诊 ≥2 次的患者占比。"""
    today, start, axis = _span(days)
    patients = db.query(Patient).filter(Patient.deleted_at.is_(None)).all()
    live_ids = {p.id for p in patients}
    daily = {d.isoformat(): 0 for d in axis}
    new_this_month = 0
    gender = Counter()
    age_buckets = Counter()
    constitution = Counter()
    syndrome = Counter()
    for p in patients:
        created = p.created_at
        if created:
            key = created.date().isoformat()
            if key in daily:
                daily[key] += 1
            if created.year == today.year and created.month == today.month:
                new_this_month += 1
        gender[p.gender or "未填写"] += 1
        age = _age_of(p.birth_date, today)
        if age is None:
            age_buckets["未填写"] += 1
        elif age <= 18:
            age_buckets["0-18岁"] += 1
        elif age <= 35:
            age_buckets["19-35岁"] += 1
        elif age <= 50:
            age_buckets["36-50岁"] += 1
        elif age <= 65:
            age_buckets["51-65岁"] += 1
        else:
            age_buckets["66岁以上"] += 1
        constitution[p.constitution_type or "未评估"] += 1
        mains = _syndrome_of(p)
        if mains:
            for m in mains:
                syndrome[m] += 1
        else:
            syndrome["未评估"] += 1

    visit_counts = (
        db.query(Visit.patient_id, func.count(Visit.id))
        .group_by(Visit.patient_id)
        .all()
    )
    with_visits = [c for pid, c in visit_counts if pid in live_ids]
    returning = sum(1 for c in with_visits if c >= 2)
    age_order = ["0-18岁", "19-35岁", "36-50岁", "51-65岁", "66岁以上", "未填写"]
    return {
        "total_patients": len(patients),
        "new_this_month": new_this_month,
        "returning_rate": round(returning * 100 / len(with_visits), 1) if with_visits else 0.0,
        "daily_new": [{"date": d, "count": n} for d, n in sorted(daily.items())],
        "gender_stats": _top(gender, 10),
        "age_stats": [{"name": k, "count": age_buckets[k]} for k in age_order if age_buckets[k]],
        "constitution_stats": _top(constitution),  # 兼容旧调用方：原始主标签逐条计数
        "syndrome_stats": _top(syndrome, 10),  # 按主经/判定状态归并，与患者列表筛选项同口径
    }
