<template>
  <div class="acupoint-list">
    <!-- 工具栏：搜索 + 来源 + 分部 + 查询 -->
    <div class="toolbar">
      <div class="left">
        <el-input v-model="filter.search" placeholder="搜索穴名" clearable style="width: 200px" @keyup.enter="loadAcupoints" @clear="loadAcupoints" />
        <el-select v-model="filter.source" placeholder="来源" clearable style="width: 150px" @change="loadAcupoints">
          <el-option label="全部来源" value="" />
          <el-option v-for="opt in dimOptions('source')" :key="opt.value" :label="opt.label" :value="opt.value">
            <span v-if="opt.color" :style="{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: opt.color, marginRight: '6px', verticalAlign: 'middle' }"></span>
            <span>{{ opt.label }}</span>
            <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
              <span class="opt-hint-dot"></span>
            </el-tooltip>
          </el-option>
        </el-select>
        <el-select v-model="filter.meridian" placeholder="归经" clearable style="width: 160px" @change="loadAcupoints">
          <el-option label="全部归经" value="" />
          <el-option v-for="opt in dimOptions('meridian')" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-select v-model="filter.region" placeholder="部位" clearable style="width: 130px" @change="loadAcupoints">
          <el-option label="全部部位" value="" />
          <el-option v-for="opt in dimOptions('region')" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-button type="primary" @click="loadAcupoints">查询</el-button>
      </div>
      <div class="right">
        <el-button type="success" @click="openCreate">新增穴位</el-button>
        <el-button @click="exportData">导出</el-button>
        <el-button @click="importVisible = true">导入</el-button>
      </div>
    </div>

    <!-- 桌面端表格：7 列（穴名 / 来源 / 分部 / 类型 / 定位 / 功效 / 操作） -->
    <el-card class="table-card" shadow="never">
      <el-table :data="acupoints" v-loading="loading" border stripe>
        <el-table-column prop="name" label="穴名" width="110" fixed />
        <el-table-column label="来源" width="130">
          <template #default="{ row }"><span class="src-pill" :style="tagStyle('source', row.source)">{{ row.source || '—' }}</span></template>
        </el-table-column>
        <el-table-column label="归经" min-width="150">
          <template #default="{ row }"><span class="src-pill" :style="tagStyle('meridian', row.meridian)">{{ row.meridian || '—' }}</span></template>
        </el-table-column>
        <el-table-column label="部位" min-width="90">
          <template #default="{ row }"><span class="src-pill" :style="tagStyle('region', row.region)">{{ row.region || '—' }}</span></template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }"><span class="src-pill" :style="tagStyle('point_type', row.point_type)">{{ row.point_type || '—' }}</span></template>
        </el-table-column>
        <el-table-column prop="location" label="定位" min-width="240" show-overflow-tooltip />
        <el-table-column prop="efficacy" label="功效" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="summary">共 {{ acupoints.length }} 个穴位（维度均可字典自定义）</div>
    </el-card>

    <!-- 移动端卡片 -->
    <div class="mobile-cards">
      <el-card v-for="a in acupoints" :key="a.id" class="m-card" shadow="never">
        <div class="m-head">
          <span class="m-name">{{ a.name }}</span>
          <span class="src-pill" :style="tagStyle('source', a.source)">{{ a.source || '—' }}</span>
        </div>
        <div class="m-row"><span class="m-label">归经</span><span class="m-val">{{ a.meridian || '—' }}</span></div>
        <div class="m-row"><span class="m-label">部位</span><span class="m-val">{{ a.region || '—' }}</span></div>
        <div class="m-row"><span class="m-label">类型</span><span class="m-val">{{ a.point_type || '—' }}</span></div>
        <div class="m-row"><span class="m-label">定位</span><span class="m-val">{{ a.location || '—' }}</span></div>
        <div class="m-row"><span class="m-label">功效</span><span class="m-val">{{ a.efficacy || '—' }}</span></div>
        <div class="m-actions">
          <el-button size="small" @click="openEdit(a)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="del(a)">删除</el-button>
        </div>
      </el-card>
    </div>

    <!-- 新增/编辑弹窗：4 个字典下拉 + 定位/功效/主治/刺法/备注 -->
    <el-dialog :title="editId ? '编辑穴位' : '新增穴位'" v-model="dialogVisible" width="560px">
      <el-form :model="form" label-width="70px">
        <el-form-item label="穴名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="来源">
          <el-select v-model="form.source" filterable allow-create default-first-option placeholder="选择或录入" style="width:100%">
            <el-option v-for="opt in dimOptions('source')" :key="opt.value" :label="opt.label" :value="opt.value">
            <span v-if="opt.color" :style="{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: opt.color, marginRight: '6px', verticalAlign: 'middle' }"></span>
            <span>{{ opt.label }}</span>
            <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
              <span class="opt-hint-dot"></span>
            </el-tooltip>
          </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="归经">
          <el-select v-model="form.meridian" filterable allow-create default-first-option placeholder="选择或录入" style="width:100%">
            <el-option v-for="opt in dimOptions('meridian')" :key="opt.value" :label="opt.label" :value="opt.value">
              <span v-if="opt.color" :style="{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: opt.color, marginRight: '6px', verticalAlign: 'middle' }"></span>
              <span>{{ opt.label }}</span>
              <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
                <span class="opt-hint-dot"></span>
              </el-tooltip>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="部位">
          <el-select v-model="form.region" filterable allow-create default-first-option placeholder="选择或录入" style="width:100%">
            <el-option v-for="opt in dimOptions('region')" :key="opt.value" :label="opt.label" :value="opt.value">
              <span v-if="opt.color" :style="{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: opt.color, marginRight: '6px', verticalAlign: 'middle' }"></span>
              <span>{{ opt.label }}</span>
              <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
                <span class="opt-hint-dot"></span>
              </el-tooltip>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.point_type" filterable allow-create default-first-option placeholder="选择或录入" style="width:100%">
            <el-option v-for="opt in dimOptions('point_type')" :key="opt.value" :label="opt.label" :value="opt.value">
              <span v-if="opt.color" :style="{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: opt.color, marginRight: '6px', verticalAlign: 'middle' }"></span>
              <span>{{ opt.label }}</span>
              <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
                <span class="opt-hint-dot"></span>
              </el-tooltip>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="定位"><el-input v-model="form.location" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="功效"><el-input v-model="form.efficacy" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="主治"><el-input v-model="form.indications" type="textarea" :rows="2" placeholder="主治病症" /></el-form-item>
        <el-form-item label="刺法"><el-input v-model="form.needling_method" type="textarea" :rows="2" placeholder="针刺方法/操作要点" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog title="导入穴位" v-model="importVisible" width="480px">
      <el-input v-model="importText" type="textarea" :rows="10" placeholder="粘贴 JSON 数组" />
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" @click="importData">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

