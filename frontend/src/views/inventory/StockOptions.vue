<template>
  <div class="stock-options">
    <el-card shadow="hover" class="opt-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">🏷️</span>
            <span class="tcm-head__text">物品类别</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ categories.length }} 项</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-button type="primary" @click="openCreate('category')">
              <el-icon><Plus /></el-icon> 新增类别
            </el-button>
          </div>
        </div>
      </template>
      <el-table v-if="!isMobile" :data="categories" class="tcm-table" empty-text="暂无类别">
        <el-table-column label="名称" min-width="160">
          <template #default="{ row }">
            <span class="xw-tag" :style="optionChipStyle(row)">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="(v: any) => toggle(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="isMobile" class="cards">
        <div v-for="row in categories" :key="row.id" class="card">
          <span class="card-name">{{ row.name }}</span>
          <div class="card-actions">
            <el-switch v-model="row.is_active" @change="(v: any) => toggle(row, v)" />
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </div>
        </div>
        <el-empty v-if="!categories.length" description="暂无类别" />
      </div>
    </el-card>

    <el-card shadow="hover" class="opt-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">📐</span>
            <span class="tcm-head__text">计量单位</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ units.length }} 项</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-button type="primary" @click="openCreate('unit')">
              <el-icon><Plus /></el-icon> 新增单位
            </el-button>
          </div>
        </div>
      </template>
      <el-table v-if="!isMobile" :data="units" class="tcm-table" empty-text="暂无单位">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="(v: any) => toggle(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="isMobile" class="cards">
        <div v-for="row in units" :key="row.id" class="card">
          <span class="card-name">{{ row.name }}</span>
          <div class="card-actions">
            <el-switch v-model="row.is_active" @change="(v: any) => toggle(row, v)" />
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </div>
        </div>
        <el-empty v-if="!units.length" description="暂无单位" />
      </div>
    </el-card>

    <el-dialog v-model="visible" :title="editing ? '编辑选项' : '新增选项'" width="420px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="类型">
          <el-input :model-value="form.opt_type === 'category' ? '物品类别' : '计量单位'" disabled />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：理疗耗材 / 袋" maxlength="60" show-word-limit />
        </el-form-item>
        <el-form-item v-if="isCategory" label="颜色">
          <el-color-picker v-model="form.color" />
          <span style="font-size:12px;color:#999;margin-left:8px;">自定义颜色：用于物品类别标签着色，留空则用默认色</span>
          <div style="margin-top:10px;display:flex;align-items:center;gap:8px;">
            <span class="xw-tag" :style="chipStyle(previewColor)">{{ form.name || '预览' }}</span>
            <span v-if="!form.color" style="font-size:12px;color:#999;">（当前为默认色，保存后按此色着色）</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '@/utils/api'

const DEFAULT_COLOR = '#909399'

const isMobile = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }
const categories = ref<any[]>([])
const units = ref<any[]>([])
const visible = ref(false)
const editing = ref<number | null>(null)
const saving = ref(false)
const form = ref<{ opt_type: 'category' | 'unit'; name: string; color: string | null }>({ opt_type: 'category', name: '', color: null })

// 依据颜色亮度返回可读前景色（浅色用深字/深边框，深色用浅字），避免白色等浅色导致标签不可见
function readableInk(hex: string): string {
  const c = (hex || '').replace('#', '')
  if (c.length < 6) return '#333333'
  const r = parseInt(c.slice(0, 2), 16)
  const g = parseInt(c.slice(2, 4), 16)
  const b = parseInt(c.slice(4, 6), 16)
  const L = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return L > 0.6 ? '#333333' : '#ffffff'
}
function chipStyle(c: string): Record<string, string> {
  const ink = readableInk(c)
  return { color: ink, backgroundColor: c, borderColor: ink }
}
function optionChipStyle(row: any): Record<string, string> {
  return chipStyle(row?.color || DEFAULT_COLOR)
}
const isCategory = computed(() => form.value.opt_type === 'category')
const previewColor = computed(() => form.value.color || DEFAULT_COLOR)

async function load() {
  try {
    const res = (await api.get('/stock/options') as any) || []
    categories.value = res.filter((o: any) => o.opt_type === 'category')
    units.value = res.filter((o: any) => o.opt_type === 'unit')
  } catch {
    /* 错误提示由拦截器处理 */
  }
}
function openCreate(type: 'category' | 'unit') {
  editing.value = null
  form.value = { opt_type: type, name: '', color: null }
  visible.value = true
}
function openEdit(row: any) {
  editing.value = row.id
  form.value = { opt_type: row.opt_type, name: row.name, color: row.color || null }
  visible.value = true
}
async function save() {
  const name = form.value.name.trim()
  if (!name) { ElMessage.warning('请输入名称'); return }
  saving.value = true
  try {
    // 仅物品类别支持自定义颜色，单位不写 color
    const color = form.value.opt_type === 'category' ? (form.value.color || null) : undefined
    if (editing.value) {
      const payload: any = { name }
      if (color !== undefined) payload.color = color
      await api.put(`/stock/options/${editing.value}`, payload)
      ElMessage.success('已更新')
    } else {
      const payload: any = { opt_type: form.value.opt_type, name }
      if (color !== undefined) payload.color = color
      await api.post('/stock/options', payload)
      ElMessage.success('已添加')
    }
    visible.value = false
    load()
  } catch {
    /* 错误提示由拦截器处理 */
  } finally {
    saving.value = false
  }
}
async function toggle(row: any, v: any) {
  const val = Boolean(v)
  try {
    await api.put(`/stock/options/${row.id}`, { is_active: val })
    ElMessage.success('已更新')
  } catch {
    row.is_active = !val // 失败回滚
  }
}
async function remove(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认删除选项「${row.name}」？已使用该选项的物品不受影响（仅不再作为下拉候选）。`,
      '删除确认', { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await api.delete(`/stock/options/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch {
    /* 错误提示由拦截器处理 */
  }
}
onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  load()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))
</script>

<style scoped lang="scss">
.stock-options { display: flex; flex-direction: column; gap: 16px; }

.opt-card {
  border-radius: 12px;
  border: 1px solid #f0e4d6;

  :deep(.el-card__header) { padding: 0; border-bottom: none; }
}

.cards { display: flex; flex-direction: column; gap: 8px; }
.card {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  border: 1px solid #f0e4d6; border-radius: 10px; padding: 10px 12px; background: #fff;
  box-shadow: 0 1px 3px rgba(44,24,16,.04);
}
.card .card-name { font-size: 16px; color: #2c1810; word-break: break-all; flex: 1; }
.card .card-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }

.xw-tag {
  display: inline-block;
  padding: 0 8px;
  font-size: 12px;
  line-height: 20px;
  border: 1px solid;
  border-radius: 10px;
  white-space: nowrap;
}

@media (max-width: 767px) {
  .opt-card {
    :deep(.el-card__header) { padding: 0; }
    :deep(.el-card__body) { padding: 12px; }
  }
}
</style>