<template>
  <div class="acupoint-list">
    <el-card class="main-card" shadow="never">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">🪡</span>
            <span class="tcm-head__text">针灸穴位</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ acupoints.length }} 个</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-button v-if="editable" @click="triggerImport">
              <el-icon><Upload /></el-icon>导入
            </el-button>
            <el-button v-if="editable" @click="exportData">
              <el-icon><Download /></el-icon>导出
            </el-button>
            <el-button v-if="editable" type="primary" @click="openCreate">
              <el-icon><Plus /></el-icon> 新增穴位
            </el-button>
            <input ref="fileInput" type="file" accept=".json,application/json" style="display:none" @change="onImportFile" />
          </div>
        </div>
      </template>

      <!-- 筛选栏 -->
      <div class="tcm-filter">
        <el-input v-model="filter.search" placeholder="按穴名搜索" clearable class="filter-search" @keyup.enter="loadAcupoints" @clear="loadAcupoints">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="filter.source" placeholder="全部来源" clearable class="filter-sel" @change="loadAcupoints">
          <el-option label="全部来源" value="" />
          <el-option v-for="opt in dimOptions('source')" :key="opt.value" :label="opt.label" :value="opt.value">
            <div class="term-opt">
              <span class="opt-dot" :style="{ backgroundColor: opt.color || '#909399' }"></span>
              <span class="term-name">{{ opt.label }}</span>
              <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
                <span class="opt-hint-dot"></span>
              </el-tooltip>
            </div>
          </el-option>
        </el-select>
        <el-select v-model="filter.meridian" placeholder="全部归经" clearable class="filter-sel" @change="loadAcupoints">
          <el-option label="全部归经" value="" />
          <el-option v-for="opt in dimOptions('meridian')" :key="opt.value" :label="opt.label" :value="opt.value">
            <div class="term-opt">
              <span class="opt-dot" :style="{ backgroundColor: opt.color || '#909399' }"></span>
              <span class="term-name">{{ opt.label }}</span>
              <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
                <span class="opt-hint-dot"></span>
              </el-tooltip>
            </div>
          </el-option>
        </el-select>
        <el-select v-model="filter.region" placeholder="全部部位" clearable class="filter-sel" @change="loadAcupoints">
          <el-option label="全部部位" value="" />
          <el-option v-for="opt in dimOptions('region')" :key="opt.value" :label="opt.label" :value="opt.value">
            <div class="term-opt">
              <span class="opt-dot" :style="{ backgroundColor: opt.color || '#909399' }"></span>
              <span class="term-name">{{ opt.label }}</span>
              <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
                <span class="opt-hint-dot"></span>
              </el-tooltip>
            </div>
          </el-option>
        </el-select>
        <div class="filter-actions">
          <el-button type="primary" @click="loadAcupoints">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
      </div>

      <!-- 桌面端表格：穴名 / 来源 / 归经 / 部位 / 类型 / 定位 / 功效 / 操作，拖动边框可调列宽 -->
      <el-table v-if="!isMobile" :data="acupoints" v-loading="loading" class="tcm-table" border>
        <el-table-column prop="name" label="穴名" width="100" fixed />
        <el-table-column label="来源" width="108">
          <template #default="{ row }"><span class="src-pill" :style="tagStyle('source', row.source)">{{ row.source || '—' }}</span></template>
        </el-table-column>
        <el-table-column label="归经" width="132">
          <template #default="{ row }"><span class="src-pill" :style="tagStyle('meridian', row.meridian)">{{ row.meridian || '—' }}</span></template>
        </el-table-column>
        <el-table-column label="部位" width="78">
          <template #default="{ row }"><span class="src-pill" :style="tagStyle('region', row.region)">{{ row.region || '—' }}</span></template>
        </el-table-column>
        <el-table-column label="类型" width="150">
          <template #default="{ row }"><span class="src-pill" :style="tagStyle('point_type', row.point_type)">{{ row.point_type || '—' }}</span></template>
        </el-table-column>
        <el-table-column prop="location" label="定位" min-width="260" show-overflow-tooltip />
        <el-table-column prop="efficacy" label="功效" min-width="240" show-overflow-tooltip />
        <el-table-column v-if="editable" label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!isMobile" class="summary">共 {{ acupoints.length }} 个穴位（维度均可字典自定义）</div>
    </el-card>

    <!-- 移动端卡片 -->
    <div v-if="isMobile" class="mobile-cards">
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
        <div class="m-actions" v-if="editable">
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
              <div class="term-opt">
                <span class="opt-dot" :style="{ backgroundColor: opt.color || '#909399' }"></span>
                <span class="term-name">{{ opt.label }}</span>
                <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
                  <span class="opt-hint-dot"></span>
                </el-tooltip>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="归经">
          <el-select v-model="form.meridian" filterable allow-create default-first-option placeholder="选择或录入" style="width:100%">
            <el-option v-for="opt in dimOptions('meridian')" :key="opt.value" :label="opt.label" :value="opt.value">
              <div class="term-opt">
                <span class="opt-dot" :style="{ backgroundColor: opt.color || '#909399' }"></span>
                <span class="term-name">{{ opt.label }}</span>
                <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
                  <span class="opt-hint-dot"></span>
                </el-tooltip>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="部位">
          <el-select v-model="form.region" filterable allow-create default-first-option placeholder="选择或录入" style="width:100%">
            <el-option v-for="opt in dimOptions('region')" :key="opt.value" :label="opt.label" :value="opt.value">
              <div class="term-opt">
                <span class="opt-dot" :style="{ backgroundColor: opt.color || '#909399' }"></span>
                <span class="term-name">{{ opt.label }}</span>
                <el-tooltip v-if="opt.description" :content="opt.description" placement="right" :teleported="true">
                  <span class="opt-hint-dot"></span>
                </el-tooltip>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-input v-model="form.point_type" placeholder="如 井穴·木 / 荥穴·火 / 原穴" />
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

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { errMsg } from '@/utils/api'
import { fileTimestamp } from '@/utils/datetime'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const editable = computed(() => auth.canWrite('acupoints'))

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
const fileInput = ref<HTMLInputElement | null>(null)
const editId = ref<number | null>(null)

