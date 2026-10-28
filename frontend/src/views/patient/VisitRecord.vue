<template>
  <div class="visit-record">
    <el-page-header @back="$router.back()" :content="`新增就诊 — ${patientName}`" />

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 左: 四诊信息 -->
      <el-col :xs="24" :lg="12" class="left-col">
        <el-card shadow="hover">
          <template #header><span>🔍 四诊信息</span></template>
          <el-form :model="form" label-width="80px" label-position="top">
            <el-form-item label="主诉" required>
              <el-input v-model="form.chief_complaint" placeholder="如：胃脘胀痛3天" />
            </el-form-item>
            <el-form-item label="现病史">
              <el-input v-model="form.present_illness" type="textarea" :rows="3" />
            </el-form-item>

            <el-divider content-position="left">望诊</el-divider>
            <el-form-item label="望诊(面色/神态/形体)">
              <el-input v-model="form.observation" type="textarea" :rows="2" placeholder="如：面色萎黄，神疲倦怠" />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :xs="24" :sm="12">
                <el-form-item label="舌质">
                  <el-select v-model="form.tongue_body" clearable filterable placeholder="选择舌质" style="width:100%"
                    @change="form.tongue_body_term_id = findId('tongue', form.tongue_body, '舌质')">
                    <el-option v-for="t in tongueBodyTerms" :key="t.id" :label="t.name" :value="t.name">
                      <div class="term-opt"><span class="term-name">{{ t.name }}</span><span v-if="t.description" class="term-desc">{{ t.description }}</span></div>
                    </el-option>
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="舌苔">
                  <el-select v-model="form.tongue_coat" clearable filterable placeholder="选择舌苔" style="width:100%"
                    @change="form.tongue_coat_term_id = findId('tongue', form.tongue_coat, '舌苔')">
                    <el-option v-for="t in tongueCoatTerms" :key="t.id" :label="t.name" :value="t.name">
                      <div class="term-opt"><span class="term-name">{{ t.name }}</span><span v-if="t.description" class="term-desc">{{ t.description }}</span></div>
                    </el-option>
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <!-- 舌象/面色照片上传 -->
            <el-row :gutter="12">
              <el-col :xs="24" :sm="12">
                <el-form-item label="舌象照片">
                  <div class="img-upload-row">
                    <el-button size="small" @click="triggerVisitImage('tongue')">📷 拍摄/上传</el-button>
                    <el-image v-if="visitImages.tongue" :src="visitImages.tongue" fit="cover" class="visit-thumb"
                      :preview-src-list="[visitImages.tongue]" />
                    <el-icon v-if="visitImages.tongue" class="remove-visit-img" @click="visitImages.tongue = ''"><Close /></el-icon>
                  </div>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="面色照片">
                  <div class="img-upload-row">
                    <el-button size="small" @click="triggerVisitImage('face')">📷 拍摄/上传</el-button>
                    <el-image v-if="visitImages.face" :src="visitImages.face" fit="cover" class="visit-thumb"
                      :preview-src-list="[visitImages.face]" />
                    <el-icon v-if="visitImages.face" class="remove-visit-img" @click="visitImages.face = ''"><Close /></el-icon>
                  </div>
                </el-form-item>
              </el-col>
            </el-row>

            <el-divider content-position="left">闻诊</el-divider>
            <el-form-item label="闻诊(语声/呼吸/气味)">
              <el-input v-model="form.auscultation" type="textarea" :rows="2" placeholder="如：语声低微" />
            </el-form-item>

            <el-divider content-position="left">问诊</el-divider>
            <el-form-item label="问诊(寒热/汗出/饮食/睡眠/二便)">
              <el-input v-model="form.inquiry" type="textarea" :rows="3" placeholder="如：畏寒怕冷，纳差，大便溏薄" />
            </el-form-item>

            <el-divider content-position="left">切诊</el-divider>
            <el-form-item label="脉象">
              <el-select v-model="form.pulse" multiple clearable filterable placeholder="选择脉象" style="width:100%"
                @change="form.pulse_term_id = form.pulse.length ? (pulseTerms.find(p => p.name === form.pulse[0])?.id ?? null) : null">
                <el-option v-for="t in pulseTerms" :key="t.id" :label="t.name" :value="t.name">
                  <div class="term-opt"><span class="term-name">{{ t.name }}</span><span v-if="t.description" class="term-desc">{{ t.description }}</span></div>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="切诊(其他)">
              <el-input v-model="form.palpation" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="hover" class="right-col-equal">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span>🩺 辨证论治 (理法方药)</span>
              <div style="display:flex;gap:8px;">
                <el-button size="small" @click="triggerVisitImage('lab')">📷 化验单</el-button>
                <el-button type="primary" size="small" @click="aiAssist" :loading="aiLoading">
                  <el-icon><ChatDotRound /></el-icon> AI辅助辨证
                </el-button>
              </div>
            </div>
          </template>
          <!-- 已上传化验单预览 -->
          <div v-if="visitImages.lab.length" class="lab-preview">
            <span class="lab-label">已上传化验单：</span>
            <el-image v-for="(img, i) in visitImages.lab" :key="i" :src="img" fit="cover" class="lab-thumb"
              :preview-src-list="visitImages.lab" :initial-index="i" />
            <el-button size="small" text type="danger" @click="visitImages.lab = []">清除</el-button>
          </div>
          <el-form :model="form" label-width="80px" label-position="top">
            <el-form-item label="中医病名">
              <el-input v-model="form.tcm_disease" placeholder="如：胃脘痛" />
            </el-form-item>
            <el-form-item label="证型">
              <el-select v-model="form.tcm_syndrome" clearable filterable allow-create default-first-option
                placeholder="选证书型或输入" style="width:100%"
                @change="form.syndrome_term_id = findId('syndrome', form.tcm_syndrome)">
                <el-option v-for="t in syndromeTerms" :key="t.id" :label="t.name" :value="t.name">
                  <div class="term-opt"><span class="term-name">{{ t.name }}</span><span v-if="t.description" class="term-desc">{{ t.description }}</span></div>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="治法">
              <el-input v-model="form.treatment_method" placeholder="如：疏肝理气" />
            </el-form-item>
            <el-form-item label="医嘱/调护">
              <el-input v-model="form.doctor_notes" type="textarea" :rows="3" placeholder="饮食禁忌、生活调摄等" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右: 问诊十问 -->
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover">
          <template #header><span>🪷 问诊十问（经方家辨证）</span></template>
          <TenAspectsPanel ref="tenAspectsRef" :patient-id="patientId" :visit-id="currentVisitId" />
        </el-card>

        <div style="margin-top: 16px; text-align: right;">
          <el-button @click="$router.back()">取消</el-button>
          <el-button type="primary" @click="submitVisit" :loading="submitting">保存就诊记录</el-button>
        </div>

        <div v-if="currentVisitId" class="visit-saved-hint">
          <div class="hint-title">✓ 本次就诊已保存（ID: {{ currentVisitId }}），可继续在上方完成本次问诊十问，或：</div>
          <div style="text-align: right; margin-top: 8px;">
            <el-button @click="$router.push(`/patients/${patientId}`)">返回详情</el-button>
            <el-button type="primary" @click="$router.push(`/prescriptions/new?patient_id=${patientId}&visit_id=${currentVisitId}`)">去开药</el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 隐藏的图片上传 input -->
    <input ref="visitFileInputRef" type="file" accept="image/*" style="display:none" @change="onVisitImageSelect" />

    <!-- AI 辨证前核对 -->
    <el-dialog v-model="showAiConfirm" title="🪧 核对本次辨证信息" width="620px" class="ai-basis-dialog">
      <div class="ai-basis-block">
        <div class="ai-basis-title">本次将依据以下信息进行辨证</div>
        <div class="ai-basis-body" v-html="renderMarkdown(aiBasisText)"></div>
      </div>
      <div v-if="aiResultWarnings.length" class="ai-warning-row">
        <el-alert v-for="w in aiResultWarnings" :key="w" :title="w" type="warning" :closable="false" show-icon />
      </div>
      <template #footer>
        <el-button @click="showAiConfirm = false">返回修改</el-button>
        <el-button type="primary" :loading="aiLoading" @click="doAiAnalyze">确认无误，开始分析</el-button>
      </template>
    </el-dialog>

    <!-- AI 辨证分析结果 -->
    <el-dialog v-model="showAiResult" title="🤖 AI 辨证分析结果" width="660px" class="ai-result-dialog">
      <div v-if="aiBasisText" class="ai-basis-block">
        <div class="ai-basis-title">🪧 本次辨证依据</div>
        <div class="ai-basis-body" v-html="renderMarkdown(aiBasisText)"></div>
      </div>
      <div v-for="w in aiResultWarnings" :key="w" class="ai-warning-row">
        <el-alert :title="w" type="warning" :closable="false" show-icon />
      </div>
      <div class="ai-result-body" v-html="renderMarkdown(aiResultText)"></div>
      <template #footer>
        <el-button @click="showAiResult = false">仅查看，不入库</el-button>
        <el-button type="primary" @click="saveAiIntoRecord">存入本就诊 AI 诊断库</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Close } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { renderMarkdown } from '@/utils/markdown'
