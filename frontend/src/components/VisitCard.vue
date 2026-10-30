<template>
  <el-card shadow="never" class="visit-card" :class="{ 'visit-card--child': isChild }">
    <div class="visit-header">
      <el-tag size="small" :type="visit.visit_type === '复诊' ? 'success' : 'info'" effect="plain" style="margin-right:6px;">{{ visit.visit_type || '初诊' }}</el-tag>
      <strong>主诉：</strong>{{ visit.chief_complaint }}
    </div>
    <div v-if="visit.tcm_disease || visit.tcm_syndrome" class="visit-diagnosis">
      <el-tag type="primary" size="small">{{ visit.tcm_disease }}</el-tag>
      <el-tag type="warning" size="small">{{ visit.tcm_syndrome }}</el-tag>
      <el-tag type="info" size="small">{{ visit.treatment_method }}</el-tag>
    </div>
    <div v-if="visit.tongue_body || visit.tongue_coat || visit.pulse" class="visit-sizhen">
      <span v-if="visit.tongue_body">舌质: {{ visit.tongue_body }}</span>
      <span v-if="visit.tongue_coat">舌苔: {{ visit.tongue_coat }}</span>
      <span v-if="visit.pulse">脉象: {{ visit.pulse }}</span>
    </div>

    <!-- 影像资料（舌苔/面色/化验单，点击可放大） -->
    <div v-if="visit.tongue_image || visit.face_image || (visit.lab_report_images && visit.lab_report_images.length)" class="sub-block">
      <div class="sub-title">📷 影像资料</div>
      <div class="visit-imgs">
        <div v-if="visit.tongue_image" class="visit-img-item">
          <span class="img-label">舌苔</span>
          <PinchImage :src="visit.tongue_image" thumb-class="visit-thumb" />
        </div>
        <div v-if="visit.face_image" class="visit-img-item">
          <span class="img-label">面色</span>
          <PinchImage :src="visit.face_image" thumb-class="visit-thumb" />
        </div>
        <div v-for="(img, i) in (visit.lab_report_images || [])" :key="i" class="visit-img-item">
          <span class="img-label">化验单{{ (visit.lab_report_images || []).length > 1 ? i + 1 : '' }}</span>
          <PinchImage :src="img" :list="visit.lab_report_images || []" :index="i" thumb-class="visit-thumb" />
        </div>
      </div>
    </div>

    <!-- 本次问诊十问（按就诊日期关联，半折叠） -->
    <div v-if="inquiries.length" class="sub-block">
      <div class="sub-title">
        <span>🩺 本次问诊十问</span>
        <el-button link type="warning" size="small" style="margin-left:auto;padding:0;height:auto;" @click="iqExpanded = !iqExpanded">
          {{ iqExpanded ? '收起' : '查看全部' }}
        </el-button>
      </div>
      <div class="collapse-box" :class="{ collapsed: !iqExpanded }">
        <div v-for="iq in inquiries" :key="iq.id" class="sub-item">
          <el-tag type="warning" size="small">{{ iq.primary_type || '未定型' }}</el-tag>
          <span class="sub-note">偏性画像</span>
          <div v-if="hasAnswers(iq)" class="iq-answers">
            <div v-for="q in TEN_QUESTIONS" :key="q.key" v-show="iqAnswer(iq, q.key)" class="iq-answer-row" :class="{ 'iq-abn': iqAbnormal(iq, q) }">
              <span class="iq-answer-label">{{ q.title }}</span>
              <span class="iq-opt">{{ iqAnswer(iq, q.key) }}</span>
              <span v-if="iqNote(iq, q.key)" class="iq-custom-note">（自填：{{ iqNote(iq, q.key) }}）</span>
              <span v-if="iqAbnormal(iq, q)" class="iq-abn-tag">⚠ {{ iqFindingText(iq, q) }}</span>
            </div>
          </div>
          <ul v-if="iqGeneralFindings(iq).length" class="iq-findings">
            <li v-for="(f, fi) in iqGeneralFindings(iq)" :key="fi">{{ f }}</li>
          </ul>
          <div v-if="iqSuggestionParts(iq).length" class="iq-suggestion">
            <div class="iq-suggestion-title">辨证结论（按主经）</div>
            <div v-for="(p, pi) in iqSuggestionParts(iq)" :key="pi" class="iq-suggestion-row">
              <span v-if="p.name" class="iq-meridian-tag">{{ p.name }}</span>
              <span class="iq-meridian-text">{{ p.text }}</span>
            </div>
          </div>
          <div v-else-if="iq.result && iq.result.suggestion" class="iq-suggestion">{{ iq.result.suggestion }}</div>
          <div class="visit-actions">
            <el-button link type="warning" size="small" @click="$emit('view-iq', iq)">查看完整评估</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 本次处方 -->
    <div v-if="prescriptions.length" class="sub-block">
      <div v-for="rx in prescriptions" :key="rx.id" class="sub-item">
        <div class="sub-title">💊 本次处方
          <el-tag :type="statusTag(rx.status)" size="small" effect="plain">{{ rx.status }}</el-tag>
        </div>
        <template v-if="rx.items && rx.items.length">
          <div class="rx-sub-title">🌿 中药方{{ rx.formula_name ? ' · ' + rx.formula_name : '' }}</div>
          <div class="rx-herbs">
            <span v-for="(it, ix) in rx.items" :key="'h'+ix" class="rx-herb">
              {{ it.herb_name }}<em v-if="it.is_king_herb" class="king">君</em>
              <b>{{ it.dose }}g</b>
            </span>
          </div>
          <div class="rx-doses">{{ rx.doses }} 剂 · {{ rx.preparation_method }}</div>
        </template>
        <template v-if="rx.acupoints && rx.acupoints.length">
          <div class="rx-sub-title">🪡 针灸方{{ rx.acupoint_formula_name ? ' · ' + rx.acupoint_formula_name : '' }}</div>
          <div class="rx-herbs">
            <span v-for="(a, ix) in rx.acupoints" :key="'a'+ix" class="rx-herb">
              {{ a.acupoint_name }}<b v-if="a.technique">·{{ a.technique }}</b>
            </span>
          </div>
          <div v-if="rx.acupoint_technique || rx.treatment_frequency || rx.treatment_days" class="rx-acu-meta">
            <span v-if="rx.acupoint_technique">{{ rx.acupoint_technique }}</span>
            <span v-if="rx.treatment_frequency">{{ rx.treatment_frequency }}</span>
            <span v-if="rx.treatment_days">{{ rx.treatment_days }} 天</span>
          </div>
        </template>
        <div class="visit-actions">
          <el-button link type="danger" size="small" @click="$emit('view-rx', rx)">查看处方</el-button>
        </div>
      </div>
    </div>

    <div v-if="visit.ai_analysis" class="sub-block">
      <div class="sub-title">
        <span>🤖 AI 诊断库（辨证论治）</span>
        <el-button link type="warning" size="small" style="margin-left:auto;padding:0;height:auto;" @click="aiExpanded = !aiExpanded">
          {{ aiExpanded ? '收起' : '查看全部' }}
        </el-button>
      </div>
      <div class="view-ai-analysis" :class="{ collapsed: !aiExpanded }" v-html="renderMarkdown(visit.ai_analysis)"></div>
      <div v-if="parseAiFormulas(visit).length" class="ai-formulas">
        <div class="ai-formulas-title">💊 将 AI 推荐方带入开方</div>
        <div v-for="(f, fi) in parseAiFormulas(visit)" :key="fi" class="ai-formula-row">
          <span class="ai-formula-name">{{ f.name }}</span>
          <span class="ai-formula-comp">{{ f.composition }}</span>
          <el-button link type="success" size="small" style="flex:none;" @click="goPrescribeWithFormula(f)">去开药（带入该方）</el-button>
        </div>
      </div>
    </div>

    <!-- 随访/回访记录（并入本次就诊） -->
    <div v-if="followups.length" class="sub-block">
      <div class="sub-title">📈 随访/回访记录</div>
      <div v-for="fu in followups" :key="fu.id" class="fu-item">
        <span class="fu-date">{{ fu.followup_date }}</span>
        <el-tag size="small" :type="improvementTag(fu.improvement)">{{ fu.improvement || '未评估' }}</el-tag>
        <span v-if="fu.feedback" class="fu-feedback">{{ fu.feedback }}</span>
        <span v-if="editable" class="visit-actions">
          <el-button link type="primary" size="small" @click="$emit('view-followup', fu)">编辑</el-button>
          <el-button link type="danger" size="small" @click="$emit('delete-followup', fu)">删除</el-button>
        </span>
      </div>
    </div>

    <div class="visit-actions">
      <el-button v-if="editable" link type="success" size="small" @click="$emit('add-followup', visit)">+ 随访</el-button>
      <el-button link type="primary" size="small" @click="$emit('view', visit)">查看就诊详情</el-button>
      <el-button link type="warning" size="small" @click="$emit('edit', visit.id)">完善/编辑</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { renderMarkdown } from '@/utils/markdown'
