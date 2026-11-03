<template>
  <span class="tpl-io">
    <el-button size="small" @click="exportTpl" :loading="exporting">
      <el-icon><Download /></el-icon>导出模板
    </el-button>
    <el-upload
      :auto-upload="false"
      :show-file-list="false"
      accept=".json"
      :disabled="!editable"
      @change="onFile"
    >
      <el-button size="small" :disabled="!editable">
        <el-icon><Upload /></el-icon>导入模板
      </el-button>
    </el-upload>
    <el-button
      v-if="bundledAvailable"
      size="small"
      type="primary"
      plain
      :disabled="!editable"
      :loading="importingBundled"
      @click="importBundled"
    >
      导入内置
    </el-button>
    <el-tooltip placement="top">
      <template #content>
        <div style="max-width: 300px; line-height: 1.7">
          导出：把当前本模块数据存为 JSON 备份 / 模板。<br />
          导入模板：选择本地 JSON 批量写入（同名自动更新，不存在则新增）。<br />
          导入内置：一键载入随安装包附带的示例（已按倪海厦人纪整理）。<br />
          <br />
          内置示例存放于后端 <code>app/data/</code>（随安装包附带，源码克隆不含）。
          内容仅供学习参考，<strong>非临床依据</strong>，使用前请核对权威典籍。
        </div>
      </template>
      <el-icon class="tpl-io-help"><QuestionFilled /></el-icon>
    </el-tooltip>
  </span>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { Download, Upload, QuestionFilled } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const props = defineProps<{ type: string; label?: string }>()

const auth = useAuthStore()
const editable = computed(() => auth.can('system:write'))
const exporting = ref(false)
const importingBundled = ref(false)
const bundledAvailable = ref(false)

onMounted(async () => {
  try {
    const list = await api.get<Array<{ type: string; bundled_available: boolean }>>('/templates')
    const it = list.find((t) => t.type === props.type)
    if (it) bundledAvailable.value = it.bundled_available
  } catch {
    // 取不到不影响上传导入/导出
  }
})

async function exportTpl() {
  exporting.value = true
  try {
    const res = await api.get<Blob>(`/templates/export/${props.type}`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res]))
    const a = document.createElement('a')
    a.href = url
    a.download = `tcm_template_${props.type}.json`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('模板已导出')
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

async function onFile(file: UploadFile) {
  const raw = file.raw
  if (!raw) return
  const fd = new FormData()
  fd.append('file', raw)
  try {
    const res = await api.post<{ added: number; updated: number; skipped: number; errors: string[] }>(
      `/templates/import?type=${props.type}`,
      fd,
    )
    ElMessage.success(
      `${props.label ?? props.type}：新增 ${res.added}，更新 ${res.updated}，跳过 ${res.skipped}` +
        (res.errors.length ? `；异常 ${res.errors.length} 条` : ''),
    )
  } catch {
    ElMessage.error('导入失败')
  }
}

async function importBundled() {
  importingBundled.value = true
  try {
    const res = await api.post<{ added: number; updated: number; skipped: number; errors: string[] }>(
      `/templates/import?type=${props.type}&use_bundled=true`,
    )
    ElMessage.success(
      `${props.label ?? props.type}：新增 ${res.added}，更新 ${res.updated}，跳过 ${res.skipped}` +
        (res.errors.length ? `；异常 ${res.errors.length} 条` : ''),
    )
  } catch {
    ElMessage.error('导入内置模板失败')
  } finally {
    importingBundled.value = false
  }
}
</script>

<style scoped lang="scss">
.tpl-io {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  .tpl-io-help {
    color: #b08753;
    cursor: help;
  }
}
</style>