const filter = reactive({ search: '', source: '', meridian: '', region: '' })

// 重置筛选条件并重新加载（供模板「重置」按钮调用）
function resetFilters() {
  filter.search = ''
  filter.source = ''
  filter.meridian = ''
  filter.region = ''
  loadAcupoints()
}

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

const POINT_TYPE_DEFAULT_COLORS: Record<string, string> = {
  '井穴': '#aed6f1', '荥穴': '#5dade2', '输穴': '#2e86c1', '经穴': '#1f618d', '合穴': '#154360',
  '原穴': '#8e6bb0', '络穴': '#16a085', '郄穴': '#a93226', '募穴': '#d68910', '背俞穴': '#7d6608',
  '八会穴': '#6c3483', '八脉交会穴': '#5b2c6f', '下合穴': '#21618c', '经外奇穴': '#7f8c8d',
  '特效穴': '#b9770e', '常用要穴': '#af601a',
}
const FIVE_ELEMENT_COLORS: Record<string, string> = {
  '木': '#2e9e5b', '火': '#d9434e', '土': '#e0a82e', '金': '#aab8c2', '水': '#2c3e50',
}

function tagColor(dim: string, value: string | null | undefined): string {
  if (!value) return ''
  if (dim === 'point_type') {
    const fe = value.match(/[木火土金水]/)
    if (fe) return FIVE_ELEMENT_COLORS[fe[0]] || ''
    const base = value.split(/[·、\s]/)[0]
    return POINT_TYPE_DEFAULT_COLORS[base] || ''
  }
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
  } catch (e) {
    ElMessage.error(errMsg(e) || '保存失败')
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
  a.download = `针灸穴位_${fileTimestamp()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function triggerImport() {
  if (fileInput.value) { fileInput.value.value = ''; fileInput.value.click() }
}

async function onImportFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  try {
    const text = await f.text()
    const arr = JSON.parse(text)
    if (!Array.isArray(arr)) { ElMessage.error('文件须为穴位数组 JSON'); return }
    const r: { imported?: number; updated?: number } = await api.post('/acupoints/import', arr, { silent: true })
    ElMessage.success(`导入完成：新增 ${r.imported ?? 0} 条，更新 ${r.updated ?? 0} 条`)
    loadAcupoints()
  } catch (err) {
    ElMessage.error('JSON 解析或导入失败：' + errMsg(err))
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}

const isMobile = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  loadMeta()
  loadAcupoints()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))
</script>

<style scoped>
.acupoint-list { padding: 0; }
.main-card {
  margin-bottom: 12px;
  border-radius: 12px;
  border: 1px solid #f0e4d6;

  :deep(.el-card__header) {
    padding: 0;
    border-bottom: none;
  }
}
.filter-search { width: 200px; }
.filter-sel { width: 140px; }
.filter-actions { display: flex; gap: 8px; }
.opt-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.15);
  vertical-align: middle;
  flex: none;
}
.term-opt { display: flex; align-items: center; gap: 6px; line-height: 1.35; padding: 2px 0; }
.term-name { font-weight: 500; }
.summary { margin-top: 10px; font-size: 12px; color: #907a63; }
.src-pill { display: inline-block; padding: 0 8px; font-size: 12px; line-height: 20px; border: 1px solid transparent; border-radius: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; vertical-align: middle; }
.tcm-table :deep(.el-table__header-wrapper th .cell),
.tcm-table :deep(.el-table__body-wrapper td .cell) { padding: 0 8px; }

/* 移动端卡片 */
.mobile-cards { display: none; }
.m-card {
  margin-bottom: 10px;
  border-radius: 10px;
  border: 1px solid #f0e4d6;
}
.m-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.m-name { font-weight: 600; font-size: 15px; color: #2c1810; }
.m-row { display: flex; font-size: 13px; margin: 3px 0; line-height: 1.6; }
.m-label { width: 42px; color: #907a63; flex: none; }
.m-val { color: #4a3628; flex: 1; word-break: break-all; }
.m-actions { margin-top: 8px; display: flex; gap: 8px; }

@media (max-width: 767px) {
  .mobile-cards { display: block; }
  .tcm-head__actions {
    width: 100%;
    flex-wrap: nowrap;
    gap: 6px;

    :deep(.el-button) {
      margin-left: 0;
      flex: 1 1 auto;
      padding-left: 6px;
      padding-right: 6px;
    }
  }
  .filter-actions { width: 100%; }
}
</style>