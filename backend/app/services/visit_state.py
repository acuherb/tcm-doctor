"""就诊状态判定的共享业务事实。

挂号登记会先创建一条占位就诊（主诉「（待接诊）」），医生在患者详情完善病历后
才应视为真正开始诊疗。此判定同时被挂号路由（能否「完成」）与患者就诊路由
（保存病历后自动推进「已接诊」）使用，避免两处口径漂移。
"""

PLACEHOLDER_COMPLAINT = "（待接诊）"


def has_real_record(v) -> bool:
    """是否已留下真实诊疗记录：主诉脱离占位符，且至少有一项四诊/诊断/治法/医嘱。"""
    complaint = (v.chief_complaint or "").strip()
    detail_fields = (
        v.present_illness, v.observation, v.auscultation, v.inquiry, v.palpation,
        v.tongue_body, v.tongue_coat, v.pulse, v.tcm_disease, v.tcm_syndrome,
        v.treatment_method, v.doctor_notes, v.ai_analysis, v.doctor_id,
    )
    return bool(complaint and complaint != PLACEHOLDER_COMPLAINT and any(detail_fields))