import PinchImage from '@/components/PinchImage.vue'
import { TEN_QUESTIONS } from '@/utils/tenAspectsQuestions'

const router = useRouter()

const props = withDefaults(
  defineProps<{
    visit: any
    inquiries?: any[]
    prescriptions?: any[]
    followups?: any[]
    editable?: boolean
    isChild?: boolean
    patientId?: number
  }>(),
  { inquiries: () => [], prescriptions: () => [], followups: () => [], editable: false, isChild: false, patientId: undefined },
)

defineEmits<{
  view: [any]
  edit: [number]
  'add-followup': [any]
  'view-followup': [any]
  'delete-followup': [any]
  'view-rx': [any]
  'view-iq': [any]
}>()

// 卡片内 问诊十问 / AI 诊断库 默认折叠
const iqExpanded = ref(false)
const aiExpanded = ref(false)

function statusTag(s?: string) {
  if (!s) return 'info'
  if (s.includes('审核')) return 'warning'
  if (s.includes('发药')) return 'success'
  return 'info'
}
function improvementTag(s?: string) {
  if (s === '明显好转' || s === '好转') return 'success'
  if (s === '稳定') return 'info'
  if (s === '反复' || s === '加重') return 'danger'
  return 'info'
}
function hasAnswers(iq: any): boolean {
  return !!iq?.answers && Object.keys(iq.answers).length > 0
}
function iqAnswer(iq: any, qKey: string): string {
  const a = iq?.answers?.[qKey]
  if (!a) return ''
  if (a === 'custom') return '（自填）'
  const q = TEN_QUESTIONS.find(x => x.key === qKey)
  const o = q?.options.find(o => o.key === a)
  return o ? o.label : a
}
function iqNote(iq: any, qKey: string): string {
  const n = iq?.notes?.[qKey]
  return n && String(n).trim() ? String(n) : ''
}

