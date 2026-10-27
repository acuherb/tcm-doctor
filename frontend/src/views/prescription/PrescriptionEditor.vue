<template>
  <div class="prescription-editor">
    <!-- 左侧：处方表单 -->
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>📝 {{ prescriptionId ? '编辑处方' : '开具处方' }}</span>
          <div style="display:flex;gap:8px;">
            <el-button v-if="editable" size="small" @click="loadFromFormula">从经典方导入</el-button>
            <el-button v-if="editable" type="primary" size="small" @click="submitPrescription" :loading="submitting">
              {{ prescriptionId ? '保存修改' : '提交处方' }}
            </el-button>
          </div>
        </div>
      </template>

      <el-form :model="form" label-width="80px">
        <!-- 公共信息区 -->
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="患者" required>
              <el-select v-model="form.patient_id" filterable remote reserve-keyword
                placeholder="输入姓名或电话搜索" style="width:100%"
                :remote-method="searchPatients" :loading="patientsLoading"
                @change="onPatientChange">
                <el-option v-for="p in patients" :key="p.id" :label="p.name" :value="p.id">
                  <span>{{ p.name }}</span>
                  <span style="color:#999;font-size:12px;margin-left:8px;">{{ p.gender }} {{ p.phone }}</span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="就诊ID">
              <el-input-number v-model="form.visit_id" :min="1" style="width:100%" placeholder="关联就诊记录" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 中药方区块 -->
        <el-divider content-position="left">🌿 中药方</el-divider>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="方名">
              <el-input v-model="form.formula_name" placeholder="如：小柴胡汤加减" />
            </el-form-item>
          </el-col>
          <el-col :span="5">
            <el-form-item label="煎法">
              <el-select v-model="form.preparation_method" style="width:100%">
                <el-option v-for="m in preparationMethods" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="5">
            <el-form-item label="剂数">
              <el-input-number v-model="form.doses" :min="1" :max="30" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="服法">
              <el-input v-model="form.administration" placeholder="如：日一剂，分早晚温服" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 药味列表 -->
        <el-divider content-position="left">药味明细</el-divider>

        <div class="herb-items">
          <div v-for="(item, idx) in form.items" :key="idx" class="herb-item-row">
            <div class="herb-item-fields">
              <HerbSelector
                v-model="item.herb_id"
                :display-name="item.herb_name"
                :exclude-ids="getExcludeIds(idx)"
                @select="(h: any) => onHerbSelect(idx, h)"
                width="180px"
              />
              <el-input-number v-model="item.dose" :min="0.5" :max="200" :precision="1"
                placeholder="剂量" style="width:120px;" />
              <span style="font-size:13px;color:#999;">g</span>
              <el-select v-model="item.special_method" placeholder="煎法" clearable style="width:100px;">
                <el-option v-for="m in specialMethods" :key="m" :label="m" :value="m" />
              </el-select>
              <el-checkbox v-model="item.is_king_herb" label="君药" />
              <el-input v-model="item.note" placeholder="备注" style="width:120px;" size="small" />
            </div>
            <div class="herb-item-actions">
              <el-button v-if="editable" link type="danger" @click="removeItem(idx)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <!-- 实时配伍警告 -->
            <div v-if="item._warnings?.length" class="item-warnings">
              <el-tag v-for="w in item._warnings" :key="w" type="danger" size="small" style="margin:2px;">
                {{ w }}
              </el-tag>
            </div>
          </div>

          <div class="add-herb-row">
            <el-button v-if="editable" type="primary" plain @click="addItem" style="width:100%;">
              <el-icon><Plus /></el-icon> 添加药味
            </el-button>
          </div>
        </div>

        <!-- 针灸方区块 -->
        <el-divider content-position="left">🪡 针灸方</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="方案名">
              <el-input v-model="form.acupoint_formula_name" placeholder="如：安神定志针方（为后续针灸库预留）" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="针法">
              <el-input v-model="form.acupoint_technique" placeholder="如：毫针补法 / 温针灸" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="操作频次">
              <el-select v-model="form.treatment_frequency" placeholder="选择频次" clearable filterable allow-create style="width:100%">
                <el-option v-for="f in treatmentFrequencies" :key="f" :label="f" :value="f" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="疗程天数">
              <el-input-number v-model="form.treatment_days" :min="1" :max="60" style="width:100%" />
              <span style="font-size:13px;color:#999;margin-left:6px;">天</span>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 配穴明细 -->
        <el-divider content-position="left">配穴明细</el-divider>
        <div class="herb-items" v-if="form.acupoints.length">
          <div v-for="(acp, idx) in form.acupoints" :key="idx" class="herb-item-row">
            <div class="herb-item-fields">
              <el-select
                v-model="acp.acupoint_name"
                placeholder="搜索或输入穴位"
                filterable
                allow-create
                default-first-option
                :teleported="false"
                style="width:200px;"
                @change="(v: any) => onAcupointChange(idx, v)"
              >
                <el-option
                  v-for="a in filteredAcupoints"
                  :key="a.id"
                  :label="`${a.name}${a.point_type ? '（' + a.point_type + '）' : ''} — ${a.meridian || '奇穴'}`"
                  :value="a.name"
                >
                  <div class="acp-option">
                    <div class="acp-option-name">{{ a.name }} <span class="acp-option-type">{{ a.point_type || '' }}</span></div>
                    <div class="acp-option-sub">{{ a.meridian || '奇穴' }}<span v-if="a.location"> · {{ a.location }}</span></div>
                  </div>
                </el-option>
              </el-select>
              <el-select v-model="acp.technique" placeholder="针法" clearable style="width:116px;">
                <el-option v-for="t in techniques" :key="t" :label="t" :value="t" />
              </el-select>
              <el-input v-model="acp.retention" placeholder="分钟" style="width:80px;" title="留针时间(分钟)">
                <template #prepend>留针</template>
              </el-input>
              <el-input-number v-model="acp.sequence" :min="1" :max="30" placeholder="顺序" style="width:80px;" />
              <el-input v-model="acp.note" placeholder="备注" style="width:120px;" size="small" />
            </div>
            <div class="herb-item-actions">
              <el-button v-if="editable" link type="danger" @click="removeAcupoint(idx)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
        <div class="add-herb-row acp-filter-row" v-if="meridians.length">
          <el-select v-model="meridianFilter" placeholder="按归经筛选，快速定位" clearable filterable style="width:220px;">
            <el-option v-for="m in meridians" :key="m" :label="m" :value="m" />
          </el-select>
          <span class="acp-count" v-if="filteredAcupoints.length">匹配合穴 {{ filteredAcupoints.length }} 个</span>
        </div>
        <div class="add-herb-row">
          <el-button v-if="editable" type="primary" plain style="width:100%;" @click="addAcupoint">
            <el-icon><Plus /></el-icon> 添加配穴
          </el-button>
        </div>

        <el-form-item label="医嘱" style="margin-top:16px;">
          <el-input v-model="form.doctor_notes" type="textarea" :rows="2" placeholder="饮食禁忌、调护建议等" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 右侧：配伍安全检查结果 -->
    <el-card shadow="hover" style="margin-top:16px;">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>🔍 安全检查</span>
          <el-button size="small" @click="runSafetyCheck">重新检查</el-button>
        </div>
      </template>

      <!-- 配伍禁忌 -->
      <div v-if="incompatibilityWarnings.length > 0" class="safety-section">
        <el-alert type="error" :closable="false" show-icon title="配伍禁忌" style="margin-bottom:8px;" />
        <div v-for="w in incompatibilityWarnings" :key="w.herb_a + w.herb_b" class="safety-item danger">
          <el-tag type="danger" size="small">{{ w.rule_type }}</el-tag>
          <span>{{ w.herb_a }} + {{ w.herb_b }}</span>
          <span v-if="w.description" style="color:#999;font-size:12px;">{{ w.description }}</span>
        </div>
      </div>

      <!-- 剂量超限 -->
      <div v-if="dosageWarnings.length > 0" class="safety-section">
        <el-alert type="warning" :closable="false" show-icon title="剂量超限" style="margin-bottom:8px;" />
        <div v-for="w in dosageWarnings" :key="w" class="safety-item warning">
          <el-tag type="warning" size="small">超量</el-tag>
          <span>{{ w }}</span>
        </div>
      </div>

      <!-- 孕妇禁忌 -->
      <div v-if="pregnancyWarnings.length > 0" class="safety-section">
        <el-alert type="warning" :closable="false" show-icon title="孕妇禁忌" style="margin-bottom:8px;" />
        <div v-for="w in pregnancyWarnings" :key="w" class="safety-item warning">
          <el-tag type="warning" size="small">孕妇慎用</el-tag>
          <span>{{ w }}</span>
        </div>
      </div>

      <!-- 安全通过 -->
      <div v-if="incompatibilityWarnings.length === 0 && dosageWarnings.length === 0 && pregnancyWarnings.length === 0 && form.items.length > 0"
        class="safety-section">
        <el-alert type="success" :closable="false" show-icon title="安全检查通过" description="未检测到配伍禁忌、剂量超限或孕妇禁忌" />
      </div>

      <div v-if="form.items.length === 0 && hasAcupointContent" class="safety-section">
        <el-alert type="info" :closable="false" show-icon title="纯针灸方" description="已添加配穴，无需配伍安全检查" />
      </div>

      <el-empty v-if="form.items.length === 0 && !hasAcupointContent"
        :description="'请在左侧添加药味或配穴'" :image-size="60" />
    </el-card>

    <!-- 经典方导入对话框 -->
    <el-dialog v-model="formulaDialogVisible" title="📖 从经典方导入" width="650px" destroy-on-close>
      <el-input v-model="formulaSearch" placeholder="搜索方名" clearable style="margin-bottom:12px;" />
      <el-table :data="filteredFormulas" stripe size="small" @row-click="selectFormula"
        highlight-current-row style="cursor:pointer;">
        <el-table-column prop="name" label="方名" width="120" />
        <el-table-column prop="source" label="出处" width="100" />
        <el-table-column prop="efficacy" label="功效" show-overflow-tooltip />
        <el-table-column label="组成" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.composition?.herbs">
              {{ row.composition.herbs.map((h: any) => `${h.herb}${h.dose}g`).join('、') }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 配伍禁忌弹窗 -->
    <IncompatibilityAlert
      v-model="showIncompatibilityDialog"
      :warnings="incompatibilityWarnings"
      :pregnancy-warnings="pregnancyWarnings"
      :dosage-warnings="dosageWarnings"
      :allow-force="incompatibilityWarnings.length === 0"
      @cancel="showIncompatibilityDialog = false"
      @force-confirm="forceSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/utils/api'
import HerbSelector from '@/components/HerbSelector.vue'
import IncompatibilityAlert from '@/components/IncompatibilityAlert.vue'
import { useAuthStore } from '@/store/auth'

const route = useRoute()
const router = useRouter()

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)

