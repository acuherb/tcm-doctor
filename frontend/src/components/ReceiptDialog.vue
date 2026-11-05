<template>
  <el-dialog
    :model-value="visible"
    title="收费收据"
    width="420px"
    append-to-body
    @update:model-value="$emit('update:visible', $event)"
  >
    <div id="receipt-print" class="receipt">
      <div class="receipt__head">
        <div class="receipt__clinic">{{ clinicName || '中医诊所' }}</div>
        <div class="receipt__title">收 费 收 据</div>
      </div>
      <div class="receipt__meta">
        <span>单号：{{ charge?.charge_no }}</span>
        <span>{{ payTime }}</span>
      </div>
      <div class="receipt__patient">患者：{{ charge?.patient_name || '-' }}</div>
      <div v-if="charge?.status === '已退费' || charge?.status === '已取消'" class="receipt__void">
        本单{{ charge?.status }}（{{ charge?.refund_reason || charge?.cancel_reason || '无原因' }}），金额已冲销
      </div>

      <table class="receipt__table" v-if="charge?.prescription">
        <tr>
          <th>项目</th>
          <th class="num">金额</th>
        </tr>
        <tr v-for="it in herbLines" :key="'h' + it.id">
          <td>{{ it.label }}</td>
          <td class="num">{{ it.price }}</td>
        </tr>
        <tr v-if="charge.prescription.acupuncture_fee">
          <td>针灸治疗费</td>
          <td class="num">{{ Number(charge.prescription.acupuncture_fee).toFixed(2) }}</td>
        </tr>
      </table>
      <div v-else class="receipt__plain">处方明细不可用</div>

      <div class="receipt__sum">
        <div><span>应收</span><b>¥{{ Number(charge?.amount || 0).toFixed(2) }}</b></div>
        <div v-if="charge?.discount"><span>减免</span><b>-¥{{ Number(charge.discount).toFixed(2) }}</b></div>
        <div><span>应付</span><b>¥{{ Number(charge?.payable || 0).toFixed(2) }}</b></div>
        <div><span>实收</span><b>¥{{ Number(charge?.paid || 0).toFixed(2) }}</b></div>
        <div v-if="Number(charge?.overpaid || 0) > 0">
          <span>多收未找零</span><b>¥{{ Number(charge.overpaid).toFixed(2) }}</b>
        </div>
        <div v-if="Number(charge?.refund_amount || 0) > 0">
          <span>已退</span><b>-¥{{ Number(charge.refund_amount).toFixed(2) }}</b>
        </div>
        <div v-if="Number(charge?.refund_amount || 0) > 0">
          <span>净收</span><b>¥{{ Number(charge?.net_paid || 0).toFixed(2) }}</b>
        </div>
      </div>

      <div class="receipt__foot">
        <span>收款方式：{{ charge?.payment_method || '-' }}</span>
        <span>收银员：{{ charge?.cashier_name || '-' }}</span>
      </div>
      <div class="receipt__note" v-if="charge?.note">备注：{{ charge.note }}</div>
      <div class="receipt__sign">签名：____________</div>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
      <el-button type="primary" @click="doPrint">打印收据</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import api from '@/utils/api'
import type { Charge } from '@/types'

const props = defineProps<{ visible: boolean; charge: Charge | null }>()
defineEmits<{ 'update:visible': [boolean] }>()

const clinicName = ref('')
api.get<{ clinic_name?: string }>('/config', { silent: true })
  .then((r) => { clinicName.value = r.clinic_name || '' })
  .catch(() => {})

const payTime = computed(() => {
  const t = props.charge?.paid_at || props.charge?.created_at
  return t ? String(t).replace('T', ' ').slice(0, 19) : '-'
})

const herbLines = computed(() => {
  const p = props.charge?.prescription
  if (!p) return []
  const lines: Array<{ id: number; label: string; price: string }> = []
  for (const it of (p.items || [])) {
    lines.push({
      id: it.id ?? Math.random(),
      label: `${it.herb_name} ${it.dose ?? ''}${it.special_method ? '(' + it.special_method + ')' : ''}`,
      price: '—',
    })
  }
  for (const a of (p.acupoints || [])) {
    lines.push({ id: (a.id ?? Math.random()) + 100000, label: `配穴：${a.acupoint_name}`, price: '—' })
  }
  for (const j of (p.injections || [])) {
    lines.push({ id: (j.id ?? Math.random()) + 200000, label: `针剂：${j.drug_name}`, price: '—' })
  }
  return lines
})

function doPrint() {
  window.print()
}
</script>

<style scoped lang="scss">
.receipt {
  font-family: 'Courier New', monospace;
  color: #222;
  padding: 8px 4px;

  &__head {
    text-align: center;
    margin-bottom: 8px;
  }
  &__clinic { font-size: 16px; font-weight: 700; }
  &__title { font-size: 14px; letter-spacing: 4px; margin-top: 2px; }
  &__meta, &__patient {
    display: flex; justify-content: space-between;
    font-size: 12px; margin: 4px 0;
  }
  &__table {
    width: 100%; border-collapse: collapse; font-size: 12px; margin: 6px 0;
    th, td { border-bottom: 1px dashed #ccc; padding: 3px 2px; text-align: left; }
    .num { text-align: right; width: 70px; }
  }
  &__sum {
    font-size: 13px; margin-top: 6px;
    div { display: flex; justify-content: space-between; padding: 2px 0; }
    b { font-weight: 700; }
  }
  &__foot { font-size: 12px; display: flex; justify-content: space-between; margin-top: 6px; }
  &__note { font-size: 12px; margin-top: 4px; }
  &__sign { font-size: 12px; margin-top: 14px; text-align: right; }
  &__plain { font-size: 12px; color: #999; }
  &__void {
    font-size: 12px; color: #c0392b; border: 1px dashed #c0392b;
    padding: 4px 6px; margin: 6px 0; text-align: center;
  }
}
</style>

<!-- 打印时仅保留收据区域 -->
<style lang="scss">
@media print {
  body * { visibility: hidden !important; }
  #receipt-print, #receipt-print * { visibility: visible !important; }
  #receipt-print {
    position: absolute; left: 0; top: 0; width: 100%;
    box-shadow: none !important; border: none !important;
  }
  .el-overlay, .el-dialog__header, .el-dialog__footer { display: none !important; }
}
</style>