interface Acupoint {
  id: number
  name: string
  meridian?: string | null
  location?: string | null
  efficacy?: string | null
  point_type?: string | null
  notes?: string | null
  source?: string | null
  region?: string | null
  indications?: string | null
  needling_method?: string | null
  is_active: boolean
  created_at?: string | null
}

const acupoints = ref<Acupoint[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const importVisible = ref(false)
const importText = ref('')
const editId = ref<number | null>(null)

const filter = reactive({ search: '', source: '', meridian: '', region: '' })

// 字典维度选项（来自 /acupoints/tags/meta）
interface TagOption {
  value: string
  label: string
  description: string
  color: string
}
interface TagDimension {
  label: string
  multi: boolean
  options: TagOption[]
}
interface TagMeta {
  dimensions: { [key: string]: TagDimension }
}
const meta = ref<TagMeta>({
  dimensions: {
    source: { label: '来源', multi: false, options: [] },
    meridian: { label: '归经', multi: false, options: [] },
    region: { label: '部位', multi: false, options: [] },
    point_type: { label: '类型', multi: false, options: [] },
  },
})
function dimOptions(key: string): TagOption[] {
  return meta.value.dimensions[key]?.options || []
}

const FALLBACK_TAG_INK = '#606266'
const FALLBACK_TAG_BG = '#f5f7fa'
const FALLBACK_TAG_BORDER = '#dcdfe6'

function readableInk(hex: string): string {
  const c = (hex || '').replace('#', '')
  if (c.length < 6) return '#333333'
  const r = parseInt(c.slice(0, 2), 16)
  const g = parseInt(c.slice(2, 4), 16)
  const b = parseInt(c.slice(4, 6), 16)
  const L = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return L > 0.6 ? '#333333' : '#ffffff'
}

function tagColor(dim: string, value: string | null | undefined): string {
  if (!value) return ''
  const opt = dimOptions(dim).find((o) => o.value === value)
  return opt?.color || ''
}

function tagStyle(dim: string, value: string | null | undefined): Record<string, string> {
  const color = tagColor(dim, value)
  if (!color) {
    return { color: FALLBACK_TAG_INK, backgroundColor: FALLBACK_TAG_BG, borderColor: FALLBACK_TAG_BORDER }
  }
  const ink = readableInk(color)
  return { color: ink, backgroundColor: color, borderColor: ink }
}

const form = reactive({
  name: '', meridian: '', location: '', efficacy: '', point_type: '', notes: '',
  source: '', region: '', indications: '', needling_method: '',
})

async function loadMeta() {
  try {
    const data = await api.get('/acupoints/tags/meta')
    if (data?.dimensions) meta.value = data
  } catch (e) { /* 回退到默认空词表 */ }
}

async function loadAcupoints() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filter.search) params.search = filter.search
    if (filter.source) params.source = filter.source
    if (filter.meridian) params.meridian = filter.meridian
    if (filter.region) params.region = filter.region
    const data = await api.get('/acupoints', { params })
    acupoints.value = data
  } catch (e) {
    ElMessage.error('加载穴位失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editId.value = null
  Object.assign(form, { name: '', meridian: '', location: '', efficacy: '', point_type: '', notes: '', source: '', region: '', indications: '', needling_method: '' })
  dialogVisible.value = true
}

function openEdit(row: Acupoint) {
  editId.value = row.id
  Object.assign(form, {
    name: row.name, meridian: row.meridian || '', location: row.location || '',
    efficacy: row.efficacy || '', point_type: row.point_type || '', notes: row.notes || '',
    source: row.source || '', region: row.region || '', indications: row.indications || '',
    needling_method: row.needling_method || '',
  })
  dialogVisible.value = true
}

async function save() {
  const payload = { ...form }
  try {
    if (editId.value) {
      await api.put(`/acupoints/${editId.value}`, payload)
      ElMessage.success('已更新')
    } else {
      await api.post('/acupoints', payload)
      ElMessage.success('已新增')
    }
    dialogVisible.value = false
    loadAcupoints()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
}

async function del(row: Acupoint) {
  try {
    await ElMessageBox.confirm(`确认删除穴位「${row.name}」？`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await api.delete(`/acupoints/${row.id}`)
    ElMessage.success('已删除')
    loadAcupoints()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

function exportData() {
  const blob = new Blob([JSON.stringify(acupoints.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'acupoints.json'
  a.click()
  URL.revokeObjectURL(url)
}

async function importData() {
  try {
    const arr = JSON.parse(importText.value)
    if (!Array.isArray(arr)) throw new Error('格式错误')
    for (const item of arr) {
      await api.post('/acupoints', item)
    }
    ElMessage.success(`已导入 ${arr.length} 条`)
    importVisible.value = false
    importText.value = ''
    loadAcupoints()
  } catch (e: any) {
    ElMessage.error(e?.message || '导入失败')
  }
}

onMounted(() => {
  loadMeta()
  loadAcupoints()
})
</script>

<style scoped>
.acupoint-list { padding: 8px 0; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }
.toolbar .left { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.table-card { margin-bottom: 12px; }
.summary { margin-top: 10px; font-size: 12px; color: #909399; }
.src-pill { display: inline-block; padding: 0 8px; font-size: 12px; line-height: 20px; border: 1px solid transparent; border-radius: 10px; white-space: nowrap; }

/* 移动端卡片 */
.mobile-cards { display: none; }
.m-card { margin-bottom: 10px; }
.m-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.m-name { font-weight: 600; font-size: 15px; }
.m-row { display: flex; font-size: 13px; margin: 2px 0; }
.m-label { width: 42px; color: #909399; flex: none; }
.m-val { color: #303133; flex: 1; }
.m-actions { margin-top: 8px; display: flex; gap: 8px; }

@media (max-width: 768px) {
  .table-card { display: none; }
  .mobile-cards { display: block; }
}
</style>