<template>
  <div class="visit-record">
    <el-page-header v-if="!props.embedded" @back="$router.back()" :content="(currentVisitId ? '编辑就诊' : '新增就诊') + ' — ' + patientName" />

    <el-alert v-if="patientTagInfos.length" type="warning" show-icon :closable="false" style="margin-top:16px;"
      title="该患者带标签提醒，请关注：">
      <template #default>
        <div class="tag-reminders">
          <div v-for="ti in patientTagInfos" :key="ti.name" class="tag-remind-item">
            <el-tag size="small" effect="plain" :style="tagRemindStyle(ti)">{{ ti.name }}</el-tag>
            <span class="tag-remind-desc">{{ ti.description }}</span>
          </div>
        </div>
      </template>
    </el-alert>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 左: 四诊信息 -->
      <el-col :xs="24" :lg="12" class="left-col">
        <el-card shadow="hover" class="tcm-visit-card">
          <template #header><span>🔍 四诊信息</span></template>
          <div v-if="lastVisitHint || lastVisit" class="visit-type-hint">
            <template v-if="lastVisitHint">{{ lastVisitHint }}</template>
            <el-button v-if="lastVisit && currentVisitId == null" size="small" type="warning" style="margin-left:8px;" @click="applyLastVisitDraft">📋 参照上次</el-button>
            <span v-if="lastVisit && lastVisit.prescriptions && lastVisit.prescriptions.length" class="vit-last-rx">
              上次处方：{{ lastVisit.prescriptions.map((r: any) => r.formula_name || r.id).join('、') }}
            </span>
          </div>
          <el-form :model="form" label-width="80px" label-position="top">
            <el-form-item label="就诊类型" required>
              <el-radio-group v-model="form.visit_type" @change="onVisitTypeChange">
                <el-radio-button value="初诊">初诊</el-radio-button>
                <el-radio-button value="复诊">复诊</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="form.visit_type === '复诊'" label="关联初诊" required>
              <el-select v-model="form.parent_visit_id" placeholder="选择本次复诊对应的初诊" filterable clearable style="width:100%">
                <el-option
                  v-for="r in rootVisits"
                  :key="r.id"
                  :value="r.id"
                  :label="`${r.visit_date} · ${r.chief_complaint || r.tcm_disease || '初诊'}`"
                />
              </el-select>
              <div v-if="!rootVisits.length" class="form-tip">该患者暂无初诊记录，请先建立初诊后再添加复诊</div>
              <div v-else class="form-tip">请选择本次复诊归属的初诊，便于归入同一次完整就诊</div>
            </el-form-item>
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
                    <el-button size="small" @click="triggerVisitImage('tongue','camera')">📷 拍摄</el-button>
                    <el-button size="small" @click="triggerVisitImage('tongue','album')">🖼 相册</el-button>
                    <span v-if="visitImages.tongue" class="visit-thumb-wrap">
                      <PinchImage :src="visitImages.tongue" thumb-class="pinch-thumb" />
                      <el-icon class="remove-visit-img" @click="visitImages.tongue = ''"><Close /></el-icon>
                    </span>
                  </div>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="面色照片">
                  <div class="img-upload-row">
                    <el-button size="small" @click="triggerVisitImage('face','camera')">📷 拍摄</el-button>
                    <el-button size="small" @click="triggerVisitImage('face','album')">🖼 相册</el-button>
                    <span v-if="visitImages.face" class="visit-thumb-wrap">
                      <PinchImage :src="visitImages.face" thumb-class="pinch-thumb" />
                      <el-icon class="remove-visit-img" @click="visitImages.face = ''"><Close /></el-icon>
                    </span>
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

        <el-card shadow="hover" class="tcm-visit-card right-col-equal">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
              <span>🩺 辨证论治 (理法方药)</span>
              <el-button type="primary" size="small" @click="aiAssist" :loading="aiLoading">
                <el-icon><ChatDotRound /></el-icon> AI辅助辨证
              </el-button>
            </div>
          </template>
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

        <!-- 其他资料补充：独立于四诊与辨证论治，按需上传纸质/影像资料 -->
        <el-card shadow="hover" class="tcm-visit-card other-files-card">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
              <span>📎 其他资料补充</span>
              <div style="display:flex;gap:8px;">
                <el-button size="small" @click="triggerVisitImage('lab','camera')">📷 拍摄</el-button>
                <el-button size="small" @click="triggerVisitImage('lab','album')">🖼 相册</el-button>
              </div>
            </div>
          </template>
          <div v-if="visitImages.lab.length" class="lab-preview">
            <span class="lab-label">已上传 {{ visitImages.lab.length }} 张：</span>
            <PinchImage v-for="(img, i) in visitImages.lab" :key="i" :src="img" :list="visitImages.lab" :index="i" thumb-class="lab-thumb" />
            <el-button size="small" text type="danger" @click="visitImages.lab = []">清除全部</el-button>
          </div>
          <div v-else class="form-tip">可补充上传化验单、诊断报告、既往病历等纸质资料（最多 {{ MAX_LAB }} 张）</div>
        </el-card>
      </el-col>

      <!-- 右: 问诊十问 -->
      <el-col :xs="24" :lg="12" class="right-col">
        <el-card shadow="hover" class="tcm-visit-card">
          <template #header><span>🪷 问诊十问（经方家辨证）</span></template>
          <TenAspectsPanel ref="tenAspectsRef" :patient-id="patientId" :visit-id="currentVisitId" :initial="initialIq" />
        </el-card>

        <div style="text-align: right;">
          <el-button @click="onCancel">取消</el-button>
          <el-button type="primary" @click="submitVisit" :loading="submitting">保存就诊记录</el-button>
        </div>

        <div v-if="currentVisitId" class="visit-saved-hint">
          <div class="hint-title">✓ 本次就诊已保存（ID: {{ currentVisitId }}），可继续在上方完成本次问诊十问，或：</div>
          <div style="text-align: right; margin-top: 8px;">
            <el-button @click="props.embedded ? onCancel() : $router.push(`/patients/${patientId}`)">返回详情</el-button>
            <el-button type="primary" @click="$router.push(`/prescriptions/new?patient_id=${patientId}&visit_id=${currentVisitId}`)">去开药</el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 隐藏的图片上传 input：拍摄(相机) + 相册(选择) -->
    <input ref="visitFileInputRef" type="file" accept="image/*" style="display:none" @change="onVisitImageSelect" />
    <input ref="visitCameraInputRef" type="file" accept="image/*" capture="camera" style="display:none" @change="onVisitImageSelect" />

    <!-- 桌面端拍摄：网页摄像头捕捉 -->
    <el-dialog v-model="showCamera" title="📷 拍摄照片" width="420px" append-to-body class="camera-dialog" @closed="stopCamera">
      <div class="camera-box">
        <video ref="cameraVideoRef" autoplay playsinline muted></video>
        <canvas ref="cameraCanvasRef" style="display:none"></canvas>
      </div>
      <template #footer>
        <el-button @click="stopCamera">取消</el-button>
        <el-button type="primary" @click="capturePhoto">拍摄</el-button>
      </template>
    </el-dialog>

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
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Close } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { renderMarkdown } from '@/utils/markdown'
import { compressImageFile } from '@/utils/image'
import { TEN_QUESTIONS } from '@/utils/tenAspectsQuestions'
import TenAspectsPanel from '@/components/TenAspectsPanel.vue'
import PinchImage from '@/components/PinchImage.vue'

