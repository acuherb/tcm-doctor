<template>
  <el-card class="acupoint-card" shadow="never">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchText"
          placeholder="搜索穴名"
          clearable
          style="width: 180px"
          @keyup.enter="loadAcupoints"
        />
        <el-select v-model="meridianFilter" placeholder="按归经筛选" clearable style="width: 200px">
          <el-option v-for="m in meridians" :key="m" :label="m" :value="m" />
        </el-select>
        <el-button type="primary" @click="loadAcupoints">查询</el-button>
        <el-tag type="info" effect="plain">{{ total }} 穴</el-tag>
      </div>
      <div class="toolbar-right">
        <el-button v-if="editable" size="small" @click="exportAcupoints">导出</el-button>
        <el-button v-if="editable" size="small" @click="triggerImport">导入</el-button>
        <el-button v-if="editable" type="primary" size="small" @click="openAdd">新增穴位</el-button>
        <input ref="fileInput" type="file" accept=".json,application/json" style="display: none" @change="onImportFile" />
      </div>
    </div>

    <!-- 表格 -->
    <el-table :data="acupoints" stripe style="width: 100%">
      <el-table-column prop="name" label="穴名" width="110" fixed>
        <template #default="{ row }">
          <span class="acupoint-name">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="meridian" label="归经" width="160">
        <template #default="{ row }">
          <el-tag :type="meridianTag(row.meridian)" effect="plain">{{ row.meridian }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="point_type" label="类型" width="90" />
      <el-table-column prop="location" label="定位" min-width="220" show-overflow-tooltip />
      <el-table-column prop="efficacy" label="功效" min-width="220" show-overflow-tooltip />
      <el-table-column v-if="editable" label="操作" width="140" align="center">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="removeAcupoint(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="showDialog" :title="isEdit ? '编辑穴位' : '新增穴位'" width="560px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="穴名" required>
          <el-input v-model="form.name" placeholder="如：足三里" />
        </el-form-item>
        <el-form-item label="归经">
          <el-select v-model="form.meridian" placeholder="选择归经" filterable style="width: 100%">
            <el-option v-for="m in meridians" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.point_type" placeholder="如：合穴" filterable allow-create style="width: 100%">
            <el-option v-for="t in pointTypes" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="定位">
          <el-input v-model="form.location" type="textarea" :rows="2" placeholder="取穴定位" />
        </el-form-item>
        <el-form-item label="功效">
          <el-input v-model="form.efficacy" type="textarea" :rows="2" placeholder="主治功效" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="倪师取穴要点、操作说明等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)

const meridians = [
  '手太阴肺经', '手阳明大肠经', '足阳明胃经', '足太阴脾经',
  '手少阴心经', '手太阳小肠经', '足太阳膀胱经', '足少阴肾经',
  '手厥阴心包经', '手少阳三焦经', '足少阳胆经', '足厥阴肝经',
  '任脉', '督脉', '奇穴及倪师常用组合', '未分类',
]
const pointTypes = ['井穴', '荥穴', '输穴', '经穴', '合穴', '原穴', '络穴', '郄穴', '募穴', '经外奇穴']
const meridianColors = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399', '#D4A574', '#62c2b6', '#a58fe0']

const acupoints = ref<any[]>([])
const searchText = ref('')
const meridianFilter = ref('')
const total = ref(0)
const showDialog = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)

const form = ref<any>({
  name: '', meridian: '', location: '', efficacy: '', point_type: '', notes: '',
})

function meridianTag(m: string) {
  const idx = meridians.findIndex((x) => x === m)
  const colors = ['primary', 'success', 'warning', 'danger', 'info', 'danger']
  return colors[Math.abs(idx) % colors.length] as any
}

function defaultForm() {
  return { name: '', meridian: '', location: '', efficacy: '', point_type: '', notes: '' }
}

async function loadAcupoints() {
  try {
    const params: any = {}
    if (searchText.value) params.search = searchText.value
    if (meridianFilter.value) params.meridian = meridianFilter.value
    const data: any = await api.get('/acupoints', { params })
    acupoints.value = data
    total.value = Array.isArray(data) ? data.length : 0
  } catch {}
}

function openAdd() {
  isEdit.value = false
  editingId.value = null
  form.value = defaultForm()
  showDialog.value = true
}

function openEdit(row: any) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    name: row.name || '',
    meridian: row.meridian || '',
    location: row.location || '',
    efficacy: row.efficacy || '',
    point_type: row.point_type || '',
    notes: row.notes || '',
  }
  showDialog.value = true
}

async function submitForm() {
  if (!form.value.name.trim()) { ElMessage.warning('请输入穴名'); return }
  saving.value = true
  try {
    const payload: any = { ...form.value }
    if (isEdit.value) {
      await api.put(`/acupoints/${editingId.value}`, payload)
      ElMessage.success('穴位更新成功')
    } else {
      await api.post('/acupoints', payload)
      ElMessage.success('穴位添加成功')
    }
    showDialog.value = false
    loadAcupoints()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function removeAcupoint(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除穴位「${row.name}」？`, '提示', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  try {
    const r: any = await api.delete(`/acupoints/${row.id}`)
    ElMessage.success(r?.message || '操作成功')
    loadAcupoints()
  } catch {}
}

// ── 导入/导出 ──
const fileInput = ref<HTMLInputElement | null>(null)
function triggerImport() {
  if (fileInput.value) { fileInput.value.value = ''; fileInput.value.click() }
}
async function onImportFile(e: any) {
  const f = e.target.files?.[0]
  if (!f) return
  try {
    const text = await f.text()
    const arr = JSON.parse(text)
    if (!Array.isArray(arr)) { ElMessage.error('文件须为穴位数组 JSON'); return }
    const r: any = await api.post('/acupoints/import', arr)
    ElMessage.success(`导入完成：新增 ${r.imported} 条，更新 ${r.updated} 条`)
    loadAcupoints()
  } catch {
    ElMessage.error('JSON 解析或导入失败')
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}
async function exportAcupoints() {
  try {
    const data: any = await api.get('/acupoints/export')
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `acupoints_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch {}
}

onMounted(loadAcupoints)
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 8px;
}
.toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.acupoint-name { font-weight: 600; color: #5b3b1e; }
</style>