// 是否已添加配穴（用于支持纯针灸处方）
const hasAcupointContent = computed(() =>
  form.value.acupoints.some((a: any) => a.acupoint_name)
)

const submitting = ref(false)
const patients = ref<any[]>([])
const patientsLoading = ref(false)
const classicFormulas = ref<any[]>([])
const formulaDialogVisible = ref(false)
const formulaSearch = ref('')
const showIncompatibilityDialog = ref(false)

const incompatibilityWarnings = ref<any[]>([])
const dosageWarnings = ref<string[]>([])
const pregnancyWarnings = ref<string[]>([])

const preparationMethods = ['水煎服', '水煎服代煎', '研末冲服', '丸剂', '散剂', '膏方']
const specialMethods = ['先煎', '后下', '包煎', '烊化', '冲服', '另煎']
const techniques = ['毫针泻法', '毫针补法', '平补平泻', '温针灸', '艾灸', '拔罐', '放血', '电针']
const treatmentFrequencies = ['每日', '隔日', '每周', '隔周', '每三日']
const acupointOptions = ref<any[]>([])
const meridianFilter = ref<string>('')
const meridians = computed(() => {
  const set = new Set<string>()
  acupointOptions.value.forEach((a: any) => a.meridian && set.add(a.meridian))
  return Array.from(set).sort()
})
const filteredAcupoints = computed(() => {
  if (!meridianFilter.value) return acupointOptions.value
  return acupointOptions.value.filter((a: any) => a.meridian === meridianFilter.value)
})