const tenAspectsRef = ref<{ getAspectSummary: () => string; getAspectAnswers?: () => { answers: Record<string, string>; notes: Record<string, string> } } | null>(null)

const props = defineProps<{
  patientId?: number
  patientName?: string
  patientTags?: string[]
  visitId?: number | null
  parentVisit?: any
  embedded?: boolean
}>()
const emit = defineEmits<{ saved: [any]; cancel: [] }>()
const route = useRoute()
const router = useRouter()
const patientId = props.patientId ?? Number(route.params.id)
const patientName = props.patientName ?? (route.query.name as string) ?? ''
const effectiveVisitId = props.visitId ?? (route.query.visit_id ? Number(route.query.visit_id) : null)
// 患者标签：用于在治疗页提示（如"不遵医瞩"→慎用峻药）
const patientTags = ref<string[]>([])
// 根据字典释义匹配患者标签，进入就诊页时提醒医生
const patientTagInfos = computed(() => {
  return patientTags.value
    .map(name => {
      const t = dictTerms.value.find(x => x.term_type === 'tag' && x.name === name)
      return { name, description: (t?.description || '').trim(), color: t?.color || '' }
    })
    .filter(x => x.description)
})
function tagRemindStyle(ti: { color: string }): Record<string, string> {
  const c = ti.color || '#909399'
  return { color: c, borderColor: c, backgroundColor: '#fff' }
}
const submitting = ref(false)
const aiLoading = ref(false)
const currentVisitId = ref<number | null>(null)
// 二次编辑时回填上一次问诊十问（选项/自填/结果）
const initialIq = ref<any>(null)
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
  description?: string | null
  color?: string | null
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
  if (props.patientTags) {
    patientTags.value = props.patientTags
  } else {
    try {
      const p = (await api.get(`/patients/${patientId}`)) as any
      patientTags.value = p.tags || []
    } catch {}
  }
  // 加载既有就诊记录，用于自动推断初诊/复诊
  try {
    const vl = (await api.get(`/patients/${patientId}/visits`)) as any
    visits.value = vl || []
  } catch {}
  if (effectiveVisitId != null) {
    await loadExistingVisit(effectiveVisitId)
    // 取该就诊已存的问诊十问，回填到右侧面板，避免二次编辑从头重选
    try {
      const iqs = (await api.get(`/patients/${patientId}/inquiries`, { params: { visit_id: effectiveVisitId } })) as any
      if (iqs && iqs.length) initialIq.value = iqs[0]
    } catch {}
  }
  // 基于某次初诊发起复诊：以该初诊为底稿预填，并标记 parent 关系
  else if (props.parentVisit) applyParentVisit(props.parentVisit)
})