// 六经中文名（用于优化"方域结论"展示）
const IQ_MERIDIAN_NAMES: Record<string, string> = {
  太阳: '太阳（表证）',
  阳明: '阳明（里热）',
  少阳: '少阳（半表半里）',
  太阴: '太阴（里寒湿）',
  少阴: '少阴（心肾）',
  厥阴: '厥阴（寒热错杂）',
}

// 该题在 findings 中是否有判据异常（如《5. 问口渴》）
function iqFindingText(iq: any, q: any): string {
  const fs: string[] = iq?.result?.findings || []
  const m = fs.find(f => f.includes(`《${q.title}》`))
  return m ? m.replace(`《${q.title}》`, '').trim() : ''
}
// 该题是否被判定为异常/有问题
function iqAbnormal(iq: any, q: any): boolean {
  const t = iqFindingText(iq, q)
  return !!t && !t.startsWith('补充')
}

// 仅展示"综合类"判据（不落到 1-10 具体某一题的，如寒热错杂提示）；单题判据已冗余到行尾角标
function iqGeneralFindings(iq: any): string[] {
  const fs: string[] = iq?.result?.findings || []
  return fs.filter(f => !TEN_QUESTIONS.some(q => f.includes(`《${q.title}》`)))
}

// 把 suggestion 拆成 [{经名, 建议}]，看不清来源时给每条标上所属主经
function iqSuggestionParts(iq: any): { name: string; text: string }[] {
  const sug = (iq?.result?.suggestion || '').trim()
  if (!sug) return []
  const primary: string[] = iq?.result?.detail?.primary_meridians || []
  const parts = sug.split(' · ').filter(Boolean)
  return parts.map((text, i) => {
    // 优先用 detail 里命中的主经名；多段不足时按顺序对应 primary
    const m = primary[i] || primary[primary.length - 1] || ''
    return { name: IQ_MERIDIAN_NAMES[m] || m || '', text }
  })
}
// 清洗方剂组成/加减文本：去掉 JSON 键名/引号/括号与英文，仅保留含中文的「药名+剂量」片段，
// 避免 composition/modification 等英文键名被当成一味药带入开方。
function cleanComposition(s: string): string {
  if (!s) return ''
  let v = String(s || '')
  v = v.replace(/```/g, ' ').replace(/[*{}\[\]`]/g, ' ')
  v = v.replace(/"\s*[:：]\s*"/g, ' ')
  v = v.replace(/"[A-Za-z_]+"\s*[:：]?/g, ' ')
  v = v.replace(/"/g, ' ')
  v = v.replace(/\b(composition|modification|name|indication|组成|药物|加减|方解|适应症)\b\s*[:：]?/gi, ' ')
  const toks = v.split(/\s+/).filter(Boolean).filter(t => /[一-龥]/.test(t))
  return toks.join(' ').trim()
}
// 清洗表单字段中的 JSON/Markdown 残留（AI 有时把 composition 输出成嵌套 JSON 字符串）
function cleanAiField(s: string, key = 'composition'): string {
  let v = String(s || '').trim()
  if (!v) return ''
  v = v.replace(/\*\*/g, '').replace(/[{}\[\]`]/g, ' ')
  const inner = v.match(new RegExp(`"${key}"\\s*:\\s*("(?:[^"\\\\]|\\\\.)*"|\\[[\\s\\S]*?\\])`))
  if (inner) {
    let t = inner[1].replace(/^"|"$/g, '').replace(/\\"/g, '"').trim()
    if (t.startsWith('[')) {
      const arr = t.match(/"[^"]*"/g)
      if (arr) t = arr.map((x: string) => x.replace(/"/g, '')).join(' ')
    }
    return cleanComposition(t)
  }
  return cleanComposition(v)
}
// 从已保存的 ai_analysis 文本中解析出推荐方剂（兼容新版JSON/【推荐方剂】段/旧版「推荐方剂及加减」）
function parseAiFormulas(visit: any): { name: string; composition: string; modification: string }[] {
  const text = visit?.ai_analysis || ''
  const out: { name: string; composition: string; modification: string }[] = []
  const fm = text.match(/```(?:json)?\s*\{[^`]*?recommended_formulas\s*:\s*(\[[\s\S]*?\])\s*\}?\s*```/)
  if (fm) {
    try {
      const data = JSON.parse(fm[1])
      if (Array.isArray(data)) {
        const jout: { name: string; composition: string; modification: string }[] = []
        for (const it of data) {
          if (!it?.name) continue
          let c = it.composition || it.组成 || ''
          if (Array.isArray(c)) c = c.join(' ')
          jout.push({ name: cleanAiField(String(it.name).trim(), 'name'), composition: cleanAiField(String(c || ''), 'composition'), modification: cleanAiField(String(it.modification || ''), 'modification') })
        }
        if (jout.length) return jout
      }
    } catch {}
  }
  // 旧版「推荐方剂及加减」Markdown 结构兜底：主方：X + 缩进药行
  const mi = text.search(/推荐方剂及加减|主方[：:]/)
  if (mi >= 0) {
    const seg2 = text.slice(mi).split('\n')
    let pname = ''
    const herbs: string[] = []
    for (let li = 0; li < seg2.length; li++) {
      const l2 = seg2[li]
      const nm = l2.match(/主方[：:]\s*(.+)/)
      if (nm) { pname = nm[1].trim().split(/[（(]/)[0].trim(); continue }
      if (/^\s{2,}/.test(l2) && /\d[\d.。]*\s*(g|克|钱|两|枚|片|条|只)/.test(l2)) {
        herbs.push(l2.trim().replace(/\s*[（(].*?[）)]\s*$/, ''))
        if (li < seg2.length - 1) continue
      }
      if (pname && herbs.length && /^\S/.test(l2) && (l2.includes('加减') || l2.startsWith('加减'))) break
    }
    if (pname && herbs.length) {
      out.push({ name: cleanAiField(pname, 'name'), composition: cleanComposition(herbs.join(' ')), modification: '' })
      return out
    }
  }
  const idx = text.lastIndexOf('【推荐方剂】')
  if (idx < 0) return []
  const seg = text.slice(idx).split('\n')
  for (const line of seg) {
    const m = line.match(/^[-•]\s*(.+?)[：:]\s*(.*)$/)
    if (!m) continue
    const name = m[1].trim()
    let composition = m[2].trim()
    let modification = ''
    // 兼容 AI 把 composition 输出为嵌套 JSON 对象（含 composition + modification 键）
    if (composition.includes('"composition"')) {
      const cmp = composition.match(/"composition"\s*:\s*"((?:[^"\\]|\\.)*)"/)
      const modj = composition.match(/"modification"\s*:\s*"((?:[^"\\]|\\.)*)"/)
      if (cmp) composition = cmp[1].replace(/\\"/g, '"').trim()
      if (modj) modification = modj[1].replace(/\\"/g, '"').trim()
    } else {
      const mod = composition.match(/（加减：([^）]+)）/)
      if (mod) {
        modification = mod[1].trim()
        composition = composition.replace(/（加减：[^）]+）/, '').trim()
      }
    }
    if (!name) continue
    out.push({ name: cleanAiField(name, 'name'), composition: cleanAiField(composition), modification: cleanAiField(modification, 'modification') })
  }
  return out
}

// 将推荐方剂带入开方页（预填方名与药味）
function goPrescribeWithFormula(f: { name: string; composition: string }) {
  if (!props.patientId) {
    router.push({ path: '/prescriptions/new' })
    return
  }
  const q: any = { patient_id: props.patientId }
  if (props.visit?.id) q.visit_id = props.visit.id
  q.ai_formula = JSON.stringify({ name: f.name || '', composition: f.composition || '' })
  router.push({ path: '/prescriptions/new', query: q })
}
</script>

<style scoped>
.visit-card { margin-bottom: 4px; }
.visit-card--child { margin-left: 28px; border-left: 3px solid #d9c9a3; }
.visit-header { font-size: 14px; }
.visit-diagnosis { margin-top: 8px; display: flex; gap: 6px; }
.visit-sizhen { margin-top: 8px; font-size: 13px; color: #666; display: flex; gap: 12px; }
.visit-imgs { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 6px; }
.visit-img-item { text-align: center; }
.visit-img-item .img-label { display: block; font-size: 12px; color: #999; margin-bottom: 4px; }
.visit-thumb { width: 96px; height: 96px; border-radius: 6px; border: 1px solid #eee; cursor: zoom-in; overflow: hidden; }
.iq-findings { margin: 4px 0; padding-left: 16px; font-size: 12.5px; color: #666; line-height: 1.8; }
.iq-answers { margin: 6px 0 2px; border: 1px solid #f0e6d8; border-radius: 8px; padding: 6px 10px; background: #fffdf9; }
.iq-answer-row { font-size: 12px; line-height: 1.9; }
.iq-answer-label { color: #6b4423; font-weight: 600; }
.iq-opt { color: #333; }
.iq-custom-note { color: #B8860B; font-size: 11.5px; }
.iq-answer-row.iq-abn { background: #fff5f5; border-radius: 6px; padding: 1px 6px; margin: 2px 0; }
.iq-abn-tag { display: inline-block; margin-left: 6px; padding: 0 6px; font-size: 11px; line-height: 1.6; color: #d64541; background: #fee9e7; border-radius: 10px; }
.iq-suggestion { margin-top: 6px; font-size: 12.5px; color: #8B4513; border-top: 1px dashed #e8d8c0; padding-top: 6px; }
.iq-suggestion-title { font-size: 12px; font-weight: 600; color: #8B4513; margin-bottom: 4px; }
.iq-suggestion-row { display: flex; gap: 6px; align-items: flex-start; margin: 3px 0; line-height: 1.6; }
.iq-meridian-tag { flex: none; display: inline-block; padding: 1px 8px; font-size: 11px; color: #fff; background: #c2946a; border-radius: 10px; white-space: nowrap; margin-top: 1px; }
.iq-meridian-text { color: #6b4423; }
.ai-formulas { margin-top: 6px; border-top: 1px dashed #e0d0b8; padding-top: 6px; }
.ai-formulas-title { font-size: 12px; font-weight: 600; color: #8B4513; margin-bottom: 4px; }
.ai-formula-row { display: flex; align-items: center; gap: 8px; margin: 3px 0; line-height: 1.5; }
.ai-formula-name { flex: none; font-size: 12.5px; font-weight: 600; color: #6b4423; }
.ai-formula-comp { flex: 1; font-size: 12px; color: #666; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.view-ai-analysis {
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  font-size: 12.5px;
  line-height: 1.8;
  color: #333;
  background: #fffbf0;
  border: 1px dashed #d9c9a3;
  border-radius: 6px;
  padding: 8px 10px;
  &.collapsed { max-height: 132px; overflow: hidden; position: relative; }
  &.collapsed::after {
    content: '';
    position: absolute;
    left: 0; right: 0; bottom: 0;
    height: 44px;
    background: linear-gradient(to bottom, rgba(255, 251, 240, 0), #fffbf0);
    pointer-events: none;
  }
  :deep(h1), :deep(h2), :deep(h3), :deep(h4) { margin: 8px 0 4px; color: #8B4513; line-height: 1.4; }
  :deep(h1) { font-size: 14px; }
  :deep(h2) { font-size: 13.5px; }
  :deep(h3) { font-size: 13px; }
  :deep(h4) { font-size: 12.5px; }
  :deep(p) { margin: 5px 0; overflow-wrap: anywhere; }
  :deep(ul), :deep(ol) { margin: 5px 0; padding-left: 20px; }
  :deep(li) { margin: 2px 0; overflow-wrap: anywhere; }
  :deep(table) { table-layout: fixed; width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 12px; }
  :deep(th), :deep(td) { border: 1px solid #e8e0d8; padding: 3px 6px; text-align: left; word-break: break-word; overflow-wrap: anywhere; vertical-align: top; }
  :deep(th) { background: #faf7f4; }
  :deep(strong) { color: #8B4513; }
  :deep(code) { background: #f5f0eb; padding: 0 3px; border-radius: 3px; }
  :deep(pre) { background: #f5f0eb; padding: 8px; border-radius: 5px; overflow-x: auto; }
  :deep(pre code) { background: transparent; padding: 0; }
  :deep(blockquote) { border-left: 3px solid #d9c9a3; margin: 5px 0; padding-left: 8px; color: #999; }
}
.collapse-box { position: relative; }
.collapse-box.collapsed { max-height: 110px; overflow: hidden; }
.collapse-box.collapsed::after {
  content: '';
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 38px;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0), #fff);
  pointer-events: none;
}
.visit-actions { margin-top: 8px; text-align: right; }
.fu-date { font-size:12px; color:#888; min-width:96px; }
.fu-item { display:flex; align-items:center; gap:8px; flex-wrap:wrap; padding:4px 0; border-bottom:1px dashed #f0f0f0; }
.fu-feedback { margin-top: 6px; font-size: 13px; color: #444; line-height: 1.7; white-space: pre-wrap; }
.rx-doses { font-size: 12px; color: #999; margin-top: 4px; }
.rx-herbs { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
.rx-sub-title { margin-top: 8px; font-size: 12.5px; font-weight: 600; color: #6b4f2a; }
.rx-acu-meta { margin-top: 4px; font-size: 12px; color: #999; display: flex; flex-wrap: wrap; gap: 8px; }
.rx-herb { font-size: 12px; background: #f5f7fa; border-radius: 4px; padding: 2px 8px; color: #333; }
.rx-herb b { color: #606266; margin-left: 2px; font-weight: normal; }
.rx-herb .king { color: #F56C6C; font-style: normal; margin-left: 2px; }
.sub-block { margin-top: 10px; border-top: 1px dashed #eee; padding-top: 8px; }
.sub-block + .sub-block { margin-top: 10px; }
.sub-title { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.sub-item { margin-bottom: 8px; }
.sub-note { margin-left: 6px; font-size: 12px; color: #999; }
</style>