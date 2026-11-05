<template>
  <div class="reg-page">
    <el-card shadow="hover" class="reg-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">🪪</span>
            <span class="tcm-head__text">挂号台</span>
            <el-tag size="small" effect="light" round>{{ today }}</el-tag>
          </div>
        </div>
      </template>

      <el-row :gutter="16">
        <!-- 左：挂号登记 -->
        <el-col :xs="24" :md="9">
          <el-form label-width="80px" class="reg-form">
            <el-form-item label="患者">
              <el-select
                v-model="selectedPatientId"
                filterable remote :remote-method="searchPatients" remote-show-suffix
                placeholder="搜索姓名/电话，或下方新建" style="width:100%" clearable
                @change="onSelectPatient"
              >
                <el-option v-for="p in patientOptions" :key="p.id" :label="`${p.name} ${p.gender || ''} ${p.phone || ''}`" :value="p.id" />
              </el-select>
            </el-form-item>

            <!-- 已选患者档案摘要：与「患者列表」互通，展示关键信息并提示过敏史 -->
            <div v-if="selectedPatient" class="patient-summary">
              <div class="patient-summary__head">
                <span class="patient-summary__name">{{ selectedPatient.name }}</span>
                <el-tag v-if="selectedPatient.gender" size="small">{{ selectedPatient.gender }}</el-tag>
                <span v-if="selectedPatient.birth_date" class="patient-summary__meta">{{ selectedPatient.birth_date }}</span>
                <el-link type="primary" :underline="false" class="patient-summary__link" @click="openPatientDetail(selectedPatient.id)">查看档案</el-link>
              </div>
              <el-alert v-if="selectedPatient.allergy_history" type="error" :closable="false" show-icon
                :title="`过敏史：${selectedPatient.allergy_history}`" class="patient-summary__alert" />
              <div v-else-if="selectedPatient.phone" class="patient-summary__meta">{{ selectedPatient.phone }}</div>

              <!-- 历史就诊/处方快捷查看：与档案互通，前台一眼看既往史 -->
              <el-collapse v-model="historyOpen" class="history-collapse">
                <el-collapse-item name="history">
                  <template #title>
                    历史就诊 / 处方
                    <span class="history-count" v-if="historyVisits.length || historyRx.length">
                      （就诊 {{ historyVisits.length }} · 处方 {{ historyRx.length }}）
                    </span>
                  </template>
                  <div v-if="historyLoading" class="history-loading">加载中…</div>
                  <template v-else>
                    <div v-if="!historyVisits.length && !historyRx.length" class="history-empty">暂无历史记录</div>
                    <div v-else class="history-block">
                      <div v-if="historyVisits.length" class="history-sub">就诊记录</div>
                      <div v-for="v in historyVisits" :key="'v'+v.id" class="history-item" @click="openPatientDetail(selectedPatient.id)">
                        <span class="history-date">{{ v.visit_date }}</span>
                        <span class="history-title">{{ v.chief_complaint || '就诊' }}</span>
                        <el-tag v-if="v.status" size="small" effect="plain">{{ v.status }}</el-tag>
                      </div>
                      <div v-if="historyRx.length" class="history-sub">处方记录</div>
                      <div v-for="rx in historyRx" :key="'r'+rx.id" class="history-item" @click="openPatientDetail(selectedPatient.id)">
                        <span class="history-date">{{ (rx.created_at || '').slice(0, 10) }}</span>
                        <span class="history-title">{{ rx.formula_name || rx.title || '处方' }}</span>
                        <el-tag v-if="rx.status" size="small" effect="plain">{{ rx.status }}</el-tag>
                      </div>
                    </div>
                  </template>
                </el-collapse-item>
              </el-collapse>
            </div>

            <el-collapse v-model="showNewPatient">
              <el-collapse-item name="new" title="＋ 新建患者（字段与档案一致）">
                <!-- 查重：同名/同证件疑似重复时警示，可直接选择已有患者 -->
                <div v-if="dups.length && !dupChecked" class="dup-warn">
                  <el-alert type="warning" :closable="false" show-icon>
                    <template #title>疑似重复患者（{{ dups.length }} 位），请先确认是否为同一人</template>
                    <div class="dup-list">
                      <div v-for="d in dups" :key="d.id" class="dup-item">
                        <span class="dup-meta">{{ d.name }} · {{ d.gender || '-' }} · {{ d.birth_date || '未知出生' }} · {{ d.phone || '无电话' }}</span>
                        <el-button link type="primary" size="small" @click="selectExistingDup(d)">选择此人</el-button>
                      </div>
                    </div>
                    <el-button size="small" type="primary" plain class="dup-confirm" @click="dupChecked = true">确认是新患者，继续建档</el-button>
                  </el-alert>
                </div>
                <div v-else-if="dupLoading" class="dup-loading">查重中…</div>
                <el-form label-width="72px" class="sub-form">
                  <el-form-item label="姓名"><el-input v-model="np.name" placeholder="必填" /></el-form-item>
                  <el-form-item label="性别">
                    <el-select v-model="np.gender" placeholder="选填" style="width:100%">
                      <el-option label="男" value="男" />
                      <el-option label="女" value="女" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="出生"><el-date-picker v-model="np.birth_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
                  <el-form-item label="电话"><el-input v-model="np.phone" /></el-form-item>
                  <el-form-item label="身份证"><el-input v-model="np.id_card" /></el-form-item>
                  <el-form-item label="地址"><el-input v-model="np.address" /></el-form-item>
                  <el-form-item label="身高cm"><el-input v-model.number="np.height" type="number" /></el-form-item>
                  <el-form-item label="体重kg"><el-input v-model.number="np.weight" type="number" /></el-form-item>
                  <el-form-item label="过敏史"><el-input v-model="np.allergy_history" type="textarea" :rows="2" placeholder="如：青霉素过敏" /></el-form-item>
                  <el-form-item label="既往史"><el-input v-model="np.medical_history" type="textarea" :rows="2" /></el-form-item>
                  <el-form-item label="备注"><el-input v-model="np.notes" type="textarea" :rows="1" /></el-form-item>
                </el-form>
              </el-collapse-item>
            </el-collapse>

            <el-form-item label="科室">
              <el-select v-model="department" clearable filterable placeholder="选择科室" style="width:100%"
                @change="onDepartmentChange">
                <el-option v-for="d in departmentOptions" :key="d" :label="d" :value="d" />
              </el-select>
            </el-form-item>
            <el-form-item label="接诊医师">
              <el-select v-model="doctorId" clearable filterable placeholder="选择医师（可选）" style="width:100%"
                @change="onDoctorChange">
                <el-option v-for="d in filteredDoctors" :key="d.id"
                  :label="d.department ? `${d.name}（${d.department}）` : d.name" :value="d.id" />
              </el-select>
              <div class="opt-hint">选项来自「账号管理」中启用的医生/管理员账号</div>
            </el-form-item>
            <el-form-item label="挂号费">
              <el-input-number v-model="regFee" :min="0" :precision="2" :step="1" style="width:160px" />
            </el-form-item>
            <template v-if="regFee > 0">
              <el-form-item label="收款方式">
                <el-select v-model="payMethod" style="width:160px">
                  <el-option v-for="m in methods" :key="m" :label="m" :value="m" />
                </el-select>
              </el-form-item>
              <el-form-item label="实收">
                <el-input-number v-model="paid" :min="0" :precision="2" :step="1" style="width:160px" />
              </el-form-item>
            </template>

            <el-button type="primary" :loading="submitting" @click="submitRegister">确认挂号</el-button>
          </el-form>
        </el-col>

        <!-- 右：今日队列 -->
        <el-col :xs="24" :md="15">
          <div class="queue-bar">
            <el-radio-group v-model="statusFilter" @change="loadQueue">
              <el-radio-button value="">全部</el-radio-button>
              <el-radio-button value="待诊">待诊</el-radio-button>
              <el-radio-button value="已接诊">已接诊</el-radio-button>
              <el-radio-button value="已完成">已完成</el-radio-button>
            </el-radio-group>
            <el-button @click="loadQueue">刷新</el-button>
          </div>

          <el-table :data="queue" class="queue-table" empty-text="今日暂无挂号" style="width:100%">
            <el-table-column prop="queue_no" label="号" width="60" />
            <el-table-column label="患者" min-width="110">
              <template #default="{ row }">
                <el-link type="primary" :underline="false" @click="openPatientDetail(row.patient_id)">{{ row.patient_name || '-' }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="科室 / 接诊医师" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                {{ [row.department, row.doctor_name].filter(Boolean).join(' / ') || '—' }}
              </template>
            </el-table-column>
            <el-table-column label="挂号费" width="90" align="right">
              <template #default="{ row }">
                <span v-if="row.registration_fee">¥{{ Number(row.registration_fee).toFixed(2) }}</span>
                <span v-else class="muted">免</span>
              </template>
            </el-table-column>
            <el-table-column label="收费" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.registration_charge" :type="chargeTagType(row.registration_charge.status)" size="small">
                  {{ chargeLabel(row.registration_charge.status) }}
                </el-tag>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small" effect="light" round>{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status === '待诊'" link type="primary" size="small" @click="callVisit(row)">接诊</el-button>
                <el-tooltip v-if="row.status === '已接诊'" :disabled="row.evidence?.can_complete"
                  :content="(row.evidence?.completion_blockers || []).join('；') || '需先完善本次就诊记录'" placement="top">
                  <span class="op-wrap">
                    <el-button link type="success" size="small" :disabled="!row.evidence?.can_complete" @click="completeVisit(row)">完成</el-button>
                  </span>
                </el-tooltip>
                <el-button v-if="row.evidence?.can_revert" link type="info" size="small" @click="openRevert(row)">撤销</el-button>
                <el-button v-if="row.registration_charge && row.registration_charge.status === '待收费'" link type="warning" size="small" @click="collectRegFee(row)">收挂号费</el-button>
                <el-button v-if="!['已完成','已取消'].includes(row.status)" link type="danger" size="small" @click="cancelVisit(row)">退号</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-col>
      </el-row>
    </el-card>

    <!-- 撤销误操作：原因必填，写入操作日志 -->
    <el-dialog v-model="revertVisible" title="撤销就诊状态" width="440px" append-to-body>
      <div v-if="revertTarget" class="dlg-body">
        <p>将 <b>{{ revertTarget.patient_name }}</b> 的本次就诊从「{{ revertTarget.status }}」回退？</p>
        <el-alert type="warning" :closable="false" show-icon
          :title="revertTarget.evidence?.revert_hint || '仅在未写病历、未发药、未收款时允许回退'" />
        <el-input v-model="revertReason" type="textarea" :rows="2" style="margin-top: 12px"
          placeholder="撤销原因（必填，将写入操作日志）" />
      </div>
      <template #footer>
        <el-button @click="revertVisible = false">取消</el-button>
        <el-button type="warning" :loading="reverting" @click="submitRevert">确认撤销</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { errMsg } from '@/utils/api'
import { findPatientDuplicates } from '@/utils/dedup'
import type { RegistrationQueueItem } from '@/types'

const router = useRouter()
const methods = ['现金', '微信', '支付宝', '银行卡', '医保', '记账']
const today = new Date().toISOString().slice(0, 10)

// ── 挂号表单 ──
const selectedPatientId = ref<number | null>(null)
const patientOptions = ref<any[]>([])
const selectedPatient = ref<any>(null)  // 已选患者档案摘要（互通）
const showNewPatient = ref<string[]>([])
// 历史就诊/处方快捷查看
const historyOpen = ref<string[]>([])
const historyLoading = ref(false)
const historyVisits = ref<any[]>([])
const historyRx = ref<any[]>([])

// 患者查重：防止同名/同身份证造成重复建档（就诊史分散）
const dups = ref<any[]>([])
const dupLoading = ref(false)
const dupChecked = ref(false)  // 用户已确认"仍要新建"
let dupTimer: ReturnType<typeof setTimeout> | null = null

function scheduleDupCheck() {
  dupChecked.value = false
  if (dupTimer) clearTimeout(dupTimer)
  dupTimer = setTimeout(runDupCheck, 400)
}
async function runDupCheck() {
  const name = np.name.trim()
  if (!name) { dups.value = []; return }
  dupLoading.value = true
  try {
    dups.value = await findPatientDuplicates({ name, phone: np.phone || null, id_card: np.id_card || null })
  } finally {
    dupLoading.value = false
  }
}
function selectExistingDup(d: any) {
  // 直接选中该存量患者，避免重复建档
  selectedPatientId.value = d.id
  dups.value = []
  onSelectPatient()
}
// 新建患者字段与「患者列表-新增患者」(PatientCreate) 完全一致
const np = reactive({
  name: '', gender: null as string | null, birth_date: null as string | null, phone: '',
  id_card: '', address: '', height: null as number | null, weight: null as number | null,
  allergy_history: '', medical_history: '', notes: '',
})
const department = ref('')
const doctorId = ref<number | null>(null)
// 科室与接诊医师均由「账号管理」中启用的医生/管理员账号派生
interface DoctorOption { id: number; name: string; department: string }
const departmentOptions = ref<string[]>([])
const doctors = ref<DoctorOption[]>([])
const filteredDoctors = computed(() =>
  department.value ? doctors.value.filter(d => d.department === department.value) : doctors.value
)

async function loadOptions() {
  try {
    const r = await api.get<{ departments: string[]; doctors: DoctorOption[] }>('/registration/options')
    departmentOptions.value = r.departments || []
    doctors.value = r.doctors || []
  } catch { /* 拦截器已提示 */ }
}
function onDoctorChange() {
  const d = doctors.value.find(x => x.id === doctorId.value)
  if (d?.department) department.value = d.department  // 选医师自动带出其科室
}
function onDepartmentChange() {
  const d = doctors.value.find(x => x.id === doctorId.value)
  if (d && d.department && d.department !== department.value) doctorId.value = null
}

const regFee = ref(0)
const payMethod = ref('现金')
const paid = ref(0)
const submitting = ref(false)

const canSubmit = computed(() => selectedPatientId.value || np.name.trim().length > 0)

async function searchPatients(kw: string) {
  if (!kw) { patientOptions.value = []; return }
  const r = await api.get<{ items: any[] }>('/patients', { params: { search: kw, page: 1, page_size: 20 } })
  patientOptions.value = r.items || []
}
async function onSelectPatient() {
  // 选择已有患者后拉取其档案摘要、清空新建表单，避免混淆
  if (!selectedPatientId.value) { selectedPatient.value = null; return }
  np.name = ''
  showNewPatient.value = []
  dups.value = []
  dupChecked.value = false
  historyOpen.value = ['history']
  historyVisits.value = []
  historyRx.value = []
  try {
    const r = await api.get<any>(`/patients/${selectedPatientId.value}`)
    selectedPatient.value = r
    await loadPatientHistory(selectedPatientId.value)
  } catch { selectedPatient.value = null }
}

// 快捷加载患者历史就诊与处方（与档案互通）
async function loadPatientHistory(id: number) {
  historyLoading.value = true
  try {
    const [visits, rx] = await Promise.all([
      api.get<any[]>(`/patients/${id}/visits`),
      api.get<{ items: any[] }>('/prescriptions', { params: { patient_id: id, page: 1, page_size: 10 } }),
    ])
    historyVisits.value = (visits || []).slice(0, 8)
    historyRx.value = (rx?.items || []).slice(0, 8)
  } catch {
    historyVisits.value = []
    historyRx.value = []
  } finally {
    historyLoading.value = false
  }
}
function openPatientDetail(id?: number) {
  if (!id) return
  router.push(`/patients/${id}`)
}

async function submitRegister() {
  if (!canSubmit.value) { ElMessage.warning('请选择或新建患者'); return }
  if (regFee.value > 0 && paid.value < regFee.value - 1e-6) {
    ElMessage.warning('实收不能小于挂号费'); return
  }
  // 查重：存在疑似重复且未确认时，强制二次确认，避免重复建档
  if (dups.value.length && !dupChecked.value) {
    try {
      await ElMessageBox.confirm(
        `系统中已有 ${dups.value.length} 位疑似同名/同证件患者，确认要新建档案吗？\n如为同一人，请取消并在上方选择已有患者。`,
        '疑似重复患者', { type: 'warning', confirmButtonText: '仍要新建', cancelButtonText: '去选择' }
      )
      dupChecked.value = true
    } catch {
      return  // 用户选择"去选择"，中止建档
    }
  }
  submitting.value = true
  try {
    const payload: any = {
      department: department.value || null,
      doctor_id: doctorId.value,
      registration_fee: regFee.value,
    }
    if (selectedPatientId.value) payload.patient_id = selectedPatientId.value
    else {
      // 与 PatientCreate 对齐：仅提交有值的字段
      const p: Record<string, any> = { name: np.name.trim() }
      for (const k of ['gender', 'birth_date', 'phone', 'id_card', 'address', 'height', 'weight', 'allergy_history', 'medical_history', 'notes'] as const) {
        if (np[k] !== null && np[k] !== '') p[k] = np[k]
      }
      payload.new_patient = p
    }
    if (regFee.value > 0) {
      payload.payment_method = payMethod.value
      payload.paid = paid.value
    }
    // 同日重复挂号：后端返回 409，前台确认后以 force=true 重试，避免误点重复收挂号费
    let r: any
    try {
      r = await api.post('/registration', payload, { silent: true })
    } catch (e: unknown) {
      const status = (e as any)?.response?.status
      const msg = errMsg(e)
      if (status === 409 && msg.includes('今日已挂号')) {
        try {
          await ElMessageBox.confirm(msg, '该患者今日已挂号', {
            type: 'warning', confirmButtonText: '仍然挂号', cancelButtonText: '取消',
          })
        } catch { return }
        r = await api.post('/registration', { ...payload, force: true })
      } else {
        ElMessage.error(msg)
        return
      }
    }
    ElMessage.success(`挂号成功，排队号 ${r.visit.queue_no}`)
    if (r.duplicate_of) {
      ElMessage.warning(`该患者今日已挂过号（就诊 #${r.duplicate_of}），本次为再次挂号，请核对是否重复收取挂号费`)
    }
    // 重置
    selectedPatientId.value = null; selectedPatient.value = null; patientOptions.value = []
    historyVisits.value = []; historyRx.value = []; historyOpen.value = []
    dups.value = []; dupChecked.value = false
    Object.assign(np, { name: '', gender: null, birth_date: null, phone: '', id_card: '', address: '', height: null, weight: null, allergy_history: '', medical_history: '', notes: '' })
    department.value = ''; doctorId.value = null; regFee.value = 0; paid.value = 0; showNewPatient.value = []
    loadQueue()
  } catch { /* 拦截器已提示 */ } finally {
    submitting.value = false
  }
}

// ── 队列 ──
const queue = ref<RegistrationQueueItem[]>([])
const statusFilter = ref('')

function statusType(s: string): 'success' | 'warning' | 'info' | 'danger' {
  if (s === '已完成') return 'success'
  if (s === '待诊') return 'warning'
  if (s === '已接诊') return 'primary' as any
  if (s === '已取消') return 'danger'
  return 'info'
}

function chargeLabel(s: string): string {
  return ({ '待收费': '待收', '已收费': '已收', '已退费': '已退', '已取消': '已作废' } as Record<string, string>)[s] || s
}
function chargeTagType(s: string): 'success' | 'warning' | 'info' | 'danger' {
  if (s === '已收费') return 'success'
  if (s === '待收费') return 'warning'
  if (s === '已退费') return 'danger'
  return 'info'
}

async function loadQueue() {
  try {
    const params: Record<string, any> = {}
    if (statusFilter.value) params.status = statusFilter.value
    const r = await api.get<{ items: RegistrationQueueItem[] }>('/registration/queue', { params })
    queue.value = r.items || []
  } catch { /* 拦截器已提示 */ }
}

async function callVisit(row: RegistrationQueueItem) {
  try {
    await api.post(`/registration/${row.id}/call`)
    ElMessage.success('已叫号，进入接诊')
    // 挂号时已创建本次就诊（占位病历），正确路径是去患者详情「完善本次就诊」，
    // 由医生写主诉/四诊/辨证，再由就诊抽屉内的「去开药」进入开方页。
    // 不再直接跳开方页，避免病历停留在占位符。
    if (!row.patient_id) { loadQueue(); return }
    router.push({
      path: `/patients/${row.patient_id}`,
      query: { visit_id: String(row.id), open_visit: '1' },
    })
  } catch { /* 拦截器已提示 */ }
}

async function completeVisit(row: RegistrationQueueItem) {
  const ev = row.evidence || {}
  if (ev.can_complete === false) {
    ElMessage.warning((ev.completion_blockers || []).join('；') || '请先完善本次就诊记录')
    return
  }
  const lines = [
    `本次就诊病历：${ev.has_record ? '已填写' : '未填写'}`,
    `处方：${ev.prescription_count || 0} 张`,
    ...(ev.completion_warnings || []),
    '确认将本次就诊标记为「已完成」？',
  ]
  try {
    await ElMessageBox.confirm(lines.join('\n'), '确认完成就诊', { type: 'info' })
  } catch { return }
  try {
    await api.post(`/registration/${row.id}/complete`)
    ElMessage.success('就诊已完成')
    loadQueue()
  } catch { /* 拦截器已提示 */ }
}

// 误点「接诊 / 完成」的受控回退（后端按业务事实审批并写审计日志）
const revertVisible = ref(false)
const revertTarget = ref<RegistrationQueueItem | null>(null)
const revertReason = ref('')
const reverting = ref(false)
function openRevert(row: RegistrationQueueItem) {
  revertTarget.value = row
  revertReason.value = ''
  revertVisible.value = true
}
async function submitRevert() {
  if (!revertTarget.value?.id) return
  if (!revertReason.value.trim()) { ElMessage.warning('请填写撤销原因（将写入操作日志）'); return }
  reverting.value = true
  try {
    await api.post(`/registration/${revertTarget.value.id}/revert`, { reason: revertReason.value.trim() })
    ElMessage.success('已撤销，状态已回退')
    revertVisible.value = false
    loadQueue()
  } catch { /* 拦截器已提示 */ } finally {
    reverting.value = false
  }
}

async function cancelVisit(row: RegistrationQueueItem) {
  try {
    const feePaid = row.registration_charge?.status === '已收费'
    await ElMessageBox.confirm(
      `确认退号（${row.patient_name}）？${feePaid ? '\n已收挂号费将自动全额退费；' : '\n待收挂号费将自动作废；'}该操作不可撤销。`,
      '退号', { type: 'warning', confirmButtonText: '确认退号' }
    )
    await api.patch(`/registration/${row.id}`, { status: '已取消' })
    ElMessage.success(feePaid ? '已退号，挂号费已自动退费' : '已退号，待收挂号费已作废')
    loadQueue()
  } catch { /* 取消或异常 */ }
}

async function collectRegFee(row: RegistrationQueueItem) {
  const cid = row.registration_charge?.id
  if (!cid) return
  try {
    await api.post(`/billing/charges/${cid}/pay`, { payment_method: '现金', paid: row.registration_charge?.payable })
    ElMessage.success('挂号费已收')
    loadQueue()
  } catch { /* 拦截器已提示 */ }
}

// 新建患者表单变化即触发查重（防抖）
watch(() => [np.name, np.phone, np.id_card], () => scheduleDupCheck())

onMounted(() => { loadQueue(); loadOptions() })
</script>

<style scoped lang="scss">
.reg-page { .reg-card { :deep(.el-card__header) { padding: 14px 18px; } } }
.reg-form { margin-top: 4px; }
.sub-form { background: #faf7f3; padding: 8px 12px; border-radius: 8px; margin-bottom: 8px; }
.patient-summary { background: #f7fbf8; border: 1px solid #e3efe7; border-radius: 8px; padding: 8px 12px; margin-bottom: 10px; }
.patient-summary__head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.patient-summary__name { font-weight: 600; color: #3a3a3a; }
.patient-summary__meta { color: #8a8170; font-size: 12px; }
.patient-summary__link { margin-left: auto; }
.patient-summary__alert { margin-top: 6px; }
.history-collapse { margin-top: 8px; border: none; }
.history-count { color: #8a8170; font-weight: 400; font-size: 12px; }
.history-loading, .history-empty { color: #8a8170; font-size: 13px; padding: 4px 0; }
.history-sub { font-size: 12px; color: #6b6454; margin: 6px 0 2px; font-weight: 600; }
.history-item { display: flex; align-items: center; gap: 8px; padding: 4px 6px; border-radius: 6px; cursor: pointer; }
.history-item:hover { background: #eef6f1; }
.history-date { color: #8a8170; font-size: 12px; width: 80px; flex: 0 0 80px; }
.history-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dup-warn { margin-bottom: 8px; }
.dup-loading { color: #8a8170; font-size: 12px; margin-bottom: 6px; }
.dup-list { margin: 2px 0 6px; }
.dup-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 2px 0; }
.dup-meta { font-size: 12px; color: #6b6454; }
.dup-confirm { margin-top: 2px; }
.queue-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 8px; flex-wrap: wrap; }
.muted { color: #b0a394; }
.queue-table { :deep(.el-tag--primary) { --el-tag-bg-color: #ecf5ff; --el-tag-text-color: #409eff; --el-tag-border-color: #d9ecff; } }
.op-wrap { display: inline-block; margin-right: 8px; }
.dlg-body { font-size: 14px; line-height: 1.8; }
.opt-hint { font-size: 12px; color: #8a8170; line-height: 1.4; margin-top: 2px; }
</style>