// 以父就诊(初诊)为底稿预填复诊表单
function applyParentVisit(p: any) {
  form.value.visit_type = '复诊'
  form.value.parent_visit_id = p.id
  const set = (k: string, v: any) => { if (v != null && v !== '') (form.value as any)[k] = v }
  set('present_illness', p.present_illness)
  set('observation', p.observation)
  set('auscultation', p.auscultation)
  set('inquiry', p.inquiry)
  set('palpation', p.palpation)
  set('tongue_body', p.tongue_body)
  set('tongue_coat', p.tongue_coat)
  set('tcm_disease', p.tcm_disease)
  set('tcm_syndrome', p.tcm_syndrome)
  set('treatment_method', p.treatment_method)
  if (p.pulse) form.value.pulse = String(p.pulse).split('、').filter(Boolean)
  loadLastPrescription(p.id)
}

// 同患者既往就诊（用于初诊/复诊自动判断）
const visits = ref<any[]>([])
const lastVisitHint = ref('')
// 上次同病种就诊（复诊时作为四诊/证型/处方的参照底稿）
const lastVisit = ref<any>(null)

// 可作为「本次复诊」父节点的初诊列表（parent_visit_id 为空者），供用户明确选择归属
const rootVisits = computed<any[]>(() => {
  const cur = effectiveVisitId
  return (visits.value || [])
    .filter((v: any) => v.parent_visit_id == null && v.id !== cur)
    .sort((a: any, b: any) => b.visit_date.localeCompare(a.visit_date))
})
// 给定就诊，沿 parent 链找到其所属初诊根节点 id
function findRootId(v: any): number {
  let cur = v
  const byId = new Map((visits.value || []).map((x: any) => [x.id, x]))
  while (cur && cur.parent_visit_id != null && byId.has(cur.parent_visit_id)) {
    cur = byId.get(cur.parent_visit_id)
  }
  return cur ? cur.id : v.id
}
// 切换就诊类型：选初诊则清除关联初诊；选复诊时若已通过「＋复诊」预设父节点则保留
function onVisitTypeChange(t: string) {
  if (t === '初诊') form.value.parent_visit_id = null
}

const form = ref({
  visit_date: new Date().toISOString().slice(0, 10),
  visit_type: '初诊',
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
  parent_visit_id: null as number | null,
})

