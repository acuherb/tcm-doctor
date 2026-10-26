<template>
  <div class="book-library">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>📚 医籍文库</span>
          <span class="total-count" v-if="total > 0">共 {{ total }} 条</span>
        </div>
      </template>

      <!-- 筛选栏 / 操作栏 -->
      <div class="filter-bar">
        <el-select v-model="activeCategory" placeholder="全部分类" clearable @change="onFilterChange" style="width:150px">
          <el-option v-for="cat in categories" :key="cat.name" :label="`${cat.name} (${cat.count})`" :value="cat.name" />
        </el-select>
        <el-select v-model="sourceFilter" placeholder="全部出处" clearable @change="onFilterChange" style="width:170px">
          <el-option v-for="s in sources" :key="s.name" :label="`${s.name} (${s.count})`" :value="s.name" />
        </el-select>
        <el-input v-model="searchText" placeholder="搜索标题/内容" clearable @clear="onFilterChange" style="width:220px"
          @keyup.enter="onFilterChange">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="onFilterChange">查询</el-button>

        <span class="flex-spacer"></span>

        <el-upload
          v-if="editable"
          accept=".json"
          :on-change="onImportFile"
          style="display:inline-block;"
        >
          <el-button type="success" plain :loading="importing">
            <el-icon><Upload /></el-icon> 导入 JSON
          </el-button>
        </el-upload>
        <el-button v-if="editable" type="warning" plain @click="onExport">
          <el-icon><Download /></el-icon> 导出
        </el-button>
        <el-button v-if="editable" type="primary" plain @click="openEdit()">
          <el-icon><Plus /></el-icon> 新增条目
        </el-button>
        <el-popconfirm
          v-if="editable && selectedIds.length"
          title="确定删除选中的条目？"
          confirm-button-text="删除"
          @confirm="batchDelete"
        >
          <template #reference>
            <el-button type="danger" plain>
              <el-icon><Delete /></el-icon> 批量删除({{ selectedIds.length }})
            </el-button>
          </template>
        </el-popconfirm>
      </div>

      <!-- 表格 -->
      <el-table
        :data="entries"
        v-loading="loading"
        stripe
        highlight-current-row
        style="width:100%;"
        :max-height="tableMaxHeight"
        @row-click="viewDetail"
        @selection-change="onSelectionChange"
      >
        <el-table-column v-if="editable" type="selection" width="42" />
        <el-table-column prop="title" label="标题" width="170" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="categoryTagType(row.category)">{{ row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="出处" width="130" show-overflow-tooltip />
        <el-table-column prop="content_preview" label="内容预览" min-width="300">
          <template #default="{ row }">
            <el-popover placement="top-start" :width="520" trigger="hover" :show-after="250" @show="loadFull(row)">
              <template #reference>
                <div class="preview-cell">{{ row.content_preview }}</div>
              </template>
              <div class="preview-md" v-html="renderMarkdown(fullContentMap[row.id] || '')"></div>
            </el-popover>
          </template>
        </el-table-column>
        <el-table-column v-if="editable" label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click.stop="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确定删除这条知识？" @confirm="onDelete(row)">
              <template #reference>
                <el-button size="small" type="danger" plain @click.stop>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          :page-sizes="[30, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadEntries"
          @size-change="onPageSizeChange"
        />
      </div>
    </el-card>

    <!-- 条目详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="currentEntry?.title || '条目详情'" width="720px" destroy-on-close>
      <template v-if="currentEntry">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="分类">{{ currentEntry.category || '-' }}</el-descriptions-item>
          <el-descriptions-item label="出处">{{ currentEntry.source || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-divider content-position="left">内容</el-divider>
        <div class="detail-content" v-html="renderMarkdown(currentEntry.content)"></div>
      </template>
    </el-dialog>

    <!-- 新增 / 编辑弹窗 -->
    <el-dialog v-model="editVisible" :title="editingId ? '编辑条目' : '新增条目'" width="720px" destroy-on-close>
      <el-form :model="editForm" label-width="70px">
        <el-form-item label="标题" required>
          <el-input v-model="editForm.title" placeholder="条目标题" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="editForm.category" placeholder="选择或输入分类" filterable allow-create default-first-option style="width:100%">
            <el-option v-for="c in categories" :key="c.name" :label="c.name" :value="c.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="出处">
          <el-input v-model="editForm.source" placeholder="如：伤寒论 / 倪海厦·医案" />
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="editForm.content" type="textarea" :rows="12" placeholder="条目正文内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEntry">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Search, Plus, Upload, Download, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { renderMarkdown } from '@/utils/markdown'
import { useAuthStore } from '@/store/auth'
import type { UploadFile } from 'element-plus'

// 游客（非管理员）隐藏所有写操作，只读浏览
const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)

interface SourceItem { name: string; count: number }
interface CategoryItem { name: string; count: number }
interface EntryItem {
  id: number
  title: string
  category: string
  source: string
  content_preview: string
}

const entries = ref<EntryItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const tableMaxHeight = ref(600)

const activeCategory = ref('')
const searchText = ref('')
const sourceFilter = ref('')
const sources = ref<SourceItem[]>([])
const categories = ref<CategoryItem[]>([])

const detailVisible = ref(false)
const currentEntry = ref<any>(null)
const selectedIds = ref<number[]>([])
const fullContentMap = ref<Record<number, string>>({})

const editVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const editForm = ref<{ title: string; category: string; source: string; content: string }>({
  title: '',
  category: '',
  source: '',
  content: '',
})

// 计算表格最大高度
function calcTableHeight() {
  tableMaxHeight.value = window.innerHeight - 260
}

function categoryTagType(cat: string): string {
  const map: Record<string, string> = {
    '条文': '',
    '医案': 'success',
    '针灸经络': 'warning',
    '针灸腧穴': 'warning',
    '针灸治疗': 'warning',
    '针灸技法': 'warning',
    '方剂': 'danger',
    '经典理论': 'info',
    '诊疗规范': 'info',
  }
  return map[cat] || ''
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function onFilterChange() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    currentPage.value = 1
    loadEntries()
    loadStats()
  }, 300)
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadEntries()
}

async function loadStats() {
  try {
    const stats = (await api.get('/knowledge/stats')) as any
    categories.value = stats.categories || []
  } catch {}
}

async function loadSources() {
  try {
    sources.value = (await api.get('/knowledge/sources')) as any
  } catch {}
}

async function loadEntries() {
  loading.value = true
  try {
    const params: any = {
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    }
    if (activeCategory.value) params.category = activeCategory.value
    if (sourceFilter.value) params.source = sourceFilter.value
    if (searchText.value) params.search = searchText.value
    const res = (await api.get('/knowledge/entries', { params })) as any
    entries.value = res.items || []
    total.value = res.total || 0
  } catch {
    entries.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function viewDetail(row: EntryItem) {
  try {
    currentEntry.value = await api.get(`/knowledge/entries/${row.id}`)
    detailVisible.value = true
  } catch {}
}

// ---- 编辑 / 新增 ----
async function openEdit(row?: any) {
  editingId.value = row?.id ?? null
  let entry: any = row || null
  // 列表项只有 content_preview，编辑需要完整 content，缺失时先拉详情
  if (entry && !entry.content) {
    try {
      entry = await api.get(`/knowledge/entries/${entry.id}`)
    } catch { /* 保持原值 */ }
  }
  editForm.value = {
    title: entry?.title || '',
    category: entry?.category || '',
    source: entry?.source || '',
    content: entry?.content || '',
  }
  editVisible.value = true
}

async function saveEntry() {
  if (!editForm.value.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  if (!editForm.value.content.trim()) {
    ElMessage.warning('请填写内容')
    return
  }
  saving.value = true
  try {
    const body: any = {
      title: editForm.value.title,
      category: editForm.value.category || '其他',
      content: editForm.value.content,
      source: editForm.value.source || null,
    }
    if (editingId.value) {
      await api.put(`/knowledge/entries/${editingId.value}`, body)
    } else {
      await api.post('/knowledge/entries', body)
    }
    editVisible.value = false
    ElMessage.success(editingId.value ? '已更新' : '已新增')
    loadStats()
    loadEntries()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function onDelete(row: EntryItem) {
  try {
    await api.delete(`/knowledge/entries/${row.id}`)
    ElMessage.success('已删除')
    loadStats()
    loadSources()
    loadEntries()
  } catch {
    ElMessage.error('删除失败')
  }
}

function onSelectionChange(sel: any[]) {
  selectedIds.value = sel.map((s) => s.id)
}

async function loadFull(row: any) {
  if (!row?.id || fullContentMap.value[row.id]) return
  try {
    const e = await api.get(`/knowledge/entries/${row.id}`) as any
    fullContentMap.value[row.id] = e.content || ''
  } catch { /* 忽略 */ }
}

async function batchDelete() {
  if (!selectedIds.value.length) return
  try {
    const res = (await api.delete('/knowledge/entries/batch', { data: selectedIds.value })) as any
    ElMessage.success(`已删除 ${res.deleted || 0} 条`)
    selectedIds.value = []
    loadStats()
    loadSources()
    loadEntries()
  } catch {
    ElMessage.error('批量删除失败')
  }
}

// ---- 导出 ----
async function onExport() {
  try {
    const params: any = {}
    if (activeCategory.value) params.category = activeCategory.value
    if (sourceFilter.value) params.source = sourceFilter.value
    const data = (await api.get('/knowledge/export', { params })) as any[]
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `医籍文库_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${data.length} 条`)
  } catch {
    ElMessage.error('导出失败')
  }
}

// ---- 导入 ----
async function onImportFile(file: UploadFile) {
  const raw = file.raw
  if (!raw) return
  const reader = new FileReader()
  reader.onload = async () => {
    try {
      const data = JSON.parse(String(reader.result))
      const list: any[] = Array.isArray(data) ? data : (data.items || [])
      if (!list.length) {
        ElMessage.warning('文件中没有可导入的数据')
        return
      }
      importing.value = true
      const res = (await api.post('/knowledge/import', list)) as any
      ElMessage.success(`导入完成：新增 ${res.added}，更新 ${res.updated}`)
      loadStats()
      loadSources()
      loadEntries()
    } catch {
      ElMessage.error('JSON 解析失败或格式不正确')
    } finally {
      importing.value = false
    }
  }
  reader.readAsText(raw)
}

const importing = ref(false)

onMounted(async () => {
  calcTableHeight()
  window.addEventListener('resize', calcTableHeight)
  await Promise.all([loadStats(), loadSources()])
  loadEntries()
})

onUnmounted(() => {
  window.removeEventListener('resize', calcTableHeight)
  if (debounceTimer) clearTimeout(debounceTimer)
})
</script>

<style scoped lang="scss">
.book-library {
  .total-count {
    font-size: 14px;
    color: #999;
    font-weight: 400;
  }

  .filter-bar {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 16px;
    flex-wrap: wrap;

    .flex-spacer {
      flex: 1;
    }
  }

  .pagination-wrap {
    display: flex;
    justify-content: center;
    margin-top: 16px;
  }

  .preview-cell {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    cursor: default;
  }

  :global(.preview-md) {
    font-size: 14px;
    line-height: 1.7;
    color: #2C1810;
    max-height: 420px;
    overflow-y: auto;

    h1, h2, h3, h4 {
      font-weight: 600;
      color: #8B4513;
      margin: 12px 0 6px;
      &:first-child { margin-top: 0; }
    }
    h1 { font-size: 18px; }
    h2 { font-size: 16px; }
    h3 { font-size: 15px; }
    p { margin: 5px 0; }
    ul, ol { padding-left: 20px; margin: 5px 0; }
    li { margin: 3px 0; }
    strong { color: #8B0000; }
    code {
      background: #f5f0ea;
      color: #a33;
      padding: 1px 4px;
      border-radius: 3px;
      font-size: 12px;
    }
    blockquote {
      margin: 6px 0;
      padding: 5px 10px;
      border-left: 3px solid #D4A574;
      background: #faf6f1;
      color: #5a4632;
      border-radius: 0 4px 4px 0;
    }
    table {
      border-collapse: collapse;
      margin: 6px 0;
      font-size: 13px;
    }
    th, td {
      border: 1px solid #e0d6ca;
      padding: 4px 8px;
      font-size: 13px;
    }
    th { background: #f5ede3; font-weight: 600; }
    tr:nth-child(even) td { background: #fcf9f5; }
  }

  .detail-content {
    font-size: 15px;
    line-height: 1.8;
    color: #2C1810;
    max-height: 60vh;
    overflow-y: auto;
    padding: 8px 4px;

    :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
      font-weight: 600;
      color: #8B4513;
      margin: 14px 0 8px;
      &:first-child { margin-top: 0; }
    }
    :deep(h1) { font-size: 20px; }
    :deep(h2) { font-size: 18px; }
    :deep(h3) { font-size: 16px; }
    :deep(p) { margin: 6px 0; }
    :deep(ul), :deep(ol) { padding-left: 22px; margin: 6px 0; }
    :deep(li) { margin: 3px 0; }
    :deep(strong) { color: #8B0000; }
    :deep(em) { color: #61412a; }
    :deep(code) {
      background: #f5f0ea;
      color: #a33;
      padding: 1px 5px;
      border-radius: 3px;
      font-size: 13px;
    }
    :deep(blockquote) {
      margin: 8px 0;
      padding: 6px 12px;
      border-left: 3px solid #D4A574;
      background: #faf6f1;
      color: #5a4632;
      border-radius: 0 4px 4px 0;
    }
    :deep(table) {
      border-collapse: collapse;
      margin: 8px 0;
      width: auto;
      display: block;
      overflow-x: auto;
    }
    :deep(th), :deep(td) {
      border: 1px solid #e0d6ca;
      padding: 5px 10px;
      font-size: 14px;
    }
    :deep(th) { background: #f5ede3; font-weight: 600; }
    :deep(tr:nth-child(even) td) { background: #fcf9f5; }
    :deep(a) { color: #8B4513; }
    :deep(hr) { border: none; border-top: 1px solid #e0d6ca; margin: 12px 0; }
  }
}
</style>