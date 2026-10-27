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
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const props = defineProps<{ patientId: number; visitId?: number | null }>()
const router = useRouter()

interface QOption { key: string; label: string }
interface Question { key: string; title: string; topic: string; options: QOption[] }

const questions: Question[] = [
  {
    key: 'sleep', title: '1. 问睡眠',
    topic: '睡眠如何？是否一觉到天亮？是否每天定时醒？如果会醒是几点？是否多梦？',
    options: [
      { key: 'normal', label: '一觉到天亮，睡眠安稳' },
      { key: 'wake_incomplete', label: '断续睡眠、睡不安稳' },
      { key: 'wake_1_3', label: '持续在1-3点醒来' },
      { key: 'wake_3_5', label: '持续在3-5点醒来' },
      { key: 'dreamy', label: '多梦纷纭' },
    ],
  },
  {
    key: 'appetite', title: '2. 问胃口',
    topic: '感觉饿吗？有欲望想吃什么特别的食物或味道吗？还是不饿、完全没胃口？',
    options: [
      { key: 'normal', label: '有食欲，食之有味' },
      { key: 'huge', label: '胃口过大、食不知饱' },
      { key: 'no', label: '没胃口、完全不饿' },
      { key: 'tasteless', label: '食之无味' },
    ],
  },
  {
    key: 'stool', title: '3. 问大便',
    topic: '便秘吗？每天有大便吗？大便颜色？是下利吗？很臭还是无味？',
    options: [
      { key: 'normal', label: '每日一次，成形，软硬适中' },
      { key: 'loose', label: '大便稀溏' },
      { key: 'hard', label: '大便干硬、便秘' },
      { key: 'undigested', label: '下利清谷(有未消化食物)' },
    ],
  },
  {
    key: 'urine', title: '4. 问小便',
    topic: '小便什么颜色？频尿吗？还是尿不出来？没有尿意？平均一天几次？',
    options: [
      { key: 'normal', label: '小便淡黄，通畅' },
      { key: 'yellow', label: '小便黄或深黄' },
      { key: 'clear', label: '小便清白、量多' },
    ],
  },
  {
    key: 'thirst', title: '5. 问口渴',
    topic: '很渴吗？渴想喝什么温度的水？不渴会忘记喝水？再怎么喝也不能止渴？',
    options: [
      { key: 'normal', label: '时而有口渴，正常饮水' },
      { key: 'no_thirst', label: '不渴，经常忘记喝水' },
      { key: 'unquenchable', label: '口渴，怎么喝都不解渴' },
      { key: 'cold_water', label: '口渴，想喝冰水' },
      { key: 'warm_water', label: '口渴，想喝温水' },
    ],
  },
  {
    key: 'hot_cold', title: '6. 问寒热',
    topic: '平时觉得身体很热还是很冷？手脚冰冷？睡时身体寒热如何？',
    options: [
      { key: 'normal', label: '脚温，睡时无特别感觉' },
      { key: 'cold_feet', label: '手脚冰冷' },
      { key: 'cold_all', label: '睡时全身冰冷' },
      { key: 'hot_upper_cold_lower', label: '上热下寒' },
      { key: 'mingled', label: '寒热并结' },
      { key: 'hot_all', label: '全身燥热(长期低烧)' },
    ],
  },
  {
    key: 'sweat', title: '7. 问汗',
    topic: '容易出汗吗？会半夜盗汗？会时常流汗不止？还是不出汗的身体？',
    options: [
      { key: 'normal', label: '天热或运动易出汗' },
      { key: 'constant', label: '汗流不止、动不动就出汗' },
      { key: 'night', label: '半夜盗汗' },
      { key: 'none', label: '不怎么出汗、无汗' },
    ],
  },
  {
    key: 'energy', title: '8. 问体力精神',
    topic: '精神好吗？还是一直疲惫？早上起床精神奕奕还是无法起床？精神能集中吗？',
    options: [
      { key: 'normal', label: '精神好，精力充沛' },
      { key: 'tired', label: '精力不足、容易疲惫' },
      { key: 'aortic_listless', label: '全身疲乏、难以起床' },
    ],
  },
  {
    key: 'sexual', title: '9. 问性功能',
    topic: '性功能好吗？男性晨起是否有阳反应？女性乳房是否敏感？',
    options: [
      { key: 'normal', label: '晨起有阳反应，性功能正常' },
      { key: 'low', label: '性功能减退、晨起无阳反应' },
    ],
  },
  {
    key: 'menses', title: '10. 问女子月经',
    topic: '无论有无月经，详细说明月经情形：延后还是提前？痛不痛？生过小孩吗？',
    options: [
      { key: 'na', label: '不适用 / 无月经(男性或已绝经)' },
      { key: 'regular', label: '月经规律，无不适' },
      { key: 'early', label: '月经提前' },
      { key: 'late', label: '月经延后' },
      { key: 'pain', label: '痛经或有瘀血块' },
    ],
  },
]

const answers = ref<Record<string, string>>({})
const notes = ref<Record<string, string>>({})
const result = ref<any>(null)
const submitting = ref(false)
const recommend = ref<any>(null)
const recLoading = ref(false)

const answeredCount = computed(() => questions.filter(q => answers.value[q.key] || (notes.value[q.key] || '').trim()).length)

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
    }) as any
    ElMessage.success('十问辨证完成，已归档到病历')
    await loadRecommend(result.value)
  } catch (e: any) {
    ElMessage.error('辨证失败：' + (e?.response?.data?.detail || e?.message || ''))
  }
  submitting.value = false
}

function topMeridian(r: any): string {
  const s = r?.scores || {}
  let best = ''
  let bestScore = 0
  for (const [k, v] of Object.entries(s)) {
    if (Number(v) > bestScore) { bestScore = Number(v); best = k }
  }
  return best
}

async function loadRecommend(r: any) {
  const m = topMeridian(r)
  if (!m) return
  recLoading.value = true
  try {
    recommend.value = await api.get('/prescriptions/classic-formulas/recommend', { params: { meridian: m } }) as any
  } catch {}
  recLoading.value = false
}

function useFormula(fid: number) {
  const visitPart = props.visitId ? `&visit_id=${props.visitId}` : ''
  router.push(`/prescriptions/new?patient_id=${props.patientId}&formula_id=${fid}${visitPart}`)
}
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