const form = ref({
  patient_id: null as number | null,
  visit_id: 1,
  formula_name: '',
  is_classic: false,
  classic_formula_id: null as number | null,
  preparation_method: '水煎服',
  administration: '日一剂，分早晚温服',
  doses: 7,
  doctor_notes: '',
  prescription_type: '药方',
  // 针灸方顶层字段（可与药方共存于同一张处方）
  acupoint_formula_name: '',
  acupoint_technique: '',
  treatment_frequency: '',
  treatment_days: null as number | null,
  items: [] as Array<{
    herb_id: number | null
    herb_name: string
    dose: number
    special_method: string | null
    is_king_herb: boolean
    note: string
    _warnings?: string[]
  }>,
  acupoints: [] as Array<{
    acupoint_id: number | null
    acupoint_name: string
    technique: string | null
    retention: string | null
    sequence: number
    note: string
  }>,
})

const filteredFormulas = computed(() => {
  if (!formulaSearch.value) return classicFormulas.value
  const q = formulaSearch.value.toLowerCase()
  return classicFormulas.value.filter((f: any) =>
    f.name.toLowerCase().includes(q) || (f.efficacy || '').toLowerCase().includes(q)
  )
})

function getExcludeIds(currentIdx: number) {
  return form.value.items
    .filter((_: any, i: number) => i !== currentIdx)
    .map((item: any) => item.herb_id)
    .filter(Boolean) as number[]
}