// 病名变化时自动推断：同病种曾就诊 → 复诊，否则初诊
watch(
  () => form.value.tcm_disease,
  (d) => {
    if (!d || currentVisitId.value != null) {
      if (!d) { lastVisitHint.value = ''; lastVisit.value = null }
      return
    }
    const hit = visits.value
      .filter((v: any) => v.tcm_disease && v.tcm_disease.trim() === d.trim())
      .sort((a: any, b: any) => a.visit_date.localeCompare(b.visit_date))
    if (hit.length) {
      form.value.visit_type = '复诊'
      // 自动关联该病种最近一次初诊（若用户未手动指定/未通过「＋复诊」预设则预填）
      if (form.value.parent_visit_id == null) {
        form.value.parent_visit_id = findRootId(hit[hit.length - 1])
      }
      lastVisitHint.value = `该病种曾于 ${hit[hit.length - 1].visit_date} 就诊，本次已默认标记为复诊（可手动改为初诊）`
      lastVisit.value = hit[hit.length - 1]
      loadLastPrescription(lastVisit.value.id)
    } else {
      form.value.visit_type = '初诊'
      lastVisit.value = null
      lastVisitHint.value = currentVisitId.value == null ? '该病种尚未在本院就诊，默认为初诊' : ''
    }
  }
)

// 预取上次就诊处方作参考
async function loadLastPrescription(vid: number) {
  try {
    const rxs = (await api.get(`/prescriptions?visit_id=${vid}`)) as any[]
    if (lastVisit.value) lastVisit.value = { ...lastVisit.value, prescriptions: rxs || [] }
  } catch {}
}

// 复诊时把上次同病种就诊的四诊/证型/治法带入为底稿（只填充当前为空字段，避免覆盖本次新内容）
function applyLastVisitDraft() {
  const lv = lastVisit.value
  if (!lv) return
  const setIfEmpty = (key: string, val: any) => {
    if (val && !form.value[key]) form.value[key] = val
  }
  setIfEmpty('present_illness', lv.present_illness)
  setIfEmpty('observation', lv.observation)
  setIfEmpty('auscultation', lv.auscultation)
  setIfEmpty('inquiry', lv.inquiry)
  setIfEmpty('palpation', lv.palpation)
  setIfEmpty('tongue_body', lv.tongue_body)
  setIfEmpty('tongue_coat', lv.tongue_coat)
  if (lv.pulse) {
    const arr = typeof lv.pulse === 'string' ? lv.pulse.split('、').filter(Boolean) : [...(lv.pulse || [])]
    if (!form.value.pulse.length) form.value.pulse = arr
  }
  setIfEmpty('tcm_syndrome', lv.tcm_syndrome)
  setIfEmpty('treatment_method', lv.treatment_method)
  ElMessage.info('已带入上次四诊/证型/治法作参考，请核对并按本次变化调整')
}

// 图片上传
const visitFileInputRef = ref<HTMLInputElement>()
const visitCameraInputRef = ref<HTMLInputElement>()
// 化验单最多上传张数
const MAX_LAB = 6
const visitImageTarget = ref<'tongue' | 'face' | 'lab'>('tongue')
const visitImages = ref<{ tongue: string; face: string; lab: string[] }>({ tongue: '', face: '', lab: [] })

// 手机端检测：true 时「拍摄」走系统相机，否则走网页摄像头弹窗
const isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)

// mode: 'camera' 拍照；'album' 从相册/文件选择。桌面端拍照用网页摄像头弹窗，手机端走系统相机
function triggerVisitImage(target: 'tongue' | 'face' | 'lab', mode: 'camera' | 'album' = 'album') {
  visitImageTarget.value = target
  if (mode === 'camera') {
    if (isMobile) {
      visitCameraInputRef.value?.click()
    } else {
      openCamera(target)
    }
  } else {
    visitFileInputRef.value?.click()
  }
}

