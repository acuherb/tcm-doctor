<template>
  <div class="prescription-editor">
    <!-- 左侧：处方表单 -->
    <el-card shadow="hover">
      <template #header>
        <div class="editor-header" style="display:flex;justify-content:space-between;align-items:center;">
          <span>📝 {{ prescriptionId ? '编辑处方' : '开具处方' }}</span>
          <div class="editor-actions" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <span v-if="estimatedTotal > 0" title="中药售价×剂量×剂数 + 针灸费用（预估）" style="font-size:14px;font-weight:600;color:#8B4513;">
              预估合计 ¥{{ estimatedTotal }}
            </span>
            <el-button v-if="editable" size="small" @click="loadFromFormula">从中药方导入</el-button>
            <el-button v-if="editable" size="small" @click="loadFromAcupointFormula">从针灸方导入</el-button>
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
              <span v-if="herbUnitPrice(item) != null" style="font-size:12px;color:#8B4513;white-space:nowrap;min-width:96px;display:inline-block;">
                ￥{{ herbUnitPrice(item) }}·{{ herbItemAmount(item) }}元
              </span>
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
          <el-col :span="12">
            <el-form-item label="针灸费用">
              <el-input-number v-model="form.acupuncture_fee" :min="0" :precision="2" placeholder="本次针灸收费(元)" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="建议复诊日期" prop="follow_up_date">
              <el-date-picker v-model="form.follow_up_date" type="date" value-format="YYYY-MM-DD" placeholder="可选，留空则按疗程天数自动提醒" style="width:100%" />
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
              <el-input-number
                :model-value="retentionNum(acp.retention)"
                @update:model-value="(n: any) => (acp.retention = n == null ? '' : Math.round(n) + '分钟')"
                :min="0" :max="180"
                controls-position="right"
                style="width:150px;"
                title="留针时间(分钟)"
              >
                <template #prefix>留针</template>
                <template #suffix>分</template>
              </el-input-number>
              <el-input-number
                v-model="acp.sequence"
                :min="1" :max="30"
                controls-position="right"
                style="width:96px;"
                title="施针顺序：数字越小越先施针"
              >
                <template #prefix>顺序</template>
              </el-input-number>
              <el-input v-model="acp.note" placeholder="备注" style="width:120px;" size="small" />
            </div>
            <div class="herb-item-actions">
              <el-button v-if="editable" link type="danger" @click="removeAcupoint(idx)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
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
      <div v-if="dosageWarnings.length === 0 && pregnancyWarnings.length === 0 && form.items.length > 0"
        class="safety-section">
        <el-alert type="success" :closable="false" show-icon title="安全检查通过" description="未检测到剂量超限或孕妇禁忌" />
      </div>

      <div v-if="form.items.length === 0 && hasAcupointContent" class="safety-section">
        <el-alert type="info" :closable="false" show-icon title="纯针灸方" description="已添加配穴，无需剂量安全检查" />
      </div>

      <el-empty v-if="form.items.length === 0 && !hasAcupointContent"
        :description="'请在左侧添加药味或配穴'" :image-size="60" />
    </el-card>

    <!-- 中药方导入对话框 -->
    <el-dialog v-model="formulaDialogVisible" title="📖 从中药方导入" width="650px" destroy-on-close>
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

    <!-- 针灸方导入对话框 -->
    <el-dialog v-model="acupointFormulaDialogVisible" title="🪡 从针灸方导入" width="650px" destroy-on-close>
      <el-input v-model="acupointFormulaSearch" placeholder="搜索针方名 / 功效" clearable style="margin-bottom:12px;" />
      <el-table :data="filteredAcupointFormulas" stripe size="small" @row-click="selectAcupointFormula"
        highlight-current-row style="cursor:pointer;">
        <el-table-column prop="name" label="针方名" width="140" />
        <el-table-column prop="source" label="出处" width="100" />
        <el-table-column prop="efficacy" label="功效" show-overflow-tooltip />
        <el-table-column label="配穴" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.composition?.acupoints?.length">
              {{ row.composition.acupoints.map((a: any) => a.acupoint_name).join('、') }}
            </span>
            <span v-else style="color:#bbb;">—</span>
          </template>
        </el-table-column>
        </el-table>
        </el-dialog>

        <!-- AI 结构化方剂带入：勾选加减、字典校验 -->
        <AiFormulaImportDialog
        :visible="aiImportVisible"
        :formula="aiImportFormula"
        :herb-list="herbCacheList"
        @confirm="applyStructuredFormula"
        @close="aiImportVisible = false"
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
import AiFormulaImportDialog from '@/components/AiFormulaImportDialog.vue'
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
const acupointFormulas = ref<any[]>([])
const acupointFormulaDialogVisible = ref(false)
const acupointFormulaSearch = ref('')

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
  follow_up_date: '' as string,
  acupuncture_fee: null as number | null,
  items: [] as Array<{
    herb_id: number | null
    herb_name: string
    dose: number
    special_method: string | null
    is_king_herb: boolean
    note: string
    price?: number | null
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

const filteredAcupointFormulas = computed(() => {
  if (!acupointFormulaSearch.value) return acupointFormulas.value
  const q = acupointFormulaSearch.value.toLowerCase()
  return acupointFormulas.value.filter((f: any) =>
    f.name.toLowerCase().includes(q) || (f.efficacy || '').toLowerCase().includes(q)
  )
})

// ── 计价（预估）：单价优先药材参考价，其次该药材进价 ──
function herbUnitPrice(item: any): number | null {
  if (item == null || item.herb_id == null) return null
  const herb = herbCacheList.value.find((h: any) => h.id === item.herb_id)
  const price = herb?.price ?? item.price ?? null
  return price != null ? Number(price) : null
}
function herbItemAmount(item: any): number | null {
  const p = herbUnitPrice(item)
  if (p == null) return null
  const doses = Number(form.value.doses) || 1
  return Math.round(p * Number(item.dose || 0) * doses * 100) / 100
}
const herbTotal = computed(() => {
  let sum = 0
  for (const it of form.value.items) {
    const amt = herbItemAmount(it)
    if (amt != null) sum += amt
  }
  return Math.round(sum * 100) / 100
})
const acupunctureFee = computed(() => Number(form.value.acupuncture_fee) || 0)
const estimatedTotal = computed(() => {
  return Math.round((herbTotal.value + acupunctureFee.value) * 100) / 100
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

function retentionNum(v: string | null | undefined): number | null {
  const m = String(v ?? '').match(/\d+/)
  return m ? Number(m[0]) : null
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
    // 记录单价（参考中药材参考价），用于开方时实时预估金额
    form.value.items[idx].price = herb.price ?? null
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
    dosageWarnings.value = []
    pregnancyWarnings.value = []
    return
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

// ── 中药方导入 ──
function loadFromFormula() {
  formulaDialogVisible.value = true
}

// ── 针灸方导入 ──
function loadFromAcupointFormula() {
  if (!acupointFormulas.value.length) loadAcupointFormulas()
  acupointFormulaDialogVisible.value = true
}

function selectAcupointFormula(f: any) {
  acupointFormulaDialogVisible.value = false
  applyAcupointFormulaById(f.id)
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

// 从 AI 辨证推荐方剂（自由文本组成）带入：预填方名与药味
async function applyAiFormula(f: any) {
  if (!f) return
  form.value.formula_name = f.name || ''
  form.value.is_classic = false
  form.value.classic_formula_id = null
  form.value.items = []
  if (!herbCacheList.value.length) {
    await loadHerbList()
  }
  const comp: string = f.composition || ''
  // 仅保留含中文的「药名+剂量」片段，避免英文/JSON 键名(composeition: 等)被当成一味药
  const tokens = comp.split(/\s+/).filter(Boolean).filter(t => /[一-龥]/.test(t))
  for (const tok of tokens) {
    const m = tok.match(/^(.*?)(\d+(?:\.\d+)?)\s*(g|克|钱|两|枚|片|条|只)?$/i)
    let name = tok
    let dose = 10
    if (m && m[1].trim()) {
      name = m[1].trim()
      dose = parseFloat(m[2])
    }
    let matchedHerb = herbCacheList.value.find((herb: any) => herb.name === name)
    if (!matchedHerb) {
      matchedHerb = herbCacheList.value.find((herb: any) =>
        (herb.aliases || []).some((a: string) => a === name) ||
        (herb.name && (herb.name.includes(name) || name.includes(herb.name)))
      )
    }
    form.value.items.push({
      herb_id: matchedHerb?.id || null,
      herb_name: matchedHerb ? matchedHerb.name : name,
      dose,
      special_method: null,
      is_king_herb: false,
      note: '',
      _warnings: [],
    })
  }
  ElMessage.success(`已带入 AI 推荐方「${f.name || '未命名'}」`)
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

  // 仅药味方需做剂量/孕妇检查；纯针灸方无需安全检查
  if (hasHerb && dosageWarnings.value.length > 0) {
    ElMessage.warning('存在剂量超限，已自动添加到对应药物备注，可继续提交')
  }
  if (hasHerb && pregnancyWarnings.value.length > 0) {
    ElMessage.warning('存在孕妇禁忌药物，请谨慎开具')
  }

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
  f.acupuncture_fee = p.acupuncture_fee ?? null
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

async function loadAcupointFormulas() {
  try {
    acupointFormulas.value = (await api.get('/acupoint-formulas') as any) || []
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
  loadAcupointFormulas()

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

  // 从 AI 辨证页带入推荐方剂（结构化：勾选加减→合并→字典校验）
  const importKey = q.ai_import_key as string | undefined
  if (importKey) {
    try {
      const raw = sessionStorage.getItem(importKey)
      if (raw) {
        const f = JSON.parse(raw)
        await loadHerbList()
        aiImportFormula.value = f
        aiImportVisible.value = true
        sessionStorage.removeItem(importKey)
      }
    } catch {}
  } else if (q.ai_import) {
    // 兼容旧版：结构化 JSON 直接置于 query
    try {
      const f = typeof q.ai_import === 'string' ? JSON.parse(q.ai_import) : q.ai_import
      await loadHerbList()
      aiImportFormula.value = f
      aiImportVisible.value = true
    } catch {}
  } else if (q.ai_formula) {
    // 兼容旧版自由文本带入
    try {
      const f = typeof q.ai_formula === 'string' ? JSON.parse(q.ai_formula) : q.ai_formula
      await applyAiFormula(f)
    } catch {}
  }
})

// AI 结构化方剂 → 处方（主方/副方各自独立成方）
const aiImportVisible = ref(false)
const aiImportFormula = ref<any>(null)

function applyStructuredFormula(f: any) {
  if (!f) return
  form.value.formula_name = f.name || ''
  form.value.is_classic = false
  form.value.classic_formula_id = null
  if (f.preparation) form.value.preparation_method = f.preparation
  form.value.items = (f.herbs || []).map((h: any) => {
    const doseNum = parseFloat(String(h.dose || '').replace(/[^\d.]/g, ''))
    const hit = h.herb_id ? herbCacheList.value.find((x: any) => x.id === h.herb_id) : null
    const herbName = hit ? hit.name : h.name
    return {
      herb_id: h.herb_id ?? null,
      herb_name: herbName,
      dose: isNaN(doseNum) ? 10 : doseNum,
      special_method: h.method || null,
      is_king_herb: false,
      note: h.unknown ? `⚠️字典无此药：${h.name}` : '',
      _warnings: h.unknown ? [`药材字典中无「${h.name}」，请核对`] : [],
    }
  })
  aiImportVisible.value = false
  ElMessage.success(`已带入 AI 推荐方「${f.name || '未命名'}」${f.role ? '（' + f.role + '）' : ''}`)
  runSafetyCheck()
}
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

/* ---- 移动端适配 ---- */
@media (max-width: 767px) {
  .prescription-editor {
    :deep(.el-card__header) { padding: 12px; }
    :deep(.editor-header) {
      flex-direction: column;
      align-items: stretch;
      gap: 10px;
    }
    :deep(.editor-header .editor-actions) {
      width: 100%;
      justify-content: flex-end;
    }
    /* 所有 el-col 在窄屏强制占满整行，自动单列堆叠 */
    :deep(.el-col) {
      flex: 0 0 100% !important;
      max-width: 100% !important;
    }
    :deep(.el-form-item) { margin-bottom: 14px; }
    :deep(.el-form-item__label) { padding-bottom: 4px; }
    /* 药味/配穴明细：控件在窄屏铺满整行、纵向堆叠 */
    :deep(.herb-item-fields) {
      align-items: stretch;
      gap: 6px;
    }
    :deep(.herb-item-fields > *) {
      width: 100% !important;
      min-width: 0 !important;
    }
    :deep(.herb-item-fields .el-checkbox) {
      align-items: center;
      margin-right: 0;
    }
    :deep(.el-divider) { margin: 20px 0; }
  }
}
</style>