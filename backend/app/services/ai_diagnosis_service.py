"""AI 智能辨证服务 — DeepSeek API + RAG"""
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.herb import Herb, IncompatibilityRule
from app.models.knowledge import KnowledgeEntry
from app.services.incompatibility_checker import (
    check_prescription_herbs,
    check_dosage_limits,
    check_pregnancy_contraindications,
)


# ── System Prompt ──

TCM_SYSTEM_PROMPT = """你是一位以「倪海厦经方体系」为根基的中医师，临床以《伤寒论》《金匮要略》六经辨证为纲，善用经方原量、重剂与柴胡剂枢机。请遵循以下原则：

1. **六经辨证为纲**：先判病在何经——太阳（表证、恶寒发热、脉浮）、阳明（里热实、高热汗出、便秘）、少阳（半表半里、往来寒热、胸胁苦满、口苦咽干）、太阴（里虚寒、腹满便溏）、少阴（心肾虚衰、但欲寐、手足逆冷、脉微细）、厥阴（寒热错杂、消渴、气上撞心、久病肝系）。
2. **问诊十问定六经**：结合患者已填的问诊十问定经——睡眠 1–3 点易醒→肝(厥阴)热扰；3–5 点易醒→肺(太阴)；手脚冰冷→心阳/少阴不足；小便清长→里寒/少阴；并综合寒热、汗出、口渴、饮食、情志等。请给出六经归属，不要凭空臆断。
3. **经方优先、原方原量**：优先推荐《伤寒论》《金匮要略》经方，给出方名、原方剂量构成与加减；剂量可参考经方原量思路（如柴胡常用重剂以畅少阳枢机），并说明现代换算与因人制宜。
4. **理法方药闭环**：病机→治法→方剂→药味剂量，条理清晰，并引用经典原文支撑。
5. **安全性**：必须排查十八反十九畏、毒性药剂量上限、孕妇禁忌；出现禁忌须明确警示。
6. **术语规范**：使用规范中医名词术语。
7. **免责声明**：每次回复末尾加上"⚠️ 本分析由AI辅助生成，仅供参考，不替代专业中医师面诊。"
8. **中西医结合**：如提供西医诊断（病名、化验指标、影像报告），应解读其临床意义，从中医辨病名与证型，提出中西医结合方案，并标注哪些以中医为主、哪些需西医优先。
9. **图片解读**：舌苔/面色/化验单照片应描述并辨证，注明仅供参考，临床需四诊合参。

请用中文回答，保持专业性与可读性。"""


