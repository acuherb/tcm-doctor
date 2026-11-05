<template>
  <el-dialog
    :model-value="visible"
    title="收费"
    width="460px"
    append-to-body
    @update:model-value="$emit('update:visible', $event)"
  >
    <div v-if="prescription" class="charge-form">
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
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="warning" :loading="charging" @click="submit">确认收费</el-button>
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
const createdCharge = ref<Charge | null>(null)
const receiptVisible = ref(false)

const amount = computed(() => Number(props.prescription?.total_price || 0))
const payable = computed(() => Math.max(0, amount.value - discount.value))

// 打开时按应付初始化「实收金额」
watch(() => props.visible, (v) => {
  if (v) {
    discount.value = 0
    method.value = '现金'
    paid.value = 0
    createdCharge.value = null
    // 下一次 tick 才能拿到 payable（依赖 discount 已置 0）
    setTimeout(() => { paid.value = payable.value }, 0)
  }
})

async function submit() {
  if (!props.prescription?.id) return
  if (paid.value < payable.value - 1e-6) {
    ElMessage.warning('实收金额不能小于应付金额')
    return
  }
  charging.value = true
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
    /* 拦截器已提示 */
  } finally {
    charging.value = false
  }
}
</script>

<style scoped lang="scss">
.charge-fields { margin-top: 12px; }
.payable { font-size: 16px; font-weight: 700; color: #c0392b; }
</style>
