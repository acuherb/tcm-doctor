<template>
  <div class="ten-aspects">
    <el-alert
      title="按经方家问诊方式逐项回答，可结合上面的四诊共同辨证；评估结果会自动归档到患者病历。"
      type="warning"
      :closable="false"
      style="margin-bottom: 16px;"
    />

    <div v-for="q in questions" :key="q.key" class="ta-group">
      <div class="ta-title">{{ q.title }}</div>
      <div class="ta-topic">{{ q.topic }}</div>
      <div class="ta-options">
        <el-radio
          v-for="opt in q.options"
          :key="opt.key"
          :value="opt.key"
          :model-value="answers[q.key]"
          :name="`ta-${q.key}`"
          size="small"
          @click="onPick(q.key, opt.key)"
        >
          {{ opt.label }}
        </el-radio>
      </div>
      <el-input v-model="notes[q.key]" type="textarea" :rows="1" resize="none"
        placeholder="或自填描述（此项可同时补充说明）…" class="ta-note" />
    </div>

    <div class="ta-submit">
      <el-button type="warning" @click="evaluate" :loading="submitting"
        :disabled="answeredCount < questions.length">
        🩺 根据十问辨证 (已答 {{ answeredCount }}/{{ questions.length }})
      </el-button>
    </div>

    <div v-if="result" class="ta-result">
      <el-divider content-position="left">十问辨证结果</el-divider>
      <div class="ta-primary">
        主归偏性：
        <el-tag type="warning" size="large">{{ result.primary_type }}</el-tag>
        <el-tag v-for="st in result.secondary_types || []" :key="st" size="medium" style="margin-left:6px;">
          倾向·{{ st }}
        </el-tag>
      </div>
      <ul v-if="result.findings && result.findings.length" class="ta-findings">
        <li v-for="(f, i) in result.findings" :key="i">{{ f }}</li>
      </ul>
      <div class="ta-suggestion"><b>方域提示：</b>{{ result.suggestion }}</div>

      <div v-if="recommend" class="ta-recommend">
        <el-divider content-position="left">🪷 可参考经方 <el-tag v-if="recommend.meridian" size="small" type="success" style="margin-left:6px;">{{ recommend.meridian }}类</el-tag></el-divider>

        <!-- 合病：分经展示，可同时清、温两条思路 -->
        <div v-if="recommend.groups && recommend.groups.length" v-for="g in recommend.groups" :key="g.label">
          <div class="ta-group-title" style="font-weight:600;color:#8B4513;margin:6px 0 4px;">〔{{ g.label }}〕</div>
          <el-empty v-if="!recLoading && g.matched && g.matched.length === 0" description="中药方库暂无录入该六经候选方（可在中药方库补充），下方为候选方名参考" :image-size="40">
            <template #description>
              <div class="ta-suggestion" v-if="g.missing && g.missing.length">
                候选：<el-tag v-for="n in g.missing" :key="n" size="small" style="margin-left:4px;">{{ n }}</el-tag>
              </div>
            </template>
          </el-empty>
          <div v-for="f in g.matched || []" :key="f.id" class="rec-item">
            <div class="rec-info">
              <span class="rec-name">{{ f.name }}</span>
              <el-tag size="small" type="info" v-if="f.source">{{ f.source }}</el-tag>
              <div class="rec-eff" v-if="f.efficacy">{{ f.efficacy }}</div>
            </div>
            <el-button size="small" type="danger" plain @click="useFormula(f.id)">选此方开方</el-button>
          </div>
        </div>

        <!-- 单经 -->
        <template v-else>
        <el-empty v-if="!recLoading && recommend.matched && recommend.matched.length === 0" description="中药方库暂无录入该六经候选方（可在中药方库补充），下方为候选方名参考">
          <template #description>
            <div class="ta-suggestion" v-if="recommend.missing && recommend.missing.length">
              候选：<el-tag v-for="n in recommend.missing" :key="n" size="small" style="margin-left:4px;">{{ n }}</el-tag>
            </div>
          </template>
        </el-empty>

        <div v-for="f in recommend.matched || []" :key="f.id" class="rec-item">
          <div class="rec-info">
            <span class="rec-name">{{ f.name }}</span>
            <el-tag size="small" type="info" v-if="f.source">{{ f.source }}</el-tag>
            <div class="rec-eff" v-if="f.efficacy">{{ f.efficacy }}</div>
          </div>
          <el-button size="small" type="danger" plain @click="useFormula(f.id)">选此方开方</el-button>
        </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { TEN_QUESTIONS } from '@/utils/tenAspectsQuestions'

const props = defineProps<{
  patientId: number
  visitId?: number | null
  // 二次编辑时回填：上一次该就诊的问诊十问（选项 / 自填 / 辨证结果）
  initial?: { answers?: Record<string, string>; notes?: Record<string, string>; result?: any } | null
}>()
const router = useRouter()

interface QOption { key: string; label: string }
interface Question { key: string; title: string; topic: string; options: QOption[] }

const questions: Question[] = TEN_QUESTIONS as Question[]

const answers = ref<Record<string, string>>({})
const notes = ref<Record<string, string>>({})
const result = ref<any>(null)
const submitting = ref(false)
const recommend = ref<any>(null)
const recLoading = ref(false)

