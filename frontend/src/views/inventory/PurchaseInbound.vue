<template>
  <div class="purchase-inbound">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <span>🛒 采购入库</span>
          <el-button type="primary" size="small" @click="openCreate" v-if="editable"><el-icon><Plus /></el-icon> 新建采购单</el-button>
        </div>
      </template>

      <el-table :data="orders" stripe style="width:100%" empty-text="暂无采购单">
        <el-table-column type="expand">
          <template #default="{ row }">
            <el-table :data="row.items || []" size="small" :border="false">
              <el-table-column prop="item_name" label="物品" min-width="120" />
              <el-table-column prop="batch_number" label="批号" width="120" />
              <el-table-column label="数量" width="90"><template #default="{ row }">{{ row.quantity }} {{ row.unit }}</template></el-table-column>
              <el-table-column label="进价" width="100"><template #default="{ row }">¥{{ Number(row.unit_price).toFixed(2) }}</template></el-table-column>
              <el-table-column label="金额" width="110"><template #default="{ row }">¥{{ Number(row.amount).toFixed(2) }}</template></el-table-column>
              <el-table-column prop="expiry_date" label="有效期" width="120" />
            </el-table>
          </template>
        </el-table-column>
        <el-table-column prop="order_no" label="单号" width="170" />
        <el-table-column prop="supplier_name" label="供应商" min-width="120" />
        <el-table-column prop="order_date" label="采购日期" width="120" />
        <el-table-column label="总金额" width="130"><template #default="{ row }">¥{{ Number(row.total_amount).toFixed(2) }}</template></el-table-column>
        <el-table-column prop="operator" label="操作人" width="100" />
        <el-table-column prop="note" label="备注" min-width="120" show-overflow-tooltip />
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        style="margin-top:14px;justify-content:center;"
        layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" :current-page="page"
        @current-change="(p: number) => { page = p; load() }"
      />
    </el-card>

    <el-dialog v-model="visible" title="🛒 新建采购单" width="760px" destroy-on-close>
      <el-form :model="form" label-width="84px" :rules="rules" ref="formRef">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="供应商" prop="supplier_id">
              <el-select v-model="form.supplier_id" filterable clearable placeholder="选择供应商" style="width:100%">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采购日期">
              <el-date-picker v-model="form.order_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">采购明细</el-divider>
        <div v-for="(it, idx) in form.items" :key="idx" class="po-item">
          <el-select v-model="it.item_id" filterable placeholder="物品" style="width:200px" @change="onItemPick(it)">
            <el-option v-for="i in items" :key="i.id" :label="`${i.name}（${i.unit}）`" :value="i.id" />
          </el-select>
          <el-input v-model="it.batch_number" placeholder="批号" style="width:120px" />
          <el-input-number v-model="it.quantity" :min="0.01" :precision="2" controls-position="right" style="width:130px" />
          <el-input-number v-model="it.unit_price" :min="0" :precision="2" controls-position="right" style="width:130px" />
          <el-date-picker v-model="it.expiry_date" type="date" value-format="YYYY-MM-DD" placeholder="效期" style="width:150px" />
          <el-button link type="danger" @click="removeItem(idx)"><el-icon><Delete /></el-icon></el-button>
        </div>
        <el-button link type="primary" @click="addItem"><el-icon><Plus /></el-icon> 添加明细</el-button>
        <div class="po-total">采购总额：<b>¥{{ poTotal.toFixed(2) }}</b></div>
        <el-form-item label="备注" style="margin-top:8px"><el-input v-model="form.note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="submit" :loading="submitting">提交入库</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)
const orders = ref<any[]>([])
const suppliers = ref<any[]>([])
const items = ref<any[]>([])
const visible = ref(false)
const submitting = ref(false)
const formRef = ref()
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const form = reactive({ supplier_id: null as number | null, order_date: '', note: '', items: [] as any[] })
const rules = { supplier_id: [{ required: false }] }
const poTotal = computed(() => form.items.reduce((s: number, it: any) => s + (Number(it.quantity) || 0) * (Number(it.unit_price) || 0), 0))

async function load() {
  try {
    const res = (await api.get('/stock/purchases', { params: { page: page.value, page_size: pageSize.value } }) as any) || []
    // 兼容：分页接口返回 {items,total,...}；旧全量接口返回数组
    if (Array.isArray(res)) { orders.value = res; total.value = res.length }
    else { orders.value = res.items || []; total.value = res.total || 0 }
    suppliers.value = (await api.get('/stock/suppliers') as any) || []
    items.value = (await api.get('/stock/items') as any) || []
  } catch (e: any) { ElMessage.error('加载失败：' + (e?.response?.data?.detail || e?.message)) }
}
function addItem() { form.items.push({ item_id: null, batch_number: '', quantity: 1, unit_price: null, expiry_date: '' }) }
function removeItem(idx: number) { form.items.splice(idx, 1) }
function onItemPick(it: any) {
  const i = items.value.find((x: any) => x.id === it.item_id)
  if (i && it.unit_price == null) it.unit_price = i.sell_price ? Number(i.sell_price) * 0.6 : null
}
function openCreate() {
  form.supplier_id = null; form.order_date = new Date().toISOString().slice(0, 10)
  form.note = ''; form.items = []
  visible.value = true
}
async function submit() {
  if (!form.items.length) { ElMessage.warning('请至少添加一条明细'); return }
  if (form.items.some((it: any) => !it.item_id || !(it.quantity > 0) || !(it.unit_price >= 0))) {
    ElMessage.warning('明细需填写物品、数量与进价'); return
  }
  submitting.value = true
  try {
    await api.post('/stock/purchases', { supplier_id: form.supplier_id, order_date: form.order_date, note: form.note, items: form.items })
    ElMessage.success('采购入库成功')
    visible.value = false
    page.value = 1
    load()
  } catch (e: any) { ElMessage.error('提交失败：' + (e?.response?.data?.detail || e?.message)) }
  finally { submitting.value = false }
}

onMounted(load)
</script>

<style scoped lang="scss">
.purchase-inbound {
  .po-item { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
  .po-total { margin: 8px 0; font-size: 15px; }
}
</style>