async function uploadImageFile(file: File) {
  let f = file
  try {
    f = await compressImageFile(file)
  } catch { /* 压缩失败则使用原图，后续会校验大小 */ }
  if (f.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片不能超过5MB')
    return
  }
  if (visitImageTarget.value === 'lab' && visitImages.value.lab.length >= MAX_LAB) {
    ElMessage.warning(`化验单最多上传 ${MAX_LAB} 张`)
    return
  }
  try {
    const formData = new FormData()
    formData.append('file', f)
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
}

async function onVisitImageSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  await uploadImageFile(file)
  input.value = ''
}

// ---- 桌面端网页摄像头拍摄 ----
const showCamera = ref(false)
const cameraVideoRef = ref<HTMLVideoElement>()
const cameraCanvasRef = ref<HTMLCanvasElement>()
let cameraStream: MediaStream | null = null
let cameraStarted = false

async function startCamera() {
  if (cameraStarted) return
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
    cameraStarted = true
    const video = cameraVideoRef.value
    if (video) {
      video.srcObject = cameraStream
      await video.play().catch(() => {})
    }
  } catch (e: any) {
    cameraStarted = false
    ElMessage.error('无法访问摄像头：' + (e?.message || '请检查权限设置'))
  }
}

function stopCamera() {
  cameraStream?.getTracks().forEach(t => t.stop())
  cameraStream = null
  cameraStarted = false
  if (cameraVideoRef.value) cameraVideoRef.value.srcObject = null
  showCamera.value = false
}

function openCamera(target: 'tongue' | 'face' | 'lab') {
  visitImageTarget.value = target
  showCamera.value = true
  cameraStarted = false
  nextTick(startCamera)
}

function capturePhoto() {
  const video = cameraVideoRef.value
  const canvas = cameraCanvasRef.value
  if (!video || !canvas || !video.videoWidth) {
    ElMessage.warning('摄像头尚未就绪，请稍候')
    return
  }
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height)
  canvas.toBlob(blob => {
    if (!blob) return
    uploadImageFile(new File([blob], 'camera.jpg', { type: 'image/jpeg' }))
    stopCamera()
  }, 'image/jpeg', 0.9)
}

// 由已保存的问诊十问记录生成可读摘要（AI 辨证用于兜底展示）
function buildIqSummaryFromRecord(rec: any): string {
  if (!rec || !rec.answers) return ''
  const lines: string[] = []
  for (const q of TEN_QUESTIONS) {
    let text = ''
    const picked = rec.answers[q.key]
    if (picked && picked !== 'custom') {
      const o = q.options.find(opt => opt.key === picked)
      text = o ? o.label : picked
    }
    const note = (rec.notes?.[q.key] || '').trim()
    if (note) text = text ? text + '；' + note : (picked === 'custom' ? '（自填）' : '')
    if (!text && picked === 'custom') text = '（自填）'
    lines.push(text ? `${q.title}：${text}` : `${q.title}：未回答`)
  }
  return lines.join('\n')
}

async function aiAssist() {
  if (!form.value.chief_complaint) {
    ElMessage.warning('请先填写主诉')
    return
  }
  // 组装当前录入的信息与输入指纹
  let aspects = tenAspectsRef.value?.getAspectSummary() || ''
  let tenAns = tenAspectsRef.value?.getAspectAnswers?.()
  // 面板十问为空时，从已保存的问诊十问记录兜底，避免 AI 辨证/依据里十问全是"未回答"
  if (!aspects && initialIq.value) {
    aspects = buildIqSummaryFromRecord(initialIq.value)
    tenAns = initialIq.value.answers
      ? { answers: initialIq.value.answers, notes: initialIq.value.notes || {} }
      : undefined
  }

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
  if (form.value.visit_type === '复诊' && !form.value.parent_visit_id) {
    ElMessage.warning('请选择本次复诊关联的初诊')
    return
  }
  submitting.value = true
  try {
    const payload = {
      ...form.value,
      pulse: form.value.pulse.join('、'),
      tongue_image: visitImages.value.tongue || null,
      face_image: visitImages.value.face || null,
      lab_report_images: visitImages.value.lab.length ? visitImages.value.lab : null,
    }
    // 已有就诊则更新（完善/补充病历），否则新建，避免重复建就诊
    if (currentVisitId.value != null) {
      const res = await api.put(`/patients/${patientId}/visits/${currentVisitId.value}`, payload, { silent: true }) as any
      ElMessage.success('就诊记录已更新')
      if (props.embedded) emit('saved', res)
      return res
    }
    const res = await api.post(`/patients/${patientId}/visits`, payload, { silent: true }) as any
    currentVisitId.value = res.id
    ElMessage.success(props.embedded ? '就诊记录已保存' : '就诊记录已保存，可在右侧完成本次问诊十问，或下方去开药')
    if (props.embedded) emit('saved', res)
    return res
  } catch (e: any) {
    ElMessage.error('保存失败：' + (e?.response?.data?.detail || e?.message || ''))
  } finally {
    submitting.value = false
  }
}

