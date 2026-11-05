<template>
  <el-dialog
    :model-value="visible"
    title="收费"
    width="460px"
    append-to-body
    @update:model-value="$emit('update:visible', $event)"
  >
    <div v-if="prescription" class="charge-form">
      <!-- 已有在账收费单：直接展示结果与收据入口，不再允许开单 -->
      <div v-if="activeCharge" class="charge-result">
        <el-alert
          :type="activeCharge.status === '已收费' ? 'success' : 'warning'"
          :closable="false" show-icon
          :title="activeCharge.status === '已收费' ? '该处方已收费，请勿重复收款' : '该处方已有待收款单'"
        >
          <template #default>
            单号 {{ activeCharge.charge_no }} · {{ activeCharge.status }} ·
            实收 ¥{{ Number(activeCharge.paid || 0).toFixed(2) }}
          </template>
        </el-alert>
        <el-button type="primary" plain size="small" style="margin-top: 12px" @click="openReceipt">查看收据</el-button>
      </div>

      <template v-else>
        <div v-if="checking" class="charge-checking">正在核对该处方收费状态…</div>
        <template v-else>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="处方">{{ prescription.formula_name || '自拟方' }}</el-descriptions-item>
            <el-descriptions-item label="患者">{{ prescription.patient_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="应收原价">¥{{ Number(prescription.total_price || 0).toFixed(2) }}</el-descriptions-item>
          </el-descriptions>

          <el-form label-width="84px" class="charge-fields">
            <el-form-item label="减免">
              <el-input-number v-model="discount" :min="0" :precision="2" :step="1" style="width: 160px" />
            </el-form-item>
            <el-form-item label="实收应付">
              <span class="payable">¥{{ payable.toFixed(2) }}</span>
            </el-form-item>
            <el-form-item label="收款方式">
              <el-select v-model="method" style="width: 160px">
                <el-option v-for="m in methods" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>
            <el-form-item label="实收金额">
              <el-input-number v-model="paid" :min="0" :precision="2" :step="1" style="width: 160px" />
            </el-form-item>
          </el-form>
        </template>
      </template>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">{{ activeCharge ? '完成' : '取消' }}</el-button>
      <el-button
        v-if="!activeCharge" type="warning"
        :loading="charging" :disabled="checking || submitted || checkFailed" @click="submit"
      >确认收费</el-button>
    </template>

    <ReceiptDialog v-model:visible="receiptVisible" :charge="createdCharge" />
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import type { Charge, Prescription } from '@/types'
import ReceiptDialog from '@/components/ReceiptDialog.vue'

const props = defineProps<{ visible: boolean; prescription: Prescription | null }>()
const emit = defineEmits<{ 'update:visible': [boolean]; charged: [] }>()

const methods = ['现金', '微信', '支付宝', '银行卡', '医保', '记账']
const discount = ref(0)
const method = ref('现金')
const paid = ref(0)
const charging = ref(false)
const submitted = ref(false)       // 本次已成功提交，禁止再次点击
const checking = ref(false)
const checkFailed = ref(false)  // 在账查询失败时不允许开单，避免重复收现金
const existingCharge = ref<Charge | null>(null)
const createdCharge = ref<Charge | null>(null)
const receiptVisible = ref(false)

// 结果视图依据：本次新建的单，或打开时查到的在账单
const activeCharge = computed(() => createdCharge.value || existingCharge.value)

const amount = computed(() => Number(props.prescription?.total_price || 0))
const payable = computed(() => Math.max(0, amount.value - discount.value))

// 打开时先查该处方是否已有在账收费单，避免重复开单/重复收现金
watch(() => props.visible, async (v) => {
  if (!v || !props.prescription?.id) return
  discount.value = 0
  method.value = '现金'
  paid.value = 0
  submitted.value = false
  checkFailed.value = false
  createdCharge.value = null
  existingCharge.value = null
  receiptVisible.value = false
  checking.value = true
  try {
    const res = await api.get<{ items: Charge[] }>('/billing/charges', {
      params: { prescription_id: props.prescription.id, page: 1, page_size: 50 },
    })
    existingCharge.value = (res.items || []).find(
      c => c.status === '待收费' || c.status === '已收费'
    ) || null
  } catch {
    existingCharge.value = null
    checkFailed.value = true
    ElMessage.error('无法确认是否已有在账收费单，请稍后重试')
  } finally {
    checking.value = false
    // 下一次 tick 才能拿到 payable（依赖 discount 已置 0）
    setTimeout(() => { paid.value = payable.value }, 0)
  }
})

async function submit() {
  if (!props.prescription?.id || submitted.value || activeCharge.value || checkFailed.value) return
  if (paid.value < payable.value - 1e-6) {
    ElMessage.warning('实收金额不能小于应付金额')
    return
  }
  charging.value = true
  submitted.value = true
  try {
    const c = await api.post<Charge>('/billing/charges', {
      prescription_id: props.prescription.id,
      discount: discount.value,
      payment_method: method.value,
      paid: paid.value,
    })
    // 收据需要处方明细快照：复用传入的处方对象
    c.prescription = props.prescription as any
    createdCharge.value = c
    receiptVisible.value = true
    ElMessage.success('收费成功')
    emit('charged')
  } catch {
    submitted.value = false  // 失败允许重试
  } finally {
    charging.value = false
  }
}

function openReceipt() {
  const c = activeCharge.value
  if (!c) return
  if (!createdCharge.value) {
    createdCharge.value = { ...c, prescription: props.prescription } as Charge
  }
  receiptVisible.value = true
}
</script>

<style scoped lang="scss">
.charge-fields { margin-top: 12px; }
.payable { font-size: 16px; font-weight: 700; color: #c0392b; }
.charge-checking { padding: 16px 0; color: #8a8170; font-size: 13px; }
.charge-result { padding: 4px 0; }
</style>