function addItem() {
  form.value.items.push({
    herb_id: null,
    herb_name: '',
    dose: 10,
    special_method: null,
    is_king_herb: false,
    note: '',
    _warnings: [],
  })
}

function removeItem(idx: number) {
  form.value.items.splice(idx, 1)
  runSafetyCheck()
}

function addAcupoint() {
  form.value.acupoints.push({
    acupoint_id: null,
    acupoint_name: '',
    technique: null,
    retention: '',
    sequence: form.value.acupoints.length + 1,
    note: '',
  })
}

function removeAcupoint(idx: number) {
  form.value.acupoints.splice(idx, 1)
}

function onAcupointChange(idx: number, name: string) {
  const match = acupointOptions.value.find((a: any) => a.name === name)
  form.value.acupoints[idx].acupoint_id = match?.id ?? null
}

function onHerbSelect(idx: number, herb: any) {
  if (herb) {
    form.value.items[idx].herb_name = herb.name
    // 自动填充建议剂量（取中间值）
    const mid = Math.round(((herb.dosage_min || 3) + (herb.dosage_max || 10)) / 2)
    if (!form.value.items[idx].dose || form.value.items[idx].dose === 10) {
      form.value.items[idx].dose = mid
    }
  }
  runSafetyCheck()
}

function onPatientChange(patientId: number) {
  const patient = patients.value.find((p: any) => p.id === patientId)
  if (patient?.pregnancy_contraindicated || patient?.gender === '女') {
    // 标记可能需要孕妇禁忌检查
  }
}