class DiagnosisService:
    """AI智能辨证服务"""

    # ── DB 辅助 ──

    def _get_or_create_conversation(self, conversation_id: str | None, db: Session, patient_id: int | None = None):
        """按 uuid 查找或新建 Conversation 行，返回 (ConvORM, uuid_str)"""
        from app.models.conversation import Conversation
        if conversation_id:
            conv = db.query(Conversation).filter(Conversation.uuid == conversation_id).first()
            if conv:
                return conv, conversation_id
        # 新建
        new_uuid = conversation_id or str(uuid.uuid4())
        conv = Conversation(uuid=new_uuid, patient_id=patient_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv, new_uuid

    def _build_messages_from_db(self, conv, db: Session, limit: int = 40) -> list[dict]:
        """从 DB 读取历史消息，构建 DeepSeek API 格式"""
        from app.models.conversation import Message
        db_msgs = db.query(Message).filter(
            Message.conversation_id == conv.id
        ).order_by(Message.seq.desc()).limit(limit).all()
        db_msgs.reverse()

        result = []
        for m in db_msgs:
            if m.images:
                # 多模态消息：还原为 content_parts
                content_parts: list[dict] = [{"type": "text", "text": m.content}]
                for img in m.images:
                    if isinstance(img, dict) and "url" in img:
                        content_parts.append({"type": "image_url", "image_url": {"url": img["url"]}})
                    elif isinstance(img, str):
                        content_parts.append({"type": "image_url", "image_url": {"url": img}})
                result.append({"role": m.role, "content": content_parts})
            else:
                result.append({"role": m.role, "content": m.content})
        return result

    def _save_message(self, conv, seq: int, role: str, content: str, db: Session,
                      images: list | None = None, warnings: list | None = None):
        """写入一条 Message 并更新 Conversation 冗余字段"""
        from app.models.conversation import Message
        msg = Message(
            conversation_id=conv.id,
            seq=seq,
            role=role,
            content=content,
            images=images,
            warnings=warnings,
        )
        db.add(msg)
        conv.message_count = (conv.message_count or 0) + 1
        conv.last_message_at = datetime.now()
        db.commit()

    # ── 非流式 chat（保留兼容） ──

    async def chat(
        self,
        message: str,
        images: list[str] | None = None,
        conversation_id: str | None = None,
        patient_id: int | None = None,
        visit_id: int | None = None,
        db: Session | None = None,
    ) -> dict:
        """对话式智能问诊"""
        if not settings.deepseek_api_key:
            return {
                "conversation_id": conversation_id or "demo",
                "reply": "⚠️ DeepSeek API Key 未配置，请在系统设置中配置后使用。",
                "safety_warnings": [],
            }

        conv, conv_id = self._get_or_create_conversation(conversation_id, db, patient_id)

        # 首次消息自动设标题
        if not conv.title and message:
            conv.title = message[:50] + ("..." if len(message) > 50 else "")
            db.commit()

        # RAG
        context = ""
        if db:
            context = await self._retrieve_context(message, db)

        # 构建 API 消息
        api_messages = [{"role": "system", "content": TCM_SYSTEM_PROMPT}]
        if context:
            api_messages.append({"role": "system", "content": f"参考以下中医知识库内容：\n\n{context}"})
        api_messages.extend(self._build_messages_from_db(conv, db))
        user_msg = self._build_user_message(message, images)
        api_messages.append(user_msg)

        # 调用 API
        has_images = bool(images)
        reply = await self._call_deepseek(api_messages, use_vision=has_images)
        safety_warnings = self._check_safety_in_reply(reply, db)

        # 持久化消息
        next_seq = (conv.message_count or 0) + 1
        img_data = [{"url": u} for u in images] if images else None
        self._save_message(conv, next_seq, "user", message, db, images=img_data)
        self._save_message(conv, next_seq + 1, "assistant", reply, db, warnings=safety_warnings)

        return {
            "conversation_id": conv_id,
            "reply": reply,
            "suggested_syndrome": None,
            "suggested_formula": None,
            "safety_warnings": safety_warnings,
        }

    async def analyze(
        self,
        observation: str | None = None,
        auscultation: str | None = None,
        inquiry: str | None = None,
        palpation: str | None = None,
        tongue_body: str | None = None,
        tongue_coat: str | None = None,
        pulse: str | None = None,
        chief_complaint: str | None = None,
        patient_gender: str | None = None,
        is_pregnant: bool | None = None,
        ten_aspects: str | None = None,
        ten_answers: dict | None = None,
        tongue_image: str | None = None,
        face_image: str | None = None,
        lab_report_images: list[str] | None = None,
        db: Session | None = None,
    ) -> dict:
        """四诊信息 → 辨证分析（支持图片）"""
        if not settings.deepseek_api_key:
            return self._rule_based_analyze(
                chief_complaint=chief_complaint,
                observation=observation,
                auscultation=auscultation,
                inquiry=inquiry,
                palpation=palpation,
                tongue_body=tongue_body,
                tongue_coat=tongue_coat,
                pulse=pulse,
                ten_aspects=ten_aspects,
                ten_answers=ten_answers,
            )

        # 构建四诊摘要
        four_diag = []
        if chief_complaint:
            four_diag.append(f"【主诉】{chief_complaint}")
        if observation:
            four_diag.append(f"【望诊】{observation}")
        if auscultation:
            four_diag.append(f"【闻诊】{auscultation}")
        if inquiry:
            four_diag.append(f"【问诊】{inquiry}")
        if palpation:
            four_diag.append(f"【切诊】{palpation}")
        if tongue_body or tongue_coat:
            four_diag.append(f"【舌象】舌质{tongue_body or '未记录'}，舌苔{tongue_coat or '未记录'}")
        if pulse:
            four_diag.append(f"【脉象】{pulse}")
        if ten_aspects:
            four_diag.append(f"【问诊十问】\n{ten_aspects}")

        patient_info = ""
        if patient_gender:
            patient_info += f"患者性别：{patient_gender}。"
        if is_pregnant:
            patient_info += "⚠️患者为孕妇，需注意孕妇禁忌。"

        user_message = f"请根据以下四诊信息进行辨证分析：\n\n{patient_info}\n" + "\n".join(four_diag)
        user_message += "\n\n请给出：1.病机分析 2.中医病名 3.证型 4.治法 5.推荐方剂及加减 6.调护建议"
        user_message += (
            "\n\n排版要求：对比类内容（如线索/分析/六经指向）请使用 Markdown 表格语法"
            "（每行以 | 分隔列，并在表头下一行写 |---|---|），不要使用制表符或纯空格分隔，"
            "也不要使用一级/二级大标题，统一用三级及以下小标题。"
        )
        user_message += (
            "\n\n请在回答末尾额外输出一个 ```json 代码块，键名为 recommended_formulas，"
            "内容为方剂数组；每个元素包含：name(方名)、composition(药物与剂量，示例 "
            "'桂枝9g 芍药9g 生姜9g 大枣4枚 炙甘草6g')、modification(随证加减)、indication(方解/适应症)。"
            "不要在该代码块之外再解释它。"
        )

        # RAG
        context = ""
        search_query = chief_complaint or " ".join(filter(None, [observation, inquiry, pulse]))
        if db and search_query:
            context = await self._retrieve_context(search_query, db)

        messages = [{"role": "system", "content": TCM_SYSTEM_PROMPT}]
        if context:
            messages.append({
                "role": "system",
                "content": f"参考以下中医知识库内容：\n\n{context}"
            })

        # 构建多模态用户消息
        content_parts: list[dict] = [{"type": "text", "text": user_message}]
        if tongue_image:
            content_parts.append({"type": "text", "text": "【舌象照片】请仔细观察以下舌象照片："})
            content_parts.append({"type": "image_url", "image_url": {"url": tongue_image}})
        if face_image:
            content_parts.append({"type": "text", "text": "【面色照片】请观察以下面色照片："})
            content_parts.append({"type": "image_url", "image_url": {"url": face_image}})
        if lab_report_images:
            content_parts.append({"type": "text", "text": "【化验单/影像报告】请解读以下检查报告："})
            for img in lab_report_images:
                content_parts.append({"type": "image_url", "image_url": {"url": img}})

        # 如果有图片用多模态格式，否则用纯文本
        if len(content_parts) > 1:
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": user_message})

        has_images = bool(tongue_image or face_image or lab_report_images)
        reply = await self._call_deepseek(messages, use_vision=has_images)
        safety_warnings = self._check_safety_in_reply(reply, db)

        # 从分析文本中解析出病名/证型/治法，供就诊表单自动填入
        structured = self._parse_structured(reply)
        # 解析文末的推荐方剂 JSON，供前端「方剂建议/选择」与一键开药
        formulas = self._parse_formulas(reply)

        return {
            "syndrome_analysis": reply,
            "tcm_disease": structured.get("tcm_disease"),
            "tcm_syndrome": structured.get("tcm_syndrome"),
            "treatment_method": structured.get("treatment_method"),
            "recommended_formulas": formulas,
            "safety_warnings": safety_warnings,
            "references": [],
        }

    def _rule_based_analyze(
        self,
        chief_complaint: str | None = None,
        observation: str | None = None,
        auscultation: str | None = None,
        inquiry: str | None = None,
        palpation: str | None = None,
        tongue_body: str | None = None,
        tongue_coat: str | None = None,
        pulse: str | None = None,
        ten_aspects: str | None = None,
        ten_answers: dict | None = None,
    ) -> dict:
        """未配置 API Key 时的降级辨证：基于「问诊十问」规则引擎 + 四诊文本，生成可回填的真实辨证结果（零成本、即时）"""
        from app.services.constitution_evaluator import evaluate_constitution

        answers = (ten_answers or {}).get("answers") or {}
        notes = (ten_answers or {}).get("notes") or {}
        rule = evaluate_constitution(answers, notes)

        lines = []
        if chief_complaint:
            lines.append(f"【主诉】{chief_complaint}")
        if observation:
            lines.append(f"【望诊】{observation}")
        if auscultation:
            lines.append(f"【闻诊】{auscultation}")
        if inquiry:
            lines.append(f"【问诊】{inquiry}")
        if palpation:
            lines.append(f"【切诊】{palpation}")
        if tongue_body or tongue_coat:
            lines.append(f"【舌象】舌质{tongue_body or '未记录'}，舌苔{tongue_coat or '未记录'}")
        if pulse:
            lines.append(f"【脉象】{pulse}")
        had_ten_answers = bool(answers)
        if ten_aspects:
            lines.append(f"【问诊十问】\n{ten_aspects}")

        parts = []
        header = "本辨证基于「经方家问诊十问」规则推理引擎即时得出（未调用云 API）。"
        if had_ten_answers:
            parts.append(f"{header}\n")
            parts.append(f"主归偏性：{rule['primary_type']}")
            if rule.get("secondary_types"):
                parts.append("倾向：" + "、".join(rule["secondary_types"]))
            if rule.get("findings"):
                parts.append("\n判据解析：\n" + "\n".join(f"- {f}" for f in rule["findings"]))
            if rule.get("suggestion"):
                parts.append("\n方域提示：" + rule["suggestion"])
            parts.append("\n提示：以上为规则推理初判，供参考；若需更深入的自然语言辨证，请在系统设置中配置 DeepSeek API Key（作为增强）。")
        else:
            header = "尚未填写「问诊十问」，暂无法进行准确辨证。请先在就诊页右侧完成问诊十问逐项回答，即可获得基于倪海厦判据的即时辨证结果；配置 DeepSeek API Key 后亦可用 AI 综合分析。"
            parts.append(header)

        analysis = "\n".join(parts)

        # 结构化回填：主证作为证型；治法从方域提示推导；病名缺省由主诉推断
        tcm_syndrome = rule["primary_type"] if had_ten_answers else None
        tcm_disease = None
        treatment_method = None
        if had_ten_answers:
            tcm_disease = _infer_disease_from_complaint(chief_complaint)
            treatment_method = _infer_method_from_meridian(rule.get("primary_meridians") or [])

        return {
            "syndrome_analysis": analysis,
            "tcm_disease": tcm_disease,
            "tcm_syndrome": tcm_syndrome,
            "treatment_method": treatment_method,
            "recommended_formulas": [],
            "safety_warnings": ["当前未配置 API Key，此为本地规则辨证结果；建议核对后使用。"],
            "references": [],
        }

    def _parse_structured(self, reply: str) -> dict:
        """从四诊分析文本中启发式提取中医病名/证型/治法，供表单结构化回填"""
        import re

        def _pick(disease: bool, syndrome: bool, method: bool):
            label = "中医病名" if disease else "证型" if syndrome else "治法"
            m = re.search(re.escape(label) + r"\s*[：:]\s*([^\n]+)", reply)
            if not m:
                return None
            val = m.group(1).strip().strip("，。、；;,:： ")
            # 去掉开头编号数字
            val = re.sub(r"^\d+[\.、)]\s*", "", val).strip()
            if not val or len(val) > 60:
                return None
            return val

        return {
            "tcm_disease": _pick(True, False, False),
            "tcm_syndrome": _pick(False, True, False),
            "treatment_method": _pick(False, False, True),
        }

    def _parse_formulas(self, reply: str) -> list[dict]:
        """从辨证分析文本中解析推荐方剂（期望文末 ```json 代码块，键 recommended_formulas）"""
        import json as _json
        import re

        if not reply:
            return []
        # 1) 优先匹配 fenced json 块
        m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", reply, re.DOTALL)
        raw = m.group(1) if m else None
        if not raw:
            # 2) 退化：直接定位首个 [ ... ] 数组
            s, e = reply.find("["), reply.rfind("]")
            if s != -1 and e > s:
                raw = reply[s:e + 1]
        if not raw:
            return []
        try:
            data = _json.loads(raw)
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        out: list[dict] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or item.get("方剂") or "").strip()
            comp = item.get("composition") or item.get("组成") or item.get("药物") or ""
            if isinstance(comp, list):
                comp = " ".join(str(c) for c in comp)
            out.append({
                "name": name,
                "composition": str(comp or "").strip(),
                "modification": str(item.get("modification") or item.get("加减") or "").strip(),
                "indication": str(item.get("indication") or item.get("方解") or item.get("适应症") or "").strip(),
            })
        return out

    async def analyze_stream(
        self,
        observation: str | None = None,
        auscultation: str | None = None,
        inquiry: str | None = None,
        palpation: str | None = None,
        tongue_body: str | None = None,
        tongue_coat: str | None = None,
        pulse: str | None = None,
        chief_complaint: str | None = None,
        patient_gender: str | None = None,
        is_pregnant: bool | None = None,
        ten_aspects: str | None = None,
        ten_answers: dict | None = None,
        tongue_image: str | None = None,
        face_image: str | None = None,
        lab_report_images: list[str] | None = None,
        db: Session | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式四诊辨证分析"""
        if not settings.deepseek_api_key:
            fallback = self._rule_based_analyze(
                chief_complaint=chief_complaint,
                observation=observation,
                auscultation=auscultation,
                inquiry=inquiry,
                palpation=palpation,
                tongue_body=tongue_body,
                tongue_coat=tongue_coat,
                pulse=pulse,
                ten_aspects=ten_aspects,
                ten_answers=ten_answers,
            )
            text = (fallback.get("syndrome_analysis") or "") + "\n"
            for line in text.split("\n"):
                if line:
                    yield f"data: {json.dumps({'type': 'content', 'content': line + '\n'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        four_diag = []
        if chief_complaint:
            four_diag.append(f"【主诉】{chief_complaint}")
        if observation:
            four_diag.append(f"【望诊】{observation}")
        if auscultation:
            four_diag.append(f"【闻诊】{auscultation}")
        if inquiry:
            four_diag.append(f"【问诊】{inquiry}")
        if palpation:
            four_diag.append(f"【切诊】{palpation}")
        if tongue_body or tongue_coat:
            four_diag.append(f"【舌象】舌质{tongue_body or '未记录'}，舌苔{tongue_coat or '未记录'}")
        if pulse:
            four_diag.append(f"【脉象】{pulse}")
        if ten_aspects:
            four_diag.append(f"【问诊十问】\n{ten_aspects}")

        patient_info = ""
        if patient_gender:
            patient_info += f"患者性别：{patient_gender}。"
        if is_pregnant:
            patient_info += "⚠️患者为孕妇，需注意孕妇禁忌。"

        user_message = f"请根据以下四诊信息进行辨证分析：\n\n{patient_info}\n" + "\n".join(four_diag)
        user_message += "\n\n请给出：1.病机分析 2.中医病名 3.证型 4.治法 5.推荐方剂及加减 6.调护建议"
        user_message += (
            "\n\n排版要求：对比类内容（如线索/分析/六经指向）请使用 Markdown 表格语法"
            "（每行以 | 分隔列，并在表头下一行写 |---|---|），不要使用制表符或纯空格分隔，"
            "也不要使用一级/二级大标题，统一用三级及以下小标题。"
        )

        context = ""
        search_query = chief_complaint or " ".join(filter(None, [observation, inquiry, pulse]))
        if db and search_query:
            context = await self._retrieve_context(search_query, db)

        messages = [{"role": "system", "content": TCM_SYSTEM_PROMPT}]
        if context:
            messages.append({"role": "system", "content": f"参考以下中医知识库内容：\n\n{context}"})

        content_parts: list[dict] = [{"type": "text", "text": user_message}]
        if tongue_image:
            content_parts.append({"type": "text", "text": "【舌象照片】请仔细观察以下舌象照片："})
            content_parts.append({"type": "image_url", "image_url": {"url": tongue_image}})
        if face_image:
            content_parts.append({"type": "text", "text": "【面色照片】请观察以下面色照片："})
            content_parts.append({"type": "image_url", "image_url": {"url": face_image}})
        if lab_report_images:
            content_parts.append({"type": "text", "text": "【化验单/影像报告】请解读以下检查报告："})
            for img in lab_report_images:
                content_parts.append({"type": "image_url", "image_url": {"url": img}})

        if len(content_parts) > 1:
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": user_message})

        has_images = bool(tongue_image or face_image or lab_report_images)
        full_reply = ""
        async for chunk in self._call_deepseek_stream(messages, use_vision=has_images):
            full_reply += chunk
            yield f"data: {json.dumps({'type': 'content', 'content': chunk}, ensure_ascii=False)}\n\n"

        safety_warnings = self._check_safety_in_reply(full_reply, db)
        yield f"data: {json.dumps({'type': 'warnings', 'warnings': safety_warnings}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    def _build_user_message(self, message: str, images: list[str] | None = None) -> dict:
        """构建用户消息，支持多模态（文字+图片）"""
        if not images:
            return {"role": "user", "content": message}

        content_parts: list[dict] = [{"type": "text", "text": message}]
        for img_url in images:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": img_url}
            })
        return {"role": "user", "content": content_parts}

    async def _retrieve_context(self, query: str, db: Session, top_k: int = 5) -> str:
        """RAG 多路召回"""
        contexts = []

        # 1. 关键词检索 (SQL)
        try:
            entries = db.query(KnowledgeEntry).filter(
                (KnowledgeEntry.title.contains(query)) | (KnowledgeEntry.content.contains(query))
            ).limit(top_k).all()
            for e in entries:
                contexts.append(f"[{e.category}] {e.title}\n{e.content[:500]}")
        except Exception:
            pass

        # 2. 语义检索 (ChromaDB) — 如果可用
        try:
            from app.services.vector_store import vector_store
            vector_results = vector_store.search(query, top_k=top_k)
            for r in vector_results:
                contexts.append(f"[{r.get('category', '知识库')}] {r.get('title', '')}\n{r.get('content', '')[:500]}")
        except ImportError:
            pass  # ChromaDB 未安装
        except Exception:
            pass  # 向量检索失败，降级到关键词

        if not contexts:
            return ""

        return "\n\n---\n\n".join(contexts[:8])

    async def _call_deepseek(self, messages: list[dict], use_vision: bool = False) -> str:
        """调用 DeepSeek API — 有图片时使用 Vision 端点，无 Vision 配置时降级为纯文字"""
        # 判断是否有 Vision 能力
        vision_model = settings.deepseek_vision_model
        vision_base_url = settings.deepseek_vision_base_url or settings.deepseek_base_url
        vision_api_key = settings.deepseek_vision_api_key or settings.deepseek_api_key

        if use_vision and not vision_model:
            # 无 Vision 配置：剥离图片，只保留文字描述
            messages = self._strip_images(messages)

        # 选择模型、端点和 Key
        if use_vision and vision_model:
            model = vision_model
            base_url = vision_base_url
            api_key = vision_api_key
        else:
            model = settings.deepseek_model
            base_url = settings.deepseek_base_url
            api_key = settings.deepseek_api_key

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0), trust_env=False) as client:
                response = await client.post(
                    f"{base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 4000,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            return "⚠️ 请求超时，请稍后重试。"
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("error", {}).get("message", "") or e.response.text[:200]
            except Exception:
                detail = e.response.text[:200]
            return f"⚠️ API 调用失败 (HTTP {e.response.status_code}): {detail}"
        except Exception as e:
            return f"⚠️ 请求出错: {str(e)}"

    async def _call_deepseek_stream(self, messages: list[dict], use_vision: bool = False) -> AsyncGenerator[str, None]:
        """流式调用 DeepSeek API，逐块 yield 文本内容"""
        vision_model = settings.deepseek_vision_model
        vision_base_url = settings.deepseek_vision_base_url or settings.deepseek_base_url
        vision_api_key = settings.deepseek_vision_api_key or settings.deepseek_api_key

        if use_vision and not vision_model:
            messages = self._strip_images(messages)

        if use_vision and vision_model:
            model = vision_model
            base_url = vision_base_url
            api_key = vision_api_key
        else:
            model = settings.deepseek_model
            base_url = settings.deepseek_base_url
            api_key = settings.deepseek_api_key

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0), trust_env=False) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 4000,
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except httpx.TimeoutException:
            yield "⚠️ 请求超时，请稍后重试。"
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("error", {}).get("message", "") or str(e.response.status_code)
            except Exception:
                detail = str(e.response.status_code)
            yield f"⚠️ API 调用失败 (HTTP {e.response.status_code}): {detail}"
        except Exception as e:
            yield f"⚠️ 请求出错: {str(e)}"

    async def chat_stream(
        self,
        message: str,
        images: list[str] | None = None,
        conversation_id: str | None = None,
        patient_id: int | None = None,
        visit_id: int | None = None,
        db: Session | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式对话式智能问诊"""
        if not settings.deepseek_api_key:
            yield f"data: {json.dumps({'type': 'error', 'content': '⚠️ DeepSeek API Key 未配置'}, ensure_ascii=False)}\n\n"
            return

        conv, conv_id = self._get_or_create_conversation(conversation_id, db, patient_id)

        # 首次消息自动设标题
        if not conv.title and message:
            conv.title = message[:50] + ("..." if len(message) > 50 else "")
            db.commit()

        # 发送 conversation_id
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"

        # RAG
        context = ""
        if db:
            context = await self._retrieve_context(message, db)

        # 构建 API 消息
        api_messages = [{"role": "system", "content": TCM_SYSTEM_PROMPT}]
        if context:
            api_messages.append({"role": "system", "content": f"参考以下中医知识库内容：\n\n{context}"})
        api_messages.extend(self._build_messages_from_db(conv, db))
        user_msg = self._build_user_message(message, images)
        api_messages.append(user_msg)

        # 流式调用
        has_images = bool(images)
        full_reply = ""
        async for chunk in self._call_deepseek_stream(api_messages, use_vision=has_images):
            full_reply += chunk
            yield f"data: {json.dumps({'type': 'content', 'content': chunk}, ensure_ascii=False)}\n\n"

        # 安全性校验
        safety_warnings = self._check_safety_in_reply(full_reply, db)

        # 持久化消息
        next_seq = (conv.message_count or 0) + 1
        img_data = [{"url": u} for u in images] if images else None
        self._save_message(conv, next_seq, "user", message, db, images=img_data)
        self._save_message(conv, next_seq + 1, "assistant", full_reply, db, warnings=safety_warnings)

        # 发送安全警告 + 结束标记
        yield f"data: {json.dumps({'type': 'warnings', 'warnings': safety_warnings}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    def _strip_images(self, messages: list[dict]) -> list[dict]:
        """将多模态消息中的图片剥离，保留文字描述（降级到纯文字模型时使用）"""
        result = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                # 多模态消息：提取文字部分，图片标记为 [已上传图片]
                text_parts = []
                has_image = False
                for part in content:
                    if part.get("type") == "text":
                        text_parts.append(part["text"])
                    elif part.get("type") == "image_url":
                        has_image = True
                text = "\n".join(text_parts)
                if has_image:
                    text += "\n\n[用户已上传图片，但当前模型不支持图片识别，请仅根据文字描述进行分析。]"
                result.append({"role": msg["role"], "content": text})
            else:
                result.append(msg)
        return result

    def _check_safety_in_reply(self, reply: str, db: Session | None) -> list[str]:
        """对AI回复进行安全性硬约束校验"""
        warnings = []

        if not db:
            return warnings

        # 检查回复中是否包含配伍禁忌组合
        # 从回复中提取可能出现的药名
        all_herbs = db.query(Herb).filter(Herb.is_active == True).all()
        mentioned_herbs = []
        for herb in all_herbs:
            if herb.name in reply:
                mentioned_herbs.append(herb)
            # 检查异名
            if herb.aliases:
                for alias in herb.aliases:
                    if alias in reply:
                        mentioned_herbs.append(herb)
                        break

        # 配伍禁忌检查
        if len(mentioned_herbs) >= 2:
            herb_ids = [h.id for h in mentioned_herbs]
            conflicts = check_prescription_herbs(herb_ids, db)
            for w in conflicts:
                warnings.append(f"⚠️ 配伍禁忌: {w['herb_a']} + {w['herb_b']} ({w['rule_type']})")

        # 孕妇禁忌检查
        for herb in mentioned_herbs:
            if herb.pregnancy_contraindicated:
                warnings.append(f"⚠️ 孕妇禁忌: {herb.name}")

        # 毒性药提醒
        for herb in mentioned_herbs:
            if herb.toxicity in ("有毒", "有大毒"):
                warnings.append(f"⚠️ 毒性药: {herb.name}({herb.toxicity})，注意剂量控制")

        return warnings


# 全局服务实例
diagnosis_service = DiagnosisService()


# 主证→治法 推导辅助（本地规则辨证用）
_MERIDIAN_METHODS = {
    "太阳": "发汗解表、调和营卫",
    "阳明": "清泻阳明、通下府实",
    "少阳": "和解枢机、疏利少阳气机",
    "太阴": "温中健脾、祛湿化饮",
    "少阴": "温补心肾、回阳扶正",
    "厥阴": "燮理寒热、调其枢机",
}


def _infer_method_from_meridian(primary_meridians: list[str]) -> str | None:
    """由六经主证推导治法（多个经拼接），缺省返回 None"""
    if not primary_meridians:
        return None
    methods = [_MERIDIAN_METHODS[m] for m in primary_meridians if m in _MERIDIAN_METHODS]
    return "；".join(methods) if methods else None


def _infer_disease_from_complaint(chief_complaint: str | None) -> str | None:
    """由主诉关键词粗判中医病名（仅作本地规则辨证的回填，宁缺毋滥）"""
    if not chief_complaint:
        return None
    text = chief_complaint
    for kw, disease in [
        ("不寐", "不寐"),
        ("失眠", "不寐"),
        ("睡", "不寐"),
        ("头痛", "头痛"),
        ("咳", "咳嗽"),
        ("喘", "喘证"),
        ("腹痛", "腹痛"),
        ("胃痛", "胃脘痛"),
        ("腰痛", "腰痛"),
        ("月", "月经不调"),
        ("遗精", "遗精"),
        ("乏力", "虚劳"),
        ("盗汗", "自汗/盗汗"),
        ("畏寒", "虚劳"),
    ]:
        if kw in text:
            return disease
    return None