import TenAspectsPanel from '@/components/TenAspectsPanel.vue'

const tenAspectsRef = ref<{ getAspectSummary: () => string; getAspectAnswers?: () => { answers: Record<string, string>; notes: Record<string, string> } } | null>(null)

const route = useRoute()
const router = useRouter()
const patientId = Number(route.params.id)
const patientName = (route.query.name as string) || ''
const submitting = ref(false)
const aiLoading = ref(false)
const currentVisitId = ref<number | null>(null)
const showAiResult = ref(false)
const showAiConfirm = ref(false)
const aiResultText = ref('')
const aiResultWarnings = ref<string[]>([])
const aiBasisText = ref('')
// 待分析上下文（点击「开始分析」后再真正请求；避免未核对的误请求）
let pendingAiPayload: any = null
let pendingAiFingerprint = ''
// 缓存：同一组辨证输入不重复请求(避免关闭重开再次消耗 token)
const lastAiFingerprint = ref('')
const cachedAiResult = ref<{ analysis: string; warnings: string[]; basis: string } | null>(null)

// 受控词条选项：从字典 API 动态加载
interface DictTerm {
  id: number
  term_type: string
  name: string
  aspect?: string | null
}
const dictTerms = ref<DictTerm[]>([])
const tongueBodyTerms = computed(() => dictTerms.value.filter(t => t.term_type === 'tongue' && t.aspect === '舌质'))
const tongueCoatTerms = computed(() => dictTerms.value.filter(t => t.term_type === 'tongue' && t.aspect === '舌苔'))
const pulseTerms = computed(() => dictTerms.value.filter(t => t.term_type === 'pulse'))
const syndromeTerms = computed(() => dictTerms.value.filter(t => t.term_type === 'syndrome'))