// ── 安全检查 ──
async function runSafetyCheck() {
  const herbIds = form.value.items.map(i => i.herb_id).filter(Boolean) as number[]
  if (herbIds.length < 1) {
    incompatibilityWarnings.value = []
    dosageWarnings.value = []
    pregnancyWarnings.value = []
    return
  }

  // 配伍禁忌检查
  if (herbIds.length >= 2) {
    try {
      const res = await api.post('/herbs/incompatibility-check', { herb_ids: herbIds }) as any
      incompatibilityWarnings.value = res.warnings || []
    } catch {
      incompatibilityWarnings.value = []
    }
  } else {
    incompatibilityWarnings.value = []
  }

  // 剂量和孕妇禁忌检查（应用层）
  const warnings: string[] = []
  const pregWarnings: string[] = []
  for (const item of form.value.items) {
    if (!item.herb_id) continue
    // 剂量检查通过 herb 数据
    const herb = await getHerbCache(item.herb_id)
    if (herb) {
      if (herb.dosage_max && item.dose > Number(herb.dosage_max)) {
        warnings.push(`${herb.name}: 剂量${item.dose}g 超过最大剂量${herb.dosage_max}g`)
      }
      if (herb.pregnancy_contraindicated) {
        pregWarnings.push(`${herb.name}: 孕妇禁用/慎用`)
      }
    }
  }
  dosageWarnings.value = warnings
  pregnancyWarnings.value = pregWarnings

  // 标记每项的警告
  form.value.items.forEach(item => {
    const itemWarnings: string[] = []
    for (const w of incompatibilityWarnings.value) {
      if (w.herb_a === item.herb_name || w.herb_b === item.herb_name) {
        itemWarnings.push(`${w.rule_type}: ${w.herb_a}+${w.herb_b}`)
      }
    }
    for (const dw of dosageWarnings.value) {
      if (dw.startsWith(item.herb_name)) itemWarnings.push(dw)
    }
    item._warnings = itemWarnings
  })
}

// 药材缓存
const herbCache = new Map<number, any>()
async function getHerbCache(id: number) {
  if (herbCache.has(id)) return herbCache.get(id)
  try {
    const herb = await api.get(`/herbs/${id}`) as any
    herbCache.set(id, herb)
    return herb
  } catch { return null }
}

// ── 经典方导入 ──
function loadFromFormula() {
  formulaDialogVisible.value = true
}

async function selectFormula(formula: any) {
  form.value.formula_name = formula.name
  form.value.is_classic = true
  form.value.classic_formula_id = formula.id
  form.value.items = []

  // 确保药材库已加载，便于按药名（含异名）匹配 herb_id
  if (!herbCacheList.value.length) {
    await loadHerbList()
  }

  const herbs = Array.isArray(formula.composition) ? formula.composition : formula.composition?.herbs || []
  for (const h of herbs) {
    const name = (h.herb || '').trim()
    // 先按正名精确匹配，再按异名匹配，最后按包含关系匹配（兼容炮制名，如「炙甘草」→「甘草」）
    let matchedHerb = herbCacheList.value.find((herb: any) => herb.name === name)
    if (!matchedHerb) {
      matchedHerb = herbCacheList.value.find((herb: any) =>
        (herb.aliases || []).some((a: string) => a === name) ||
        (herb.name && (herb.name.includes(name) || name.includes(herb.name)))
      )
    }
    form.value.items.push({
      herb_id: matchedHerb?.id || null,
      herb_name: h.herb,
      dose: h.dose || 10,
      special_method: h.special_method || null,
      is_king_herb: h.is_king_herb || false,
      note: h.note || '',
      _warnings: [],
    })
  }

  if (formula.usage) {
    form.value.administration = formula.usage
  }

  formulaDialogVisible.value = false
  ElMessage.success(`已导入「${formula.name}」`)
  runSafetyCheck()
}

const herbCacheList = ref<any[]>([])