function onCancel() {
  if (props.embedded) emit('cancel')
  else router.back()
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
    if (!form.value.visit_type) form.value.visit_type = '初诊'
    form.value.pulse = (res.pulse || '').split('、').filter(Boolean)
    form.value.pulse_term_ids = res.pulse_term_ids || []
    visitImages.value.tongue = res.tongue_image || ''
    visitImages.value.face = res.face_image || ''
    visitImages.value.lab = res.lab_report_images || []
  } catch {
    ElMessage.error('加载就诊记录失败')
  }
}
</script>

<style scoped>
.visit-type-hint {
  font-size: 12px;
  color: #d48806;
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 6px;
  padding: 6px 10px;
  margin-bottom: 10px;
  line-height: 1.5;
}
.vit-last-rx { margin-left: 8px; color: #8B4513; }
.form-tip { font-size: 12px; color: #999; line-height: 1.5; margin-top: 4px; }
.camera-box video {
  width: 100%;
  border-radius: 8px;
  background: #000;
  aspect-ratio: 4 / 3;
  object-fit: cover;
}
.el-divider { margin: 12px 0 16px; }

.left-col { display: flex; flex-direction: column; gap: 18px; }
.right-col { display: flex; flex-direction: column; gap: 18px; }
.right-col-equal { margin-top: 0; }
.other-files-card { margin-top: 0; }

/* 四张就诊卡片统一美化 */
.tcm-visit-card {
  --el-card-padding: 18px;
  border-radius: 12px;
  border: 1px solid #efe5d8;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(120, 80, 40, 0.06);

  :deep(.el-card__header) {
    padding: 13px 18px;
    background: linear-gradient(90deg, #fbf4ea 0%, #f4e7d3 100%);
    border-bottom: 1px solid #efe2d0;
    font-weight: 700;
    font-size: 15px;
    color: #6b4423;
    letter-spacing: 0.5px;
  }
  :deep(.el-card__body) {
    padding: var(--el-card-padding);
  }
}
/* 头部有操作按钮时与标题对齐保持美观 */
.tcm-visit-card.is-hover-shadow:hover {
  box-shadow: 0 4px 18px rgba(120, 80, 40, 0.12);
}

.img-upload-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  position: relative;

  .visit-thumb-wrap {
    position: relative;
    display: inline-block;
    line-height: 0;
  }

  .visit-thumb {
    width: 40px;
    height: 40px;
    border-radius: 4px;
    border: 1px solid #e8e0d8;
  }

  .pinch-thumb {
    width: 40px;
    height: 40px;
    border-radius: 4px;
    border: 1px solid #e8e0d8;
    overflow: hidden;
  }

  .remove-visit-img {
    position: absolute;
    top: -4px;
    right: -4px;
    left: auto;
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
    overflow: hidden;
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
  :deep(.el-card__header > div) {
    flex-wrap: wrap;
    row-gap: 6px;
  }
  :deep(.el-card__header > div > span) {
    white-space: nowrap;
  }
  .img-upload-row {
    flex-wrap: wrap;
  }
  /* 底部操作按钮全宽 */
  .visit-saved-hint .el-button {
    margin-top: 8px;
  }
  :deep(.lab-preview) {
    align-items: flex-start;
  }
}
.tag-reminders { display: flex; flex-direction: column; gap: 6px; }
.tag-remind-item { display: flex; align-items: flex-start; gap: 8px; }
.tag-remind-item .tag-remind-desc { font-size: 13px; color: #6b4f2a; line-height: 1.5; }
</style>