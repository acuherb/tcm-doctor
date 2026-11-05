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
            </div>

            <el-collapse v-model="showNewPatient">
              <el-collapse-item name="new" title="＋ 新建患者（字段与档案一致）">
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

            <el-form-item label="科室/医师">
              <el-input v-model="department" placeholder="如：中医内科 / 张医师" />
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
            <el-table-column prop="department" label="科室/医师" min-width="110" show-overflow-tooltip />
            <el-table-column label="挂号费" width="90" align="right">
              <template #default="{ row }">
                <span v-if="row.registration_fee">¥{{ Number(row.registration_fee).toFixed(2) }}</span>
                <span v-else class="muted">免</span>
              </template>
            </el-table-column>
            <el-table-column label="收费" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.registration_charge" :type="row.registration_charge.status === '已收费' ? 'success' : 'warning'" size="small">
                  {{ row.registration_charge.status === '已收费' ? '已收' : '待收' }}
                </el-tag>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small" effect="light" round>{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="170" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status === '待诊'" link type="primary" size="small" @click="callVisit(row)">接诊</el-button>
                <el-button v-if="row.status === '已接诊'" link type="success" size="small" @click="completeVisit(row)">完成</el-button>
                <el-button v-if="row.registration_charge && row.registration_charge.status === '待收费'" link type="warning" size="small" @click="collectRegFee(row)">收挂号费</el-button>
                <el-button v-if="!['已完成','已取消'].includes(row.status)" link type="danger" size="small" @click="cancelVisit(row)">退号</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import type { RegistrationQueueItem } from '@/types'

const router = useRouter()
const methods = ['现金', '微信', '支付宝', '银行卡', '医保', '记账']
const today = new Date().toISOString().slice(0, 10)

// ── 挂号表单 ──
const selectedPatientId = ref<number | null>(null)
const patientOptions = ref<any[]>([])
const selectedPatient = ref<any>(null)  // 已选患者档案摘要（互通）
const showNewPatient = ref<string[]>([])
// 新建患者字段与「患者列表-新增患者」(PatientCreate) 完全一致
const np = reactive({
  name: '', gender: null as string | null, birth_date: null as string | null, phone: '',
  id_card: '', address: '', height: null as number | null, weight: null as number | null,
  allergy_history: '', medical_history: '', notes: '',
})
const department = ref('')
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
  try {
    const r = await api.get<any>(`/patients/${selectedPatientId.value}`)
    selectedPatient.value = r
  } catch { selectedPatient.value = null }
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
  submitting.value = true
  try {
    const payload: any = {
      department: department.value || null,
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
    const r = await api.post('/registration', payload)
    ElMessage.success(`挂号成功，排队号 ${r.visit.queue_no}`)
    // 重置
    selectedPatientId.value = null; selectedPatient.value = null; patientOptions.value = []
    Object.assign(np, { name: '', gender: null, birth_date: null, phone: '', id_card: '', address: '', height: null, weight: null, allergy_history: '', medical_history: '', notes: '' })
    department.value = ''; regFee.value = 0; paid.value = 0; showNewPatient.value = []
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
    // 跳转到开方页（带入 visit 与 patient，闭合 挂号→就诊→开方 链路）
    router.push({ path: '/prescriptions/new', query: { visit_id: String(row.id), patient_id: String(row.patient_id) } })
  } catch { /* 拦截器已提示 */ }
}

async function completeVisit(row: RegistrationQueueItem) {
  try {
    await api.post(`/registration/${row.id}/complete`)
    ElMessage.success('就诊已完成')
    loadQueue()
  } catch { /* 拦截器已提示 */ }
}

async function cancelVisit(row: RegistrationQueueItem) {
  try {
    await ElMessageBox.confirm(`确认退号（${row.patient_name}）？`, '退号', { type: 'warning' })
    await api.patch(`/registration/${row.id}`, { status: '已取消' })
    ElMessage.success('已退号')
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

onMounted(loadQueue)
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
.queue-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 8px; flex-wrap: wrap; }
.muted { color: #b0a394; }
.queue-table { :deep(.el-tag--primary) { --el-tag-bg-color: #ecf5ff; --el-tag-text-color: #409eff; --el-tag-border-color: #d9ecff; } }
</style>