function findId(termType: string, name: string, aspect?: string): number | null {
  if (!name) return null
  const t = dictTerms.value.find(x =>
    x.term_type === termType && x.name === name &&
    (aspect === undefined || x.aspect === aspect)
  )
  return t ? t.id : null
}

async function loadDictionary() {
  try {
    const res = await api.get('/dictionaries') as any
    dictTerms.value = Array.isArray(res) ? res : []
  } catch { /* 后端不可用时回退为空选项 */ }
}
onMounted(loadDictionary)

const form = ref({
  visit_date: new Date().toISOString().slice(0, 10),
  chief_complaint: '',
  present_illness: '',
  observation: '',
  auscultation: '',
  inquiry: '',
  palpation: '',
  tongue_body: '',
  tongue_coat: '',
  pulse: [] as string[],
  tcm_disease: '',
  tcm_syndrome: '',
  treatment_method: '',
  ai_analysis: '',
  doctor_notes: '',
  // 受控词条关联 id (选择字典词条时自动填充)
  tongue_body_term_id: null as number | null,
  tongue_coat_term_id: null as number | null,
  pulse_term_id: null as number | null,
  syndrome_term_id: null as number | null,
})

// 图片上传
const visitFileInputRef = ref<HTMLInputElement>()
const visitImageTarget = ref<'tongue' | 'face' | 'lab'>('tongue')
const visitImages = ref<{ tongue: string; face: string; lab: string[] }>({ tongue: '', face: '', lab: [] })

