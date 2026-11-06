<template>
  <div class="knowledge-search">
    <el-card shadow="hover" class="search-card">
      <template #header>
        <div class="card-head-bar">
          <div class="card-head-title">
            <span class="head-icon">🔍</span>
            <span class="head-text">知识检索</span>
          </div>
          <el-tooltip placement="bottom-end" :show-after="200" effect="light">
            <template #content>
              <div class="mode-tip">
                <div class="mode-tip-title">{{ semanticOn ? '🧠 语义检索已启用' : '🔤 关键词检索模式' }}</div>
                <div class="mode-tip-desc">
                  <template v-if="semanticOn">按语义相似度匹配，可用自然语言描述症状或医理，结果更贴近意图。</template>
                  <template v-else>按字面关键词匹配。可理解自然语言的语义检索需在后台开启向量索引（详见下方说明）。</template>
                </div>
              </div>
            </template>
            <el-tag :type="semanticOn ? 'success' : 'info'" effect="light" round size="small" class="mode-tag">
              <el-icon><MagicStick v-if="semanticOn" /><Aim v-else /></el-icon>
              {{ semanticOn ? '语义检索' : '关键词检索' }}
            </el-tag>
          </el-tooltip>
        </div>
      </template>

      <div class="search-box">
        <el-input v-model="searchText" placeholder="输入关键词或自然语言描述，如「肝郁脾虚的调理思路」" clearable
          class="search-input" @keyup.enter="doSearch" size="large">
          <template #prefix><el-icon><Search /></el-icon></template>
          <template #append>
            <el-button type="primary" @click="doSearch" :loading="searching">
              <el-icon><Search /></el-icon>检索
            </el-button>
          </template>
        </el-input>
        <el-select v-model="categoryFilter" placeholder="全部分类" clearable class="category-select" size="large" @change="doSearch">
          <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
        </el-select>
      </div>

      <!-- 搜索结果 -->
      <div v-if="results.length > 0" class="search-results">
        <div class="results-bar">
          <span class="results-count">找到 <b>{{ results.length }}</b> 条相关知识</span>
          <el-button size="small" text @click="results = []; searched = false">
            <el-icon><Close /></el-icon>清除结果
          </el-button>
        </div>
        <div v-for="(r, idx) in results" :key="r.id ?? idx" class="result-item" @click="viewDetail(r)">
          <div class="result-index">{{ idx + 1 }}</div>
          <div class="result-body">
            <div class="result-header">
              <el-tag size="small" :type="r.match_type === '语义' ? 'success' : 'info'" effect="light" round>
                {{ r.match_type === '语义' ? '🧠 语义匹配' : '🔤 关键词' }}
              </el-tag>
              <el-tag v-if="r.category" size="small" type="warning" effect="light" round>{{ r.category }}</el-tag>
              <span v-if="r.source" class="result-source">{{ r.source }}</span>
              <span v-if="r.score" class="result-score">
                <span class="score-bar"><i :style="{ width: `${Math.min(r.score * 100, 100)}%` }"></i></span>
                {{ (r.score * 100).toFixed(1) }}%
              </span>
            </div>
            <div class="result-title">{{ r.title }}</div>
            <div class="result-content">{{ r.content }}</div>
          </div>
        </div>
      </div>

      <el-empty v-else-if="searched" :image-size="80">
        <template #description>
          <span>未找到相关知识，试试更换关键词或分类</span>
        </template>
      </el-empty>
      <div v-else class="search-hint">
        <div class="hint-icon">🍃</div>
        <div class="hint-title">输入关键词开始检索</div>
        <div class="hint-sub">
          支持按标题、内容、出处检索{{ semanticOn ? '，也可直接用自然语言描述' : '' }}
        </div>
      </div>
    </el-card>

    <!-- 知识库统计 -->
    <el-card shadow="hover" class="stat-card">
      <template #header>
        <div class="card-head-bar">
          <div class="card-head-title">
            <span class="head-icon">📊</span>
            <span class="head-text">知识库概况</span>
          </div>
        </div>
      </template>

      <div class="stat-grid">
        <div class="stat-item">
          <div class="stat-label">知识条目</div>
          <div class="stat-value">{{ stats.total_entries ?? 0 }}</div>
          <div class="stat-unit">条</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">分类数</div>
          <div class="stat-value">{{ stats.categories?.length || 0 }}</div>
          <div class="stat-unit">类</div>
        </div>
        <div class="stat-item" :class="semanticOn ? 'is-on' : 'is-off'">
          <div class="stat-label">
            向量索引
            <el-tooltip placement="top" :show-after="150" effect="light">
              <template #content>
                <div class="mode-tip">
                  <div class="mode-tip-title">什么是向量索引？</div>
                  <div class="mode-tip-desc">
                    把每条知识转成「语义向量」存入本地数据库后，检索时按语义相似度匹配，
                    能听懂「吃不下饭、容易生气」这类口语化描述，而不是只认字面关键词。
                  </div>
                  <div class="mode-tip-title" style="margin-top:6px">为什么显示未启用？</div>
                  <div class="mode-tip-desc">
                    它依赖 chromadb + 中文向量模型（体积约数百 MB），为保持系统轻量默认关闭。
                    当前所有检索会自动降级为关键词检索 —— 功能不受影响，只是不懂同义词。
                  </div>
                </div>
              </template>
              <el-icon class="stat-help"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
          <div class="stat-value stat-value--text">
            <el-tag :type="semanticOn ? 'success' : 'info'" effect="light" round>
              {{ semanticOn ? `已索引 ${stats.vector_store?.count || 0} 条` : '未启用' }}
            </el-tag>
          </div>
          <div class="stat-unit">{{ semanticOn ? '' : '关键词检索中' }}</div>
        </div>
      </div>

      <div v-if="!semanticOn" class="index-note">
        <el-icon><InfoFilled /></el-icon>
        <div>
          <div>当前为关键词检索模式，功能完整可用。如需启用语义检索（支持自然语言提问、同义词匹配），
            需在服务端安装 <code>chromadb</code> 与 <code>sentence-transformers</code>，
            并设置环境变量 <code>ENABLE_SEMANTIC_SEARCH=true</code> 后重启服务。</div>
          <div class="index-note-sub">启用后，下方「重建向量索引」可把已有的 {{ stats.total_entries ?? 0 }} 条知识导入索引。</div>
        </div>
      </div>

      <div v-if="auth.can('dict:write')" class="stat-actions">
        <el-button size="small" :disabled="!semanticOn" @click="rebuildIndex">
          <el-icon><Refresh /></el-icon>重建向量索引
        </el-button>
        <span v-if="!semanticOn" class="action-hint">语义检索未启用，暂无需重建</span>
      </div>

      <div v-if="stats.categories?.length" class="category-cloud">
        <el-divider content-position="left">分类分布</el-divider>
        <el-tag v-for="c in stats.categories" :key="c.name" class="cat-tag" effect="plain" round>
          {{ c.name }}<span class="cat-count">{{ c.count }}</span>
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
import {
  Search, Close, Refresh, InfoFilled, QuestionFilled, MagicStick, Aim,
} from '@element-plus/icons-vue'
import api from '@/utils/api'
import type { KnowledgeEntry } from '@/types'
import { useAuthStore } from '@/store/auth'
import { renderMarkdown } from '@/utils/markdown'