// ── 提交处方 ──
async function submitPrescription() {
  if (!form.value.patient_id) { ElMessage.warning('请选择患者'); return }
  const hasHerb = form.value.items.length > 0
  const hasAcupoint = form.value.acupoints.some(a => a.acupoint_name)
  if (!hasHerb && !hasAcupoint) { ElMessage.warning('请至少添加一味药或一个配穴'); return }
  if (hasHerb && form.value.items.some(i => !i.herb_id)) { ElMessage.warning('有药味未选择'); return }

  // 仅药味方需检查配伍禁忌；纯针灸方无需安全检查
  if (hasHerb && incompatibilityWarnings.value.length > 0) {
    showIncompatibilityDialog.value = true
    return
  }

  await doSubmit()
}

async function forceSubmit() {
  await doSubmit()
}

async function doSubmit() {
  submitting.value = true
  try {
    const hasHerb = form.value.items.length > 0
    const hasAcupoint = form.value.acupoints.some(a => a.acupoint_name)
    // 一张处方可同时含药方与针灸方：自动判定类型
    let ptype = '药方'
    if (hasHerb && hasAcupoint) ptype = '混合'
    else if (hasAcupoint) ptype = '针方'

    const payload = {
      ...form.value,
      prescription_type: ptype,
      items: form.value.items.map(i => ({
        herb_id: i.herb_id,
        herb_name: i.herb_name,
        dose: i.dose,
        special_method: i.special_method,
        is_king_herb: i.is_king_herb,
        note: i.note,
      })),
      acupoints: form.value.acupoints
        .filter((a: any) => a.acupoint_name)
        .map((a: any) => ({
          acupoint_id: a.acupoint_id,
          acupoint_name: a.acupoint_name,
          technique: a.technique,
          retention: a.retention,
          sequence: a.sequence,
          note: a.note,
        })),
    }
    if (prescriptionId.value) {
      await api.put(`/prescriptions/${prescriptionId.value}`, payload)
      ElMessage.success('处方已更新')
    } else {
      await api.post('/prescriptions', payload)
      ElMessage.success('处方已提交')
    }
    router.push('/prescriptions')
  } catch {} finally {
    submitting.value = false
  }
}

// 编辑态：从 PrescriptionResponse 回显并走 PUT
const prescriptionId = ref<number | null>(null)
function applyPrescription(p: any) {
  const f = form.value
  f.patient_id = p.patient_id
  f.visit_id = p.visit_id
  f.formula_name = p.formula_name || ''
  f.is_classic = p.is_classic || false
  f.classic_formula_id = p.classic_formula_id ?? null
  f.preparation_method = p.preparation_method || '水煎服'
  f.administration = p.administration || ''
  f.doses = p.doses || 7
  f.doctor_notes = p.doctor_notes || ''
  f.acupoint_formula_name = p.acupoint_formula_name || ''
  f.acupoint_technique = p.acupoint_technique || ''
  f.treatment_frequency = p.treatment_frequency || ''
  f.treatment_days = p.treatment_days ?? null
  f.items = (p.items || []).map((i: any) => ({
    herb_id: i.herb_id, herb_name: i.herb_name, dose: i.dose,
    special_method: i.special_method, is_king_herb: i.is_king_herb, note: i.note, _warnings: [],
  }))
  f.acupoints = (p.acupoints || []).map((a: any) => ({
    acupoint_id: a.acupoint_id, acupoint_name: a.acupoint_name,
    technique: a.technique, retention: a.retention, sequence: a.sequence, note: a.note,
  }))
}

// ── 数据加载 ──
async function loadPatients() {
  patientsLoading.value = true
  try {
    const res = await api.get('/patients', { params: { page_size: 100 } }) as any
    patients.value = res.items || res || []
  } catch {} finally {
    patientsLoading.value = false
  }
}

async function searchPatients(query: string) {
  if (!query) { loadPatients(); return }
  patientsLoading.value = true
  try {
    const res = await api.get('/patients', { params: { search: query, page_size: 50 } }) as any
    patients.value = res.items || res || []
  } catch {} finally {
    patientsLoading.value = false
  }
}

async function loadFormulas() {
  try {
    classicFormulas.value = (await api.get('/prescriptions/classic-formulas') as any) || []
  } catch {}
}

