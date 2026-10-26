<template>
  <div class="knowledge-search">
    <el-card shadow="hover">
      <template #header>
        <span>📚 知识检索</span>
      </template>

      <el-form :inline="true" @submit.prevent="doSearch">
        <el-form-item>
          <el-input v-model="searchText" placeholder="输入关键词或自然语言描述" clearable style="width:360px"
            @keyup.enter="doSearch" size="large">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-select v-model="categoryFilter" placeholder="分类筛选" clearable style="width:140px" @change="doSearch">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" @click="doSearch" :loading="searching">检索</el-button>
        </el-form-item>
      </el-form>

      <!-- 搜索结果 -->
      <div v-if="results.length > 0" class="search-results">
        <div v-for="r in results" :key="r.id" class="result-item" @click="viewDetail(r)">
          <div class="result-header">
            <el-tag size="small" :type="r.match_type === '语义' ? 'success' : 'info'">
              {{ r.match_type === '语义' ? '🧠 语义匹配' : '🔍 关键词' }}
            </el-tag>
            <el-tag v-if="r.category" size="small" type="warning">{{ r.category }}</el-tag>
            <span v-if="r.score" class="result-score">相似度: {{ (r.score * 100).toFixed(1) }}%</span>
          </div>
          <div class="result-title">{{ r.title }}</div>
          <div class="result-content">{{ r.content }}</div>
          <div v-if="r.source" class="result-source">出处: {{ r.source }}</div>
        </div>
      </div>

      <el-empty v-else-if="searched" description="未找到相关知识" :image-size="80" />
      <el-empty v-else description="输入关键词开始检索" :image-size="80" />
    </el-card>

    <!-- 知识库统计 -->
    <el-card shadow="hover" style="margin-top:16px;">
      <template #header><span>📊 知识库概况</span></template>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-statistic title="知识条目" :value="stats.total_entries" />
        </el-col>
        <el-col :span="8">
          <el-statistic title="分类数" :value="stats.categories?.length || 0" />
        </el-col>
        <el-col :span="8">
          <div>
            <div style="font-size:12px;color:#999;margin-bottom:4px;">向量索引</div>
            <el-tag :type="stats.vector_store?.available ? 'success' : 'info'" size="small">
              {{ stats.vector_store?.available ? `已索引 ${stats.vector_store?.count || 0} 条` : '未启用' }}
            </el-tag>
          </div>
        </el-col>
      </el-row>
      <div style="margin-top:12px;">
        <el-button size="small" @click="rebuildIndex">重建向量索引</el-button>
      </div>
      <div v-if="stats.categories?.length" style="margin-top:12px;">
        <el-tag v-for="c in stats.categories" :key="c.name" style="margin:4px;">
          {{ c.name }} ({{ c.count }})
        </el-tag>
      </div>
    </el-card>

    <!-- 条目详情 -->
    <el-dialog v-model="detailVisible" :title="currentEntry?.title || '条目详情'" fullscreen destroy-on-close>
      <template v-if="currentEntry">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="分类">{{ currentEntry.category }}</el-descriptions-item>
          <el-descriptions-item label="出处">{{ currentEntry.source || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div class="entry-content" v-html="renderMarkdown(currentEntry.content)"></div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { renderMarkdown } from '@/utils/markdown'

const searchText = ref('')
const categoryFilter = ref('')
const results = ref<any[]>([])
const searching = ref(false)
const searched = ref(false)
const stats = ref<any>({ total_entries: 0, categories: [], vector_store: {} })
const detailVisible = ref(false)
const currentEntry = ref<any>(null)

const categories = computed(() => (stats.value.categories || []).map((c: any) => c.name))

async function doSearch() {
  if (!searchText.value.trim()) return
  searching.value = true
  searched.value = true
  try {
    const params: any = { q: searchText.value, limit: 20 }
    if (categoryFilter.value) params.category = categoryFilter.value
    results.value = (await api.get('/knowledge/search', { params })) as any
  } catch {} finally {
    searching.value = false
  }
}

async function viewDetail(r: any) {
  try {
    // 如果是知识库条目，获取完整内容
    if (r.id && typeof r.id === 'number') {
      currentEntry.value = await api.get(`/knowledge/entries/${r.id}`) as any
    } else {
      currentEntry.value = r
    }
    detailVisible.value = true
  } catch {
    currentEntry.value = r
    detailVisible.value = true
  }
}

async function loadStats() {
  try {
    stats.value = (await api.get('/knowledge/stats')) as any
  } catch {}
}

async function rebuildIndex() {
  try {
    const res = await api.post('/knowledge/rebuild-index') as any
    ElMessage.success(res.message || '索引重建完成')
    loadStats()
  } catch {}
}

onMounted(loadStats)
</script>

<style scoped lang="scss">
.knowledge-search {
  .search-results {
    .result-item {
      padding: 14px;
      border: 1px solid #e8e0d8;
      border-radius: 8px;
      margin-bottom: 12px;
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        background: #faf5f0;
        border-color: #D4A574;
      }

      .result-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;

        .result-score {
          margin-left: auto;
          font-size: 12px;
          color: #52c41a;
        }
      }

      .result-title {
        font-size: 15px;
        font-weight: 600;
        color: #333;
        margin-bottom: 6px;
      }

      .result-content {
        font-size: 13px;
        color: #666;
        line-height: 1.6;
      }

      .result-source {
        margin-top: 6px;
        font-size: 12px;
        color: #999;
      }
    }
  }

  .entry-content {
    margin-top: 12px;
    line-height: 1.8;
    font-size: 15px;
    color: #2C1810;
    max-width: 980px;
    margin-left: auto;
    margin-right: auto;
    padding: 8px 24px 48px;

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