function triggerVisitImage(target: 'tongue' | 'face' | 'lab') {
  visitImageTarget.value = target
  visitFileInputRef.value?.click()
}

async function onVisitImageSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片不能超过5MB')
    return
  }
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.post('/diagnosis/upload-image', formData) as any
    const target = visitImageTarget.value
    if (target === 'lab') {
      visitImages.value.lab.push(res.data_url)
    } else {
      visitImages.value[target] = res.data_url
    }
  } catch {
    ElMessage.error('图片上传失败')
  }
  input.value = ''
}

async function aiAssist() {
  if (!form.value.chief_complaint) {
    ElMessage.warning('请先填写主诉')
    return
  }
  // 组装当前录入的信息与输入指纹
  const aspects = tenAspectsRef.value?.getAspectSummary() || ''
  const tenAns = tenAspectsRef.value?.getAspectAnswers?.()

  const basisLines: string[] = []
  basisLines.push(`主诉：${form.value.chief_complaint}`)
  const fourDiag: [string, string][] = [
    ['望诊', form.value.observation],
    ['闻诊', form.value.auscultation],
    ['问诊', form.value.inquiry],
    ['切诊', form.value.palpation],
    ['舌质', form.value.tongue_body],
    ['舌苔', form.value.tongue_coat],
    ['脉象', form.value.pulse.join('、')],
  ]
  for (const [k, v] of fourDiag) if (v) basisLines.push(`${k}：${v}`)
  if (aspects) basisLines.push('—— 问诊十问 ——\n' + aspects)

  const fingerprint = JSON.stringify({
    complaint: form.value.chief_complaint,
    observation: form.value.observation,
    inquiry: form.value.inquiry,
    palpation: form.value.palpation,
    tongue_body: form.value.tongue_body,
    tongue_coat: form.value.tongue_coat,
    pulse: form.value.pulse.join('、'),
    aspects,
  })

  // 缓存命中：同一输入直接回显结果，不重复请求(零 token)
  if (cachedAiResult.value && fingerprint === lastAiFingerprint.value) {
    aiResultText.value = cachedAiResult.value.analysis
    aiResultWarnings.value = cachedAiResult.value.warnings
    aiBasisText.value = cachedAiResult.value.basis
    showAiResult.value = true
    ElMessage.info('沿用上次辨证结果（未重新请求，节省 token）')
    return
  }

  // 未命中缓存：先展示当前收集的信息供核对，确认后再真正请求
  aiBasisText.value = basisLines.join('\n')
  pendingAiFingerprint = fingerprint
  pendingAiPayload = {
    chief_complaint: form.value.chief_complaint,
    observation: form.value.observation,
    auscultation: form.value.auscultation,
    inquiry: form.value.inquiry,
    palpation: form.value.palpation,
    tongue_body: form.value.tongue_body,
    tongue_coat: form.value.tongue_coat,
    pulse: form.value.pulse.join('、'),
    patient_gender: '',
    is_pregnant: false,
  }
  if (aspects) pendingAiPayload.ten_aspects = aspects
  if (tenAns && Object.keys(tenAns.answers || {}).length) pendingAiPayload.ten_answers = tenAns
  if (visitImages.value.tongue) pendingAiPayload.tongue_image = visitImages.value.tongue
  if (visitImages.value.face) pendingAiPayload.face_image = visitImages.value.face
  if (visitImages.value.lab.length) pendingAiPayload.lab_report_images = visitImages.value.lab

  showAiConfirm.value = true
}

async function doAiAnalyze() {
  if (!pendingAiPayload) return
  aiLoading.value = true
  showAiConfirm.value = false
  try {
    const res = await api.post('/diagnosis/analyze', pendingAiPayload) as any
    if (res.tcm_disease) form.value.tcm_disease = res.tcm_disease
    if (res.tcm_syndrome) form.value.tcm_syndrome = res.tcm_syndrome
    if (res.treatment_method) form.value.treatment_method = res.treatment_method
    aiResultText.value = res.syndrome_analysis || ''
    aiResultWarnings.value = res.safety_warnings || []
    lastAiFingerprint.value = pendingAiFingerprint
    cachedAiResult.value = { analysis: aiResultText.value, warnings: [...aiResultWarnings.value], basis: aiBasisText.value }
    showAiResult.value = true
    ElMessage.success('AI辨证建议已生成')
  } catch {}
  aiLoading.value = false
}