async function loadHerbList() {
  try {
    herbCacheList.value = (await api.get('/herbs') as any) || []
    herbCacheList.value.forEach((h: any) => herbCache.set(h.id, h))
  } catch {}
}

async function loadAcupoints() {
  try {
    acupointOptions.value = (await api.get('/acupoints') as any) || []
  } catch {}
}

// 从针灸方库「引入到处方编辑器」：预填针灸方 4 字段与配穴
async function applyAcupointFormulaById(id: number) {
  try {
    const f = await api.get(`/acupoint-formulas/${id}`) as any
    form.value.acupoint_formula_name = f.name
    if (f.technique) form.value.acupoint_technique = f.technique
    if (f.treatment_frequency) form.value.treatment_frequency = f.treatment_frequency
    if (f.treatment_days) form.value.treatment_days = f.treatment_days
    const acus = (f.composition?.acupoints || []).map((a: any, i: number) => ({
      acupoint_id: null,
      acupoint_name: a.acupoint_name,
      technique: a.technique || null,
      retention: a.retention || null,
      sequence: a.sequence || i + 1,
      note: a.note || '',
    }))
    if (acus.length) form.value.acupoints = acus
    ElMessage.success(`已引入针灸方「${f.name}」`)
  } catch {}
}

onMounted(async () => {
  loadPatients()
  loadFormulas()
  loadHerbList()
  loadAcupoints()

  // 编辑态：从详情接口回显整张处方（含 4 个针灸方字段）
  const q = route.query
  if (q.id) {
    prescriptionId.value = Number(q.id)
    try {
      const p = await api.get(`/prescriptions/${prescriptionId.value}`) as any
      applyPrescription(p)
    } catch {}
    // 编辑态下仍允许叠加引入针灸方
    if (q.acupoint_formula_id) await applyAcupointFormulaById(Number(q.acupoint_formula_id))
    return
  }

  // 从针灸方库引入：预填针灸方区块
  if (q.acupoint_formula_id) {
    await applyAcupointFormulaById(Number(q.acupoint_formula_id))
    return
  }

  // 从辨证页带参数进入：自动预填患者并导入关联经方
  if (q.patient_id) form.value.patient_id = Number(q.patient_id)
  if (q.visit_id) form.value.visit_id = Number(q.visit_id)
  if (q.formula_id) {
    const fid = Number(q.formula_id)
    if (classicFormulas.value.length) {
      const f = classicFormulas.value.find((x: any) => x.id === fid)
      if (f) selectFormula(f)
    } else {
      try {
        const f = await api.get(`/prescriptions/classic-formulas/${fid}`) as any
        if (f) selectFormula(f)
      } catch {}
    }
  }
})
</script>

<style scoped lang="scss">
.prescription-editor {
  .herb-items {
    .herb-item-row {
      padding: 8px 0;
      border-bottom: 1px dashed #e8e0d8;

      .herb-item-fields {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }

      .herb-item-actions {
        display: inline-block;
        margin-left: 8px;
      }

      .item-warnings {
        margin-top: 4px;
        padding-left: 4px;
      }
    }

    .add-herb-row {
      margin-top: 12px;
    }

    .acp-filter-row {
      display: flex;
      align-items: center;
      gap: 12px;

      .acp-count {
        color: #909399;
        font-size: 12px;
      }
    }
  }

  .acp-option {
    line-height: 1.25;
    padding: 2px 0;

    .acp-option-name {
      font-weight: 600;

      .acp-option-type {
        font-weight: 400;
        color: #a66;
        font-size: 12px;
      }
    }

    .acp-option-sub {
      color: #909399;
      font-size: 12px;
    }
  }

  .safety-section {
    margin-bottom: 16px;

    .safety-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      margin-bottom: 4px;
      border-radius: 4px;

      &.danger { background: #fef0f0; }
      &.warning { background: #fdf6ec; }
    }
  }
}
</style>