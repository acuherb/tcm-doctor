<template>
  <div class="constitution-scale">
    <el-page-header @back="$router.back()" content="经方家问诊十问" />

    <el-alert
      v-if="!hasPatient"
      title="此页面直接进入时未关联患者，问诊结果将无处归档。请选择一位患者后再开始，结果会自动存入其「问诊十问」病例链。"
      type="warning"
      :closable="false"
      style="margin-top: 16px;"
    />
    <el-card v-if="!hasPatient" shadow="hover" style="margin-top: 12px;">
      <template #header><span>👤 选择评估对象</span></template>
      <el-select
        v-model="patientId"
        placeholder="请选择患者"
        filterable
        style="width: 300px;"
        :disabled="submitting"
      >
        <el-option
          v-for="p in patients"
          :key="p.id"
          :value="p.id"
          :label="p.name + (p.gender ? ' · ' + p.gender : '')"
        />
      </el-select>
      <span v-if="patients.length === 0" class="text-muted" style="margin-left:12px;">暂无患者，请先到「患者管理」建档</span>
    </el-card>
    <el-card v-else-if="hasPatient" shadow="hover" style="margin-top: 12px;">
      <template #header><span>🩺 评估对象</span></template>
      <span style="font-size:14px;">为患者 <el-tag type="success" size="large">{{ currentPatientName }}</el-tag> 辨证，结果将自动归档到其病例</span>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <span>🩺 倪海厦·问诊十问</span>
        <el-tag type="warning" size="small" style="margin-left: 8px;">共10问</el-tag>
      </template>

      <el-alert
        title="请按经方家问诊方式，逐项说明你身体的感觉。经方家即可不看到你，仅依这些主要症状来辨证开方。"
        type="warning"
        :closable="false"
        style="margin-bottom: 20px;"
      />

      <div v-for="q in questions" :key="q.key" class="question-group">
        <h3 class="group-title">{{ q.title }}</h3>
        <p class="group-topic">{{ q.topic }}</p>
        <div class="question-options">
          <el-radio-group v-model="answers[q.key]" class="options-wrap">
            <el-radio v-for="opt in q.options" :key="opt.key" :value="opt.key" size="default" border>
              {{ opt.label }}
            </el-radio>
          </el-radio-group>
          <el-button v-if="answers[q.key]" link type="danger" size="small" class="clear-btn" @click="answers[q.key] = ''">清除选择</el-button>
        </div>
        <el-input v-model="notes[q.key]" type="textarea" :rows="2" resize="none" placeholder="若无合适选项，可在此自填你的具体情况，经方家将据此辨证…" class="custom-input" />
        <el-button v-if="(notes[q.key] || '').trim()" link type="danger" size="small" class="clear-note" @click="notes[q.key] = ''">清除自填</el-button>
      </div>

      <div class="submit-bar">
        <el-button type="primary" size="large" @click="submitScale" :loading="submitting" :disabled="answeredCount < questions.length">
          辨证评估 (已答 {{ answeredCount }}/{{ questions.length }})
        </el-button>
      </div>
    </el-card>

    <!-- 结果 -->
    <el-card v-if="result" shadow="hover" style="margin-top: 20px;" class="result-card">
      <template #header><span>📊 偏性画像</span></template>
      <div class="result-primary">
        <span class="result-label">主归偏性：</span>
        <el-tag type="warning" size="large">{{ result.primary_type }}</el-tag>
        <el-tag v-for="st in result.secondary_types" :key="st" size="medium" style="margin-left:6px;">倾向·{{ st }}</el-tag>
      </div>

      <template v-if="result.detail && result.detail.labels && result.detail.labels.length">
        <div class="result-labels">
          <el-tag v-for="lb in result.detail.labels" :key="lb" type="info" effect="plain" size="small" style="margin-right:6px;">{{ lb }}</el-tag>
        </div>
      </template>

      <template v-if="result.findings && result.findings.length">
        <el-divider>判据解析</el-divider>
        <ul class="findings">
          <li v-for="(f, i) in result.findings" :key="i">{{ f }}</li>
        </ul>
      </template>

      <el-divider>六经分布</el-divider>
      <div class="meridian-bars">
        <div v-for="(score, m) in result.scores" :key="m" class="bar-row">
          <span class="bar-label">{{ m }}</span>
          <el-progress :percentage="meridianPct(score, maxMeridian)" :stroke-width="16" style="flex:1;max-width:420px;" :color="meridianColor(score)" />
          <span class="bar-value">{{ score }} 处</span>
        </div>
      </div>

      <el-divider>方域提示</el-divider>
      <p class="suggestion">{{ result.suggestion }}</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const route = useRoute()
const initialPatientId = route.params.id ? Number(route.params.id) : null
const patientId = ref<number | null>(initialPatientId)
const patients = ref<any[]>([])
const submitting = ref(false)
const result = ref<any>(null)
const answers = ref<Record<string, string>>({})
const notes = ref<Record<string, string>>({})

const hasPatient = computed(() => patientId.value !== null && patientId.value !== undefined)
const currentPatientName = computed(() => {
  const p = patients.value.find(x => x.id === patientId.value)
  return p ? p.name : ''
})

// ── 经方家问诊十问（题干与选项） ──
interface QOption { key: string; label: string }
interface Question { key: string; title: string; topic: string; options: QOption[] }

