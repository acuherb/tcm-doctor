<template>
  <div class="billing-page">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">💰</span>
            <span class="tcm-head__text">收费管理</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ total }} 单</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-button @click="loadAll">刷新</el-button>
          </div>
        </div>
      </template>

      <!-- 汇总 -->
      <el-row :gutter="12" class="stat-row">
        <el-col :xs="12" :sm="6">
          <div class="stat-card is-paid">
            <div class="stat-card__label">已收金额</div>
            <div class="stat-card__value">¥{{ (stats.paid_amount || 0).toFixed(2) }}</div>
            <div class="stat-card__sub">{{ stats.paid_count || 0 }} 单</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-card is-pending">
            <div class="stat-card__label">待收金额</div>
            <div class="stat-card__value">¥{{ (stats.pending_amount || 0).toFixed(2) }}</div>
            <div class="stat-card__sub">{{ stats.pending_count || 0 }} 单</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-card is-refund">
            <div class="stat-card__label">退费金额</div>
            <div class="stat-card__value">¥{{ (stats.refunded_amount || 0).toFixed(2) }}</div>
            <div class="stat-card__sub">{{ stats.refunded_count || 0 }} 单</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-card is-total">
            <div class="stat-card__label">单据总数</div>
            <div class="stat-card__value">{{ stats.total_count || 0 }}</div>
            <div class="stat-card__sub">当前筛选</div>
          </div>
        </el-col>
      </el-row>

      <!-- 筛选 -->
      <div class="tcm-filter">
        <el-select v-model="statusFilter" placeholder="全部状态" clearable class="filter-mini" @change="loadCharges(true)">
          <el-option label="待收费" value="待收费" />
          <el-option label="已收费" value="已收费" />
          <el-option label="已退费" value="已退费" />
        </el-select>
        <el-select v-model="kindFilter" placeholder="全部类型" clearable class="filter-mini" @change="loadCharges(true)">
          <el-option label="处方收费" value="prescription" />
          <el-option label="挂号费" value="registration" />
        </el-select>
        <el-input v-model="patientFilter" placeholder="患者姓名" clearable class="filter-search"
          @clear="loadCharges(true)" @keyup.enter="loadCharges(true)" />
        <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD"
          start-placeholder="开始日期" end-placeholder="结束日期" style="width: 250px"
          @change="loadAll" />
        <div class="filter-actions">
          <el-button type="primary" @click="loadAll">查询</el-button>
        </div>
      </div>

      <el-table v-if="!isMobile" :data="charges" class="tcm-table" style="width:100%" empty-text="暂无收费单">
        <el-table-column prop="charge_no" label="单号" width="165" />
        <el-table-column prop="patient_name" label="患者" min-width="100" show-overflow-tooltip />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.kind === 'registration' ? 'warning' : 'info'" size="small" effect="plain">
              {{ row.kind === 'registration' ? '挂号费' : '处方' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="prescription_title" label="项目" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.kind === 'registration' ? '挂号费' : (row.prescription_title || '-') }}</template>
        </el-table-column>
        <el-table-column label="应收" width="100" align="right">
          <template #default="{ row }">¥{{ Number(row.amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="减免" width="90" align="right">
          <template #default="{ row }">{{ Number(row.discount) ? '-¥' + Number(row.discount).toFixed(2) : '—' }}</template>
        </el-table-column>
        <el-table-column label="实收" width="105" align="right">
          <template #default="{ row }">
            <span class="paid-amount">¥{{ Number(row.payable).toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="payment_method" label="方式" width="85" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small" effect="light" round>{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cashier_name" label="收银员" width="100" />
        <el-table-column prop="created_at" label="开单时间" width="160" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openReceipt(row)">收据</el-button>
            <el-button v-if="canWrite && row.status === '待收费'" link type="warning" size="small" @click="openPay(row)">收款</el-button>
            <el-button v-if="canWrite && row.status === '已收费'" link type="danger" size="small" @click="openRefund(row)">退费</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 移动端卡片 -->
      <div v-else class="bill-cards">
        <div v-for="c in charges" :key="c.id" class="bill-card">
          <div class="bill-card__head">
            <span class="bill-card__no">{{ c.charge_no }}</span>
            <el-tag :type="statusType(c.status || '')" size="small">{{ c.status }}</el-tag>
          </div>
          <div class="bill-card__line">患者：{{ c.patient_name || '-' }} · {{ c.prescription_title || '-' }}</div>
          <div class="bill-card__line">实收：<b>¥{{ Number(c.payable).toFixed(2) }}</b> · {{ c.payment_method || '-' }}</div>
          <div class="bill-card__line">{{ c.created_at }}</div>
          <div class="bill-card__ops">
            <el-button link type="primary" size="small" @click="openReceipt(c)">收据</el-button>
            <el-button v-if="canWrite && c.status === '待收费'" link type="warning" size="small" @click="openPay(c)">收款</el-button>
            <el-button v-if="canWrite && c.status === '已收费'" link type="danger" size="small" @click="openRefund(c)">退费</el-button>
          </div>
        </div>
        <el-empty v-if="!charges.length" description="暂无收费单" />
      </div>

      <el-pagination
        v-model:current-page="page" v-model:page-size="pageSize"
        :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
        class="bill-pager" @current-change="loadCharges()" @size-change="loadCharges(true)"
      />
    </el-card>

    <!-- 收据 -->
    <ReceiptDialog v-model:visible="receiptVisible" :charge="receiptCharge" />

    <!-- 收款 -->
    <el-dialog v-model="payVisible" title="收款" width="420px" append-to-body>
      <div v-if="payTarget" class="dlg-body">
        <p>单号 <b>{{ payTarget.charge_no }}</b>　患者 <b>{{ payTarget.patient_name || '-' }}</b></p>
        <p class="dlg-payable">应付：<b>¥{{ Number(payTarget.payable).toFixed(2) }}</b></p>
        <el-form label-width="84px">
          <el-form-item label="收款方式">
            <el-select v-model="payMethod" style="width: 160px">
              <el-option v-for="m in methods" :key="m" :label="m" :value="m" />
            </el-select>
          </el-form-item>
          <el-form-item label="实收金额">
            <el-input-number v-model="payAmount" :min="0" :precision="2" :step="1" style="width: 160px" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="payVisible = false">取消</el-button>
        <el-button type="warning" :loading="paying" @click="submitPay">确认收款</el-button>
      </template>
    </el-dialog>

    <!-- 退费 -->
    <el-dialog v-model="refundVisible" title="退费" width="420px" append-to-body>
      <div v-if="refundTarget" class="dlg-body">
        <p>确认将单号 <b>{{ refundTarget.charge_no }}</b> 退费？金额 ¥{{ Number(refundTarget.payable).toFixed(2) }}</p>
        <el-alert type="warning" :closable="false" show-icon title="退费仅冲销收费记录，不自动回补库存；如需退药请在处方作废时选择退回库存" />
        <el-input v-model="refundReason" placeholder="退费原因（选填）" style="margin-top: 12px" />
      </div>
      <template #footer>
        <el-button @click="refundVisible = false">取消</el-button>
        <el-button type="danger" :loading="refunding" @click="submitRefund">确认退费</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'
import type { Charge, ChargeStats } from '@/types'
import ReceiptDialog from '@/components/ReceiptDialog.vue'

const auth = useAuthStore()
const canWrite = computed(() => auth.can('billing:write'))

const methods = ['现金', '微信', '支付宝', '银行卡', '医保', '记账']
const charges = ref<Charge[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const stats = ref<ChargeStats>({
  paid_amount: 0, refunded_amount: 0, pending_amount: 0,
  paid_count: 0, refunded_count: 0, pending_count: 0, total_count: 0,
})
const statusFilter = ref('')
const kindFilter = ref('')
const patientFilter = ref('')
const dateRange = ref<[string, string] | null>(null)
const isMobile = ref(false)

const receiptVisible = ref(false)
const receiptCharge = ref<Charge | null>(null)

const payVisible = ref(false)
const payTarget = ref<Charge | null>(null)
const payMethod = ref('现金')
const payAmount = ref(0)
const paying = ref(false)

const refundVisible = ref(false)
const refundTarget = ref<Charge | null>(null)
const refundReason = ref('')
const refunding = ref(false)

function dateParams(): Record<string, string> {
  const p: Record<string, string> = {}
  if (dateRange.value?.[0]) p.start_date = dateRange.value[0]
  if (dateRange.value?.[1]) p.end_date = dateRange.value[1]
  return p
}

async function loadCharges(reset = false) {
  if (reset) page.value = 1
  try {
    const params: Record<string, any> = {
      page: page.value, page_size: pageSize.value, ...dateParams(),
    }
    if (statusFilter.value) params.status = statusFilter.value
    if (kindFilter.value) params.kind = kindFilter.value
    if (patientFilter.value) params.patient_name = patientFilter.value.trim()
    const res = await api.get<{ items: Charge[]; total: number }>('/billing/charges', { params })
    charges.value = res.items || []
    total.value = res.total || 0
  } catch { /* 拦截器已提示 */ }
}

async function loadStats() {
  try {
    stats.value = await api.get<ChargeStats>('/billing/charges/stats/summary', { params: dateParams() })
  } catch { /* 拦截器已提示 */ }
}

function loadAll() {
  loadCharges(true)
  loadStats()
}

function statusType(s: string): 'success' | 'warning' | 'danger' | 'info' {
  if (s === '已收费') return 'success'
  if (s === '待收费') return 'warning'
  if (s === '已退费') return 'danger'
  return 'info'
}

async function openReceipt(row: Charge) {
  try {
    // 详情接口带处方明细快照，用于打印项目清单
    receiptCharge.value = await api.get<Charge>(`/billing/charges/${row.id}`)
    receiptVisible.value = true
  } catch { /* 拦截器已提示 */ }
}

function openPay(row: Charge) {
  payTarget.value = row
  payMethod.value = '现金'
  payAmount.value = Number(row.payable || 0)
  payVisible.value = true
}

async function submitPay() {
  if (!payTarget.value?.id) return
  if (payAmount.value < Number(payTarget.value.payable || 0) - 1e-6) {
    ElMessage.warning('实收金额不能小于应付金额')
    return
  }
  paying.value = true
  try {
    await api.post(`/billing/charges/${payTarget.value.id}/pay`, {
      payment_method: payMethod.value, paid: payAmount.value,
    })
    ElMessage.success('收款成功')
    payVisible.value = false
    loadAll()
  } catch { /* 拦截器已提示 */ } finally {
    paying.value = false
  }
}

function openRefund(row: Charge) {
  refundTarget.value = row
  refundReason.value = ''
  refundVisible.value = true
}

async function submitRefund() {
  if (!refundTarget.value?.id) return
  refunding.value = true
  try {
    await api.post(`/billing/charges/${refundTarget.value.id}/refund`, { reason: refundReason.value })
    ElMessage.success('已退费')
    refundVisible.value = false
    loadAll()
  } catch { /* 拦截器已提示 */ } finally {
    refunding.value = false
  }
}

function updateViewport() {
  isMobile.value = window.innerWidth < 768
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  loadAll()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))
</script>

<style scoped lang="scss">
.billing-page {
  .main-card { :deep(.el-card__header) { padding: 14px 18px; } }
}

.stat-row { margin-bottom: 16px; }
.stat-card {
  border-radius: 10px; padding: 12px 14px; background: #faf7f3; border-left: 4px solid #d9a441;
  &__label { font-size: 12px; color: #8a7563; }
  &__value { font-size: 20px; font-weight: 700; color: #5b4636; margin-top: 4px; }
  &__sub { font-size: 12px; color: #a3917f; margin-top: 2px; }
  &.is-paid { border-left-color: #52c41a; }
  &.is-pending { border-left-color: #faad14; }
  &.is-refund { border-left-color: #f5222d; }
}

.tcm-filter { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; align-items: center; }
.filter-mini { width: 130px; }
.filter-search { width: 180px; }
.paid-amount { font-weight: 700; color: #c0392b; }
.bill-pager { margin-top: 14px; justify-content: flex-end; }

.dlg-body { font-size: 14px; line-height: 1.8; }
.dlg-payable { font-size: 15px; }

.bill-cards { display: flex; flex-direction: column; gap: 10px; }
.bill-card {
  border: 1px solid #eee2d5; border-radius: 8px; padding: 10px 12px; background: #fffdfb;
  &__head { display: flex; justify-content: space-between; align-items: center; }
  &__no { font-size: 12px; color: #8a7563; }
  &__line { font-size: 13px; margin-top: 4px; color: #5b4636; }
  &__ops { display: flex; gap: 8px; margin-top: 6px; border-top: 1px dashed #eee2d5; padding-top: 4px; }
}
</style>