const auth = useAuthStore()

const searchText = ref('')
const categoryFilter = ref('')
const results = ref<KnowledgeEntry[]>([])
const searching = ref(false)
const searched = ref(false)
const stats = ref<Record<string, any>>({ total_entries: 0, categories: [], vector_store: {} })
const detailVisible = ref(false)
const currentEntry = ref<KnowledgeEntry | null>(null)

// 向量索引是否启用：由后端 /knowledge/stats 返回，决定界面展示的检索模式
const semanticOn = computed(() => !!stats.value.vector_store?.available)

const categories = computed(() => ((stats.value.categories as Array<{ name: string }>) || []).map((c: { name: string }) => c.name))

async function doSearch() {
  if (!searchText.value.trim()) return
  searching.value = true
  searched.value = true
  try {
    const params: Record<string, any> = { q: searchText.value, limit: 20 }
    if (categoryFilter.value) params.category = categoryFilter.value
    results.value = (await api.get<KnowledgeEntry[]>('/knowledge/search', { params }))
  } catch {} finally {
    searching.value = false
  }
}

async function viewDetail(r: KnowledgeEntry) {
  try {
    // 如果是知识库条目，获取完整内容
    if (r.id && typeof r.id === 'number') {
      currentEntry.value = await api.get<KnowledgeEntry>(`/knowledge/entries/${r.id}`)
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
    stats.value = (await api.get<Record<string, any>>('/knowledge/stats'))
  } catch {}
}

async function rebuildIndex() {
  try {
    const res = await api.post<{ message?: string }>('/knowledge/rebuild-index')
    ElMessage.success(res.message || '索引重建完成')
    loadStats()
  } catch {}
}

onMounted(loadStats)
</script>

<style scoped lang="scss">
.knowledge-search {
  .search-card,
  .stat-card {
    :deep(.el-card__header) {
      padding: 14px 18px;
      background: linear-gradient(135deg, #fdf8f3 0%, #f7efe6 100%);
      border-bottom: 1px solid #f0e4d6;
    }
  }

  .stat-card { margin-top: 16px; }

  .card-head-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .card-head-title {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .head-icon { font-size: 18px; line-height: 1; }

  .head-text {
    font-size: 16px;
    font-weight: 600;
    color: #2c1810;
    letter-spacing: .5px;
  }

  .mode-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: default;
  }

  .search-box {
    display: flex;
    gap: 10px;
    margin-bottom: 18px;
    flex-wrap: wrap;

    .search-input { flex: 1; min-width: 260px; }
    .category-select { width: 160px; flex: none; }

    :deep(.el-input-group__append) {
      padding: 0;
      background: none;
      border: none;
      box-shadow: none;

      .el-button {
        height: 100%;
        margin: 0;
        border-radius: 0 4px 4px 0;
        padding: 0 22px;
      }
    }
  }

  .search-results {
    .results-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;

      .results-count {
        font-size: 13px;
        color: #8a7a68;
        b { color: #8b5e34; font-weight: 600; }
      }
    }

    .result-item {
      display: flex;
      gap: 12px;
      padding: 14px 16px;
      border: 1px solid #eee3d6;
      border-radius: 10px;
      margin-bottom: 10px;
      cursor: pointer;
      background: #fff;
      transition: all .2s ease;

      &:hover {
        background: #faf5f0;
        border-color: var(--tcm-accent);
        box-shadow: 0 2px 10px rgba(139, 94, 52, .08);
        transform: translateY(-1px);
      }

      .result-index {
        flex: none;
        width: 26px;
        height: 26px;
        line-height: 26px;
        text-align: center;
        font-size: 12px;
        font-weight: 600;
        color: #b89a76;
        background: #faf6f1;
        border: 1px solid #eddfd0;
        border-radius: 50%;
      }

      .result-body { min-width: 0; flex: 1; }

      .result-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
        flex-wrap: wrap;

        .result-source {
          font-size: 12px;
          color: #9a8b7a;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          max-width: 200px;
        }

        .result-score {
          margin-left: auto;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: #5b8c3e;
          font-variant-numeric: tabular-nums;

          .score-bar {
            display: inline-block;
            width: 56px;
            height: 4px;
            border-radius: 2px;
            background: #e8efe2;
            overflow: hidden;

            i {
              display: block;
              height: 100%;
              border-radius: 2px;
              background: linear-gradient(90deg, #a8c98a, #5b8c3e);
            }
          }
        }
      }

      .result-title {
        font-size: 15px;
        font-weight: 600;
        color: #2c1810;
        margin-bottom: 6px;
      }

      .result-content {
        font-size: 13px;
        color: #666;
        line-height: 1.7;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
    }
  }

  .search-hint {
    text-align: center;
    padding: 34px 0 40px;

    .hint-icon { font-size: 34px; opacity: .6; }
    .hint-title {
      font-size: 15px;
      font-weight: 600;
      color: #6b5644;
      margin-top: 8px;
    }
    .hint-sub {
      font-size: 12.5px;
      color: #a39484;
      margin-top: 6px;
    }
  }

  .stat-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;

    .stat-item {
      padding: 14px 16px;
      border-radius: 10px;
      background: #faf7f3;
      border: 1px solid #efe5d9;

      &.is-on { background: #f4f9f0; border-color: #dbe8d1; }
    }

    .stat-label {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12.5px;
      color: #90806e;
    }

    .stat-help {
      color: #b8a897;
      cursor: help;
      font-size: 13px;
      &:hover { color: #8b5e34; }
    }

    .stat-value {
      font-size: 24px;
      font-weight: 600;
      color: #2c1810;
      line-height: 1.3;
      margin-top: 4px;
      font-variant-numeric: tabular-nums;

      &--text {
        font-size: 13px;
        font-weight: 400;
        margin-top: 6px;
      }
    }

    .stat-unit {
      font-size: 12px;
      color: #a89a8a;
      min-height: 16px;
    }
  }

  .index-note {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-top: 14px;
    padding: 10px 14px;
    font-size: 12.5px;
    line-height: 1.8;
    color: #8a7a68;
    background: #faf6f1;
    border: 1px dashed #e6d9c9;
    border-radius: 8px;

    .el-icon { margin-top: 3px; color: #b89a76; flex: none; }
    code {
      background: #fff;
      border: 1px solid #e6d9c9;
      color: #8b5e34;
      padding: 0 4px;
      border-radius: 3px;
      font-size: 11.5px;
    }
    .index-note-sub { margin-top: 4px; color: #a39484; }
  }

  .stat-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 12px;

    .action-hint { font-size: 12px; color: #a89a8a; }
  }

  .category-cloud {
    margin-top: 14px;

    :deep(.el-divider__text) {
      font-size: 12.5px;
      color: #a89a8a;
      background: #fff;
    }

    .cat-tag {
      margin: 0 6px 8px 0;
      background: #fff;
      border-color: #efe5d9;
      color: #6b5644;

      .cat-count {
        margin-left: 5px;
        color: #b89a76;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
      }
    }
  }

  @media (max-width: 767px) {
    .search-box {
      .search-input,
      .category-select { width: 100%; }
    }

    .stat-grid { grid-template-columns: 1fr; }

    .search-results .result-item .result-header .result-score { margin-left: 0; }
  }

  .mode-tip {
    max-width: 300px;
    line-height: 1.7;

    .mode-tip-title { font-size: 13px; font-weight: 600; color: #2c1810; }
    .mode-tip-desc { font-size: 12.5px; color: #6b5644; }
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
      color: var(--tcm-primary);
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
      border-left: 3px solid var(--tcm-accent);
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
    :deep(a) { color: var(--tcm-primary); }
    :deep(hr) { border: none; border-top: 1px solid #e0d6ca; margin: 12px 0; }
  }
}
</style>