function saveAiIntoRecord() {
  const basis = aiBasisText.value ? `【本次辨证依据】\n${aiBasisText.value}\n\n` : ''
  const warnings = aiResultWarnings.value.length ? `\n【注意事项】\n${aiResultWarnings.value.join('\n')}\n` : ''
  form.value.ai_analysis = `${basis}【AI 辨证分析】\n${aiResultText.value}${warnings}`
  showAiResult.value = false
  ElMessage.success('已存入本就诊 AI 诊断库，保存就诊记录后将一并落库')
}

function renderMarkdown(text: string) {
  return text
    ? text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>')
    : ''
}

async function submitVisit() {
  if (!form.value.chief_complaint) {
    ElMessage.warning('请填写主诉')
    return
  }
  submitting.value = true
  try {
    const payload = { ...form.value, pulse: form.value.pulse.join('、') }
    const res = await api.post(`/patients/${patientId}/visits`, payload) as any
    currentVisitId.value = res.id
    ElMessage.success('就诊记录已保存，可在右侧完成本次问诊十问，或下方去开药')
  } catch (e: any) {
    ElMessage.error('保存失败：' + (e?.response?.data?.detail || e?.message || ''))
  }
  submitting.value = false
}
</script>

<style scoped>
.el-divider { margin: 12px 0 16px; }

.left-col { display: flex; flex-direction: column; }
.right-col-equal { margin-top: 24px; }

.img-upload-row {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;

  .visit-thumb {
    width: 40px;
    height: 40px;
    border-radius: 4px;
    border: 1px solid #e8e0d8;
  }

  .remove-visit-img {
    position: absolute;
    top: -4px;
    left: 96px;
    background: #f56c6c;
    color: #fff;
    border-radius: 50%;
    width: 16px;
    height: 16px;
    cursor: pointer;
    font-size: 10px;
  }
}

.lab-preview {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  padding: 8px;
  background: #f5f0eb;
  border-radius: 6px;
  flex-wrap: wrap;

  .lab-label { font-size: 13px; color: #8B4513; }

  .lab-thumb {
    width: 48px;
    height: 48px;
    border-radius: 4px;
    border: 1px solid #e8e0d8;
    cursor: pointer;
  }
}

/* 词条下拉释义提示 */
.term-opt {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
  padding: 2px 0;
}
.term-name {
  font-weight: 500;
  color: var(--el-text-color-primary);
}
.term-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.visit-saved-hint {
  margin-top: 16px;
  padding: 12px 14px;
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 8px;
}
.visit-saved-hint .hint-title { font-size: 13px; color: #67c23a; }

/* AI 辨证分析结果弹窗 */
.ai-result-dialog :deep(.el-dialog__body),
.ai-basis-dialog :deep(.el-dialog__body) {
  max-height: 60vh;
  overflow-y: auto;
}
.ai-warning-row { margin-bottom: 8px; }
.ai-basis-block {
  border: 1px dashed #d9c9a3;
  background: #fffbf0;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.ai-basis-title {
  font-weight: 600;
  color: #8B4513;
  margin-bottom: 6px;
}
.ai-basis-body {
  font-size: 13px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
  white-space: normal;
}
.ai-result-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
  white-space: normal;
}
.ai-result-body strong { color: #8B4513; }
.ai-result-body code {
  background: #f5f0eb;
  padding: 0 4px;
  border-radius: 4px;
  font-size: 13px;
}

/* 移动端适配 */
@media (max-width: 767px) {
  .visit-record :deep(.el-page-header__content) {
    font-size: 16px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  /* 辨证论治卡片头部按钮换行 */
  :deep(.el-card__header) {
    padding: 12px 14px;
  }
  .img-upload-row {
    flex-wrap: wrap;
  }
  .remove-visit-img {
    position: static;
  }
  /* 底部操作按钮全宽 */
  .visit-saved-hint .el-button {
    margin-top: 8px;
  }
  :deep(.lab-preview) {
    align-items: flex-start;
  }
}
</style>