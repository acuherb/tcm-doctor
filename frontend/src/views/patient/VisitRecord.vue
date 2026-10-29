<template>
  <div class="visit-record">
    <el-page-header @back="$router.back()" :content="(currentVisitId ? '编辑就诊' : '新增就诊') + ' — ' + patientName" />

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
                @change="onPulseChange">
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

      <div class="ai-section" v-if="form.tcm_disease || form.tcm_syndrome || form.treatment_method">
        <div class="ai-section-title">🩺 辨证论治（理法方药）</div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="中医病名" v-if="form.tcm_disease">{{ form.tcm_disease }}</el-descriptions-item>
          <el-descriptions-item label="证型" v-if="form.tcm_syndrome">{{ form.tcm_syndrome }}</el-descriptions-item>
          <el-descriptions-item label="治法" v-if="form.treatment_method">{{ form.treatment_method }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="ai-section" v-if="aiResultFormulas.length">
        <div class="ai-section-title">💊 推荐方剂（可一键带入开方）</div>
        <div v-for="(f, i) in aiResultFormulas" :key="i" class="formula-card">
          <div class="formula-name">{{ f.name || '推荐方' }}</div>
          <div class="formula-row" v-if="f.composition"><span class="formula-label">组成</span><span>{{ f.composition }}</span></div>
          <div class="formula-row" v-if="f.modification"><span class="formula-label">加减</span><span>{{ f.modification }}</span></div>
          <div class="formula-row" v-if="f.indication"><span class="formula-label">方解</span><span>{{ f.indication }}</span></div>
          <el-button size="small" type="success" @click="goPrescribeWithFormula(f)">去开药（带入该方）</el-button>
        </div>
      </div>

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
const aiResultFormulas = ref<any[]>([])
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
onMounted(async () => {
  await loadDictionary()
  const vid = route.query.visit_id
  if (vid) await loadExistingVisit(Number(vid))
})

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
  pulse_term_ids: [] as number[],
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
    aiResultFormulas.value = Array.isArray(res.recommended_formulas) ? res.recommended_formulas : []
    lastAiFingerprint.value = pendingAiFingerprint
    cachedAiResult.value = { analysis: aiResultText.value, warnings: [...aiResultWarnings.value], basis: aiBasisText.value }
    showAiResult.value = true
    ElMessage.success('AI辨证建议已生成')
  } catch {}
  aiLoading.value = false
}

async function saveAiIntoRecord() {
  const basis = aiBasisText.value ? `【本次辨证依据】\n${aiBasisText.value}\n\n` : ''
  const warnings = aiResultWarnings.value.length ? `\n【注意事项】\n${aiResultWarnings.value.join('\n')}\n` : ''
  const formulaText = aiResultFormulas.value.length
    ? '\n\n【推荐方剂】\n' + aiResultFormulas.value
        .map((f: any) => `- ${f.name || '推荐方'}：${f.composition || ''}${f.modification ? `（加减：${f.modification}）` : ''}`)
        .join('\n')
    : ''
  form.value.ai_analysis = `${basis}【AI 辨证分析】\n${aiResultText.value}${warnings}${formulaText}`
  if (currentVisitId.value != null) {
    try {
      await api.put(`/patients/${patientId}/visits/${currentVisitId.value}`, { ai_analysis: form.value.ai_analysis })
      ElMessage.success('已存入本就诊 AI 诊断库')
    } catch (e: any) {
      ElMessage.error('入库失败：' + (e?.response?.data?.detail || e?.message || ''))
    }
  } else {
    ElMessage.success('AI 辨证建议已采纳，请点「保存就诊记录」后即可在病历详情查看')
  }
  showAiResult.value = false
}

// 将 AI 推荐方剂带入开方页（预填方名与药味）
function goPrescribeWithFormula(f: any) {
  const q: any = { patient_id: patientId }
  if (currentVisitId.value != null) q.visit_id = currentVisitId.value
  q.ai_formula = JSON.stringify({ name: f.name || '', composition: f.composition || '' })
  router.push({ path: '/prescriptions/new', query: q })
}

