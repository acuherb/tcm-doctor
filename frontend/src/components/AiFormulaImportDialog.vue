<template>
  <el-dialog
    :model-value="visible"
    :title="`带入开方 · ${formula?.name || ''}`"
    width="680px"
    @update:model-value="(v: any) => { if (!v) emit('close') }"
  >
    <div v-if="formula" class="ai-imp">
      <div class="ai-imp-head">
        <el-tag v-if="formula.role" :type="formula.role === '主方' ? 'danger' : 'warning'" size="small">
          {{ formula.role }}
        </el-tag>
        <span class="ai-imp-name">{{ formula.name }}</span>
        <span v-if="formula.preparation" class="ai-imp-prep">· {{ formula.preparation }}</span>
      </div>

      <div class="ai-imp-block">
        <div class="ai-imp-sub">基础组成（必含）</div>
        <div class="ai-imp-herbs">
          <span
            v-for="(h, i) in finalHerbs"
            :key="'b' + i"
            class="ai-imp-herb"
            :class="{ unknown: h.unknown }"
          >
            {{ h.name }}{{ h.dose ? ' ' + h.dose : '' }}<template v-if="h.method">（{{ h.method }}）</template>
            <em v-if="h.unknown" class="ai-imp-warn">· 字典无此药</em>
          </span>
        </div>
      </div>

      <div v-if="formula.modifications && formula.modifications.length" class="ai-imp-block">
        <div class="ai-imp-sub">加减项（勾选后并入上方组成）</div>
        <el-checkbox-group v-model="selected">
          <div v-for="(m, i) in formula.modifications" :key="i" class="ai-imp-mod">
            <el-checkbox :value="m.label">
              <span class="ai-imp-mod-label">{{ m.label }}</span>
              <span v-if="m.add && m.add.length" class="ai-imp-mod-add">
                ＋ {{ m.add.map((a: any) => a.name + (a.dose ? ' ' + a.dose : '') + (a.method ? '（' + a.method + '）' : '')).join('、') }}
              </span>
              <span v-if="m.remove && m.remove.length" class="ai-imp-mod-del">
                － {{ m.remove.join('、') }}
              </span>
            </el-checkbox>
          </div>
        </el-checkbox-group>
      </div>

      <el-alert
        v-if="unknownCount"
        type="warning"
        :closable="false"
        show-icon
        :title="`有 ${unknownCount} 味药不在药材字典中，仍可带入，请核对或先维护字典`"
      />
    </div>
    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" @click="onConfirm">生成处方并带入</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  formula: any
  herbList: any[]
}>()
const emit = defineEmits<{ confirm: [any]; close: [] }>()

const selected = ref<string[]>([])

// 切换不同方剂时重置勾选
watch(
  () => props.formula,
  () => { selected.value = [] },
  { immediate: true },
)

function matchHerb(name: string): any {
  const n = (name || '').trim()
  if (!n) return null
  return props.herbList.find(
    (h: any) => h.name === n || (h.aliases || []).some((a: string) => a === n),
  )
}

// 合并：基础组成 + 勾选加减的 add；再应用勾选加减的 remove
const finalHerbs = computed(() => {
  const list = (props.formula?.herbs || []).map((h: any) => ({ ...h }))
  const mods = props.formula?.modifications || []
  for (const m of mods) {
    if (selected.value.includes(m.label)) {
      for (const a of m.add || []) list.push({ ...a })
      for (const r of m.remove || []) {
        const idx = list.findIndex((x: any) => x.name === r)
        if (idx >= 0) list.splice(idx, 1)
      }
    }
  }
  return list.map((h: any) => {
    const hit = matchHerb(h.name)
    return {
      name: h.name,
      dose: h.dose || '',
      method: h.method || '',
      herb_id: hit ? hit.id : null,
      unknown: !hit,
    }
  })
})

const unknownCount = computed(() => finalHerbs.value.filter((h: any) => h.unknown).length)

function onConfirm() {
  emit('confirm', {
    name: props.formula?.name || '',
    role: props.formula?.role || '',
    preparation: props.formula?.preparation || '',
    herbs: finalHerbs.value,
  })
}
</script>

<style scoped>
.ai-imp-head { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.ai-imp-name { font-size: 16px; font-weight: 600; }
.ai-imp-prep { color: #888; }
.ai-imp-block { margin-bottom: 14px; }
.ai-imp-sub { font-size: 13px; color: #666; margin-bottom: 6px; }
.ai-imp-herbs { display: flex; flex-wrap: wrap; gap: 6px 14px; line-height: 1.8; }
.ai-imp-herb.unknown { color: #e6a23c; }
.ai-imp-warn { font-style: normal; font-size: 12px; margin-left: 2px; }
.ai-imp-mod { margin-bottom: 4px; }
.ai-imp-mod-label { font-weight: 500; }
.ai-imp-mod-add { color: #2e7d32; margin-left: 8px; font-size: 13px; }
.ai-imp-mod-del { color: #c0392b; margin-left: 8px; font-size: 13px; }
</style>