const answeredCount = computed(() => questions.filter(q => answers.value[q.key] || (notes.value[q.key] || '').trim()).length)

// 二次编辑时回填上一次的问诊十问（选项 / 自填 / 辨证结果），避免从头重选
watch(
  () => props.initial,
  (init) => {
    const a: Record<string, string> = {}
    const n: Record<string, string> = {}
    if (init && init.answers) Object.assign(a, init.answers)
    if (init && init.notes) Object.assign(n, init.notes)
    answers.value = a
    notes.value = n
    result.value = init && init.result ? init.result : null
    recommend.value = null
    if (result.value) loadRecommend(result.value)
  },
)

function onPick(qKey: string, optKey: string) {
  answers.value[qKey] = answers.value[qKey] === optKey ? '' : optKey
}

async function evaluate() {
  if (answeredCount.value < questions.length) {
    ElMessage.warning('请回答全部十问')
    return
  }
  submitting.value = true
  recommend.value = null
  try {
    const payloadAnswers: Record<string, string> = {}
    for (const q of questions) {
      if (answers.value[q.key]) payloadAnswers[q.key] = answers.value[q.key]
      else if ((notes.value[q.key] || '').trim()) payloadAnswers[q.key] = 'custom'
    }
    result.value = await api.post(`/patients/${props.patientId}/constitution`, {
      answers: payloadAnswers,
      notes: notes.value,
      visit_id: props.visitId ?? null,
    }, { silent: true }) as any
    ElMessage.success('十问辨证完成，已归档到病历')
    await loadRecommend(result.value)
  } catch (e: any) {
    ElMessage.error('辨证失败：' + (e?.response?.data?.detail || e?.message || ''))
  }
  submitting.value = false
}

function topMeridian(r: any): string {
  // 优先采用后端主证顺序（含合病），与主标签一致；旧报告无该字段时回退到分数最高
  if (r?.primary_meridians && r.primary_meridians.length) return r.primary_meridians[0]
  const s = r?.scores || {}
  let best = ''
  let bestScore = 0
  for (const [k, v] of Object.entries(s)) {
    if (Number(v) > bestScore) { bestScore = Number(v); best = k }
  }
  return best
}

async function loadRecommend(r: any) {
  // 合病：按主经顺序取前两经分别拉推荐，避免只取 dict 顺序的第一个
  const meridians = (r?.primary_meridians && r.primary_meridians.length)
    ? r.primary_meridians.slice(0, 2)
    : (topMeridian(r) ? [topMeridian(r)] : [])
  if (meridians.length === 0) return
  recLoading.value = true
  try {
    const groups = []
    for (const m of meridians) {
      const g = await api.get('/prescriptions/classic-formulas/recommend', { params: { meridian: m } }) as any
      if (g) groups.push({ label: m, ...g })
    }
    recommend.value = groups.length === 1 ? groups[0]
      : { meridian: meridians.join('+'), groups }
  } catch {}
  recLoading.value = false
}

function useFormula(fid: number) {
  const visitPart = props.visitId ? `&visit_id=${props.visitId}` : ''
  router.push(`/prescriptions/new?patient_id=${props.patientId}&formula_id=${fid}${visitPart}`)
}

// 生成「问诊十问」可读摘要文本，供父组件带入 AI 四诊辨证
function getAspectSummary(): string {
  const lines: string[] = []
  for (const q of questions) {
    let text = ''
    const picked = answers.value[q.key]
    if (picked) {
      const opt = q.options.find(o => o.key === picked)
      text = opt ? opt.label : picked
    }
    const note = (notes.value[q.key] || '').trim()
    if (note) text = text ? text + '；' + note : note
    lines.push(`${q.title}：${text || '未回答'}`)
  }
  return lines.join('\n')
}

// 生成结构化的问诊十问答案，供后端在未配置 API Key 时执行本地规则辨证
function getAspectAnswers(): { answers: Record<string, string>; notes: Record<string, string> } {
  const payloadAnswers: Record<string, string> = {}
  for (const q of questions) {
    if (answers.value[q.key]) payloadAnswers[q.key] = answers.value[q.key]
    else if ((notes.value[q.key] || '').trim()) payloadAnswers[q.key] = 'custom'
  }
  return { answers: payloadAnswers, notes: notes.value }
}
defineExpose({ getAspectSummary, getAspectAnswers })
</script>

<style scoped>
.ta-group {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #faf8f6;
  border-left: 3px solid #8B4513;
}
.ta-title { font-size: 14px; font-weight: 600; color: #5a4632; }
.ta-opt-wrap { display: flex; flex-wrap: wrap; gap: 4px; }
.ta-note { margin-top: 8px; }
.ta-submit { text-align: center; margin-top: 8px; }
.ta-primary { font-size: 15px; }
.ta-findings { margin: 10px 0 0; padding-left: 18px; font-size: 13px; color: #666; line-height: 1.9; }
.ta-suggestion { margin-top: 8px; font-size: 13px; color: #8B4513; }
.ta-recommend { margin-top: 4px; }
.rec-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  background: #fff7e6;
  border: 1px solid #ffe7ba;
}
.rec-name { font-size: 14px; font-weight: 600; color: #8B4513; }
.rec-eff { font-size: 12px; color: #a0896f; margin-top: 2px; }
</style>