async function submitVisit() {
  if (!form.value.chief_complaint) {
    ElMessage.warning('请填写主诉')
    return
  }
  submitting.value = true
  try {
    const payload = { ...form.value, pulse: form.value.pulse.join('、') }
    // 已有就诊则更新（完善/补充病历），否则新建，避免重复建就诊
    if (currentVisitId.value != null) {
      const res = await api.put(`/patients/${patientId}/visits/${currentVisitId.value}`, payload, { silent: true }) as any
      ElMessage.success('就诊记录已更新')
      return res
    }
    const res = await api.post(`/patients/${patientId}/visits`, payload, { silent: true }) as any
    currentVisitId.value = res.id
    ElMessage.success('就诊记录已保存，可在右侧完成本次问诊十问，或下方去开药')
    return res
  } catch (e: any) {
    ElMessage.error('保存失败：' + (e?.response?.data?.detail || e?.message || ''))
  } finally {
    submitting.value = false
  }
}

// 脉象多选：记录全部词条 id（避免只保留第一项导致其余脉象词条丢失）
function onPulseChange() {
  const ids = form.value.pulse
    .map((name: string) => pulseTerms.value.find((p: any) => p.name === name)?.id)
    .filter((id: number | undefined): id is number => id != null)
  form.value.pulse_term_ids = ids
  form.value.pulse_term_id = ids[0] ?? null
}

// 编辑已有就诊：从病历详情页带入 visit_id 时加载并填充表单，便于完善病例报告
async function loadExistingVisit(visitId: number) {
  try {
    const res = await api.get(`/patients/${patientId}/visits/${visitId}`) as any
    currentVisitId.value = res.id
    const { pulse, ...rest } = res
    Object.assign(form.value, rest)
    form.value.pulse = (res.pulse || '').split('、').filter(Boolean)
    form.value.pulse_term_ids = res.pulse_term_ids || []
  } catch {
    ElMessage.error('加载就诊记录失败')
  }
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
/* markdown 渲染样式（AI 辨证结果含标题/列表/表格/代码块） */
.ai-result-body, .ai-basis-body {
  :deep(h1), :deep(h2), :deep(h3), :deep(h4) { margin: 12px 0 6px; color: #8B4513; line-height: 1.4; }
  :deep(h1) { font-size: 18px; }
  :deep(h2) { font-size: 16px; }
  :deep(h3) { font-size: 15px; }
  :deep(p) { margin: 6px 0; }
  :deep(ul), :deep(ol) { margin: 6px 0; padding-left: 22px; }
  :deep(li) { margin: 3px 0; }
  :deep(table) { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 13px; }
  :deep(th), :deep(td) { border: 1px solid #e8e0d8; padding: 4px 8px; text-align: left; }
  :deep(th) { background: #faf7f4; }
  :deep(strong) { color: #8B4513; }
  :deep(code) {
    background: #f5f0eb; padding: 0 4px; border-radius: 4px; font-size: 13px;
  }
  :deep(pre) { background: #f5f0eb; padding: 10px; border-radius: 6px; overflow-x: auto; }
  :deep(pre code) { background: transparent; padding: 0; }
  :deep(blockquote) { border-left: 3px solid #d9c9a3; margin: 6px 0; padding-left: 10px; color: #999; }
}
.ai-result-body strong { color: #8B4513; }
.ai-result-body code {
  background: #f5f0eb;
  padding: 0 4px;
  border-radius: 4px;
  font-size: 13px;
}

/* 辨证论治摘要 + 推荐方剂卡片 */
.ai-section { margin-top: 14px; }
.ai-section-title {
  font-weight: 600;
  color: #8B4513;
  margin-bottom: 8px;
  font-size: 14px;
}
.formula-card {
  border: 1px solid #e8e0d8;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
  background: #fffdf9;
}
.formula-name {
  font-weight: 700;
  color: #6b4f2a;
  font-size: 15px;
  margin-bottom: 6px;
}
.formula-row {
  display: flex;
  gap: 8px;
  font-size: 13px;
  line-height: 1.7;
  margin-bottom: 2px;
}
.formula-label {
  flex: 0 0 40px;
  color: #999;
}
.formula-card :deep(.el-button) { margin-top: 8px; }

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