const questions: Question[] = [
  {
    key: 'sleep', title: '1. 问睡眠',
    topic: '你的睡眠如何？是否一觉到天亮？是否每天定时会醒？如果会醒，是几点？是否多梦？',
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
    topic: '你感觉饿吗？有欲望想吃什么特别的食物或味道吗？还是不饿、完全没胃口？',
    options: [
      { key: 'normal', label: '有食欲，食之有味' },
      { key: 'huge', label: '胃口过大、食不知饱' },
      { key: 'no', label: '没胃口、完全不饿' },
      { key: 'tasteless', label: '食之无味' },
    ],
  },
  {
    key: 'stool', title: '3. 问大便',
    topic: '你便秘吗？每天有大便吗？大便颜色是什么？是下利吗？很臭还是无味？',
    options: [
      { key: 'normal', label: '每日一次，成形，软硬适中' },
      { key: 'loose', label: '大便稀溏' },
      { key: 'hard', label: '大便干硬、便秘' },
      { key: 'undigested', label: '下利清谷(有未消化食物)' },
    ],
  },
  {
    key: 'urine', title: '4. 问小便',
    topic: '小便什么颜色？频尿吗？还是尿不出来？还是没有尿意？平均一天几次？',
    options: [
      { key: 'normal', label: '小便淡黄，通畅' },
      { key: 'yellow', label: '小便黄或深黄' },
      { key: 'clear', label: '小便清白、量多' },
    ],
  },
  {
    key: 'thirst', title: '5. 问口渴',
    topic: '你很渴吗？如渴想喝什么温度的水？如不渴会忘记喝水吗？还是再怎么喝也不能止渴？',
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
    topic: '平时觉得身体很热还是很冷？手脚冰冷吗？睡时身体寒热如何？',
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
    topic: '你容易出汗吗？会半夜盗汗吗？会时常流汗不止吗？还是不出汗的身体呢？',
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

const answeredCount = computed(() => questions.filter(q => answers.value[q.key] || (notes.value[q.key] || '').trim()).length)
const maxMeridian = computed(() => Math.max(1, ...Object.values(result.value?.scores || {}).map(Number)))

function meridianPct(score: number, max: number): number {
  return max > 0 ? Math.round((score / max) * 100) : 0
}
function meridianColor(score: number): string {
  if (score >= 2) return '#F5222D'
  if (score === 1) return '#FA8C16'
  return '#52C41A'
}

async function submitScale() {
  if (answeredCount.value < questions.length) {
    ElMessage.warning('请回答全部问题')
    return
  }
  submitting.value = true
  try {
    // 组装答案：已选选项用选项key；仅自填的题记为 custom
    const payloadAnswers: Record<string, string> = {}
    for (const q of questions) {
      if (answers.value[q.key]) payloadAnswers[q.key] = answers.value[q.key]
      else if ((notes.value[q.key] || '').trim()) payloadAnswers[q.key] = 'custom'
    }
    const endpoint = patientId.value ? `/patients/${patientId.value}/constitution` : '/diagnosis/analyze'
    const res = await api.post(endpoint, { answers: payloadAnswers, notes: notes.value }) as any
    result.value = res
    ElMessage.success(patientId.value ? '评估完成，已存入病历' : '评估完成')
  } catch (e: any) {
    ElMessage.error('评估失败：' + (e?.response?.data?.detail || e?.message || '请确认后端已重启且患者存在'))
  }
  submitting.value = false
}

onMounted(async () => {
  if (!patientId.value) {
    try { patients.value = (await api.get('/patients'))?.items || [] } catch {}
    return
  }
  try {
    const existing = await api.get(`/patients/${patientId.value}/constitution`)
    if (existing) result.value = existing
  } catch {}
})
</script>

<style scoped lang="scss">
.question-group {
  margin-bottom: 24px;
  padding: 12px 16px;
  border-radius: 8px;
  background: #faf8f6;
  border-left: 3px solid #8B4513;

  .group-title {
    font-size: 15px;
    font-weight: 600;
    color: #8B4513;
    margin-bottom: 4px;
  }
  .group-topic {
    font-size: 13px;
    color: #888;
    margin-bottom: 12px;
  }
  .options-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .custom-input {
    margin-top: 10px;
    :deep(.el-textarea__inner) { font-size: 13px; background: #fff; }
  }
  .clear-btn { margin-top: 6px; }
  .clear-note { margin-top: 2px; }
}

.submit-bar {
  text-align: center;
  margin-top: 8px;
}

.result-card {
  .result-primary {
    font-size: 16px;
    margin-bottom: 12px;
  }
  .result-labels {
    margin-bottom: 8px;
  }
  .result-label {
    font-weight: 600;
    margin-right: 8px;
  }
  .findings {
    padding-left: 18px;
    color: #555;
    font-size: 14px;
    line-height: 1.9;
    li { margin-bottom: 2px; }
  }
  .meridian-bars {
    .bar-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
      .bar-label { width: 48px; text-align: right; font-size: 13px; }
      .bar-value { width: 40px; font-size: 13px; color: #666; }
    }
  }
  .suggestion {
    color: #8B4513;
    font-size: 14px;
    line-height: 1.8;
  }
}
</style>