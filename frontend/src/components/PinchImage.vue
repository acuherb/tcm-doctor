<template>
  <span class="pinch-image" :class="thumbClass" @click.stop="open">
    <el-image :src="src" fit="cover" class="pinch-image__thumb" draggable="false" />

    <Teleport to="body">
      <div
        v-if="visible"
        class="pinch-viewer"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @dblclick="onDblClick"
        @wheel="onWheel"
      >
        <img
          :src="current"
          class="pinch-viewer__img"
          :style="imgStyle"
          draggable="false"
          @dragstart.prevent
        />
        <span v-if="hasMultiple" class="pv-nav pv-prev" @click.stop="move(-1)">‹</span>
        <span v-if="hasMultiple" class="pv-nav pv-next" @click.stop="move(1)">›</span>
        <button class="pv-close" @click.stop="close">✕</button>
        <span class="pv-zoom pv-zoom-out" @click.stop="zoomBy(0.8)">−</span>
        <span class="pv-zoom pv-zoom-in" @click.stop="zoomBy(1.25)">＋</span>
        <span class="pv-reset" @click.stop="reset">重置</span>
      </div>
    </Teleport>
  </span>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = withDefaults(defineProps<{
  src: string
  list?: string[]
  index?: number
  thumbClass?: string
}>(), {
  list: () => [],
  index: 0,
  thumbClass: '',
})

const visible = ref(false)
const currentIdx = ref(0)
const scale = ref(1)
const tx = ref(0)
const ty = ref(0)

const current = computed(() => {
  const list = props.list?.length ? props.list : [props.src]
  return list[currentIdx.value] ?? props.src
})
const hasMultiple = computed(() => (props.list?.length || 0) > 1)

const imgStyle = computed(() => ({
  transform: `translate(${tx.value}px, ${ty.value}px) scale(${scale.value})`,
}))

function open() {
  currentIdx.value = props.index
  reset()
  visible.value = true
}

function close() {
  visible.value = false
  reset()
}

function reset() {
  scale.value = 1
  tx.value = 0
  ty.value = 0
}

function zoomBy(factor: number) {
  scale.value = Math.max(0.5, Math.min(8, scale.value * factor))
}

function move(dir: number) {
  const list = props.list?.length ? props.list : [props.src]
  currentIdx.value = (currentIdx.value + dir + list.length) % list.length
  reset()
}

function onDblClick() {
  close()
}

// ---- 指针手势：双指缩放 + 单指/拖动平移 ----
const pointers = new Map<number, { x: number; y: number }>()
let pinchStartDist = 0
let pinchStartScale = 1
let panStartTx = 0
let panStartTy = 0
let panning = false
let lastPanX = 0
let lastPanY = 0

function onPointerDown(e: PointerEvent) {
  if (!visible.value) return
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  if (pointers.size === 2) {
    panning = false
    const [p1, p2] = [...pointers.values()]
    pinchStartDist = Math.hypot(p1.x - p2.x, p1.y - p2.y) || 1
    pinchStartScale = scale.value
  } else if (pointers.size === 1) {
    panning = true
    lastPanX = e.clientX
    lastPanY = e.clientY
    panStartTx = tx.value
    panStartTy = ty.value
  }
}

function onPointerMove(e: PointerEvent) {
  if (!visible.value) return
  const cur = pointers.get(e.pointerId)
  if (!cur) return
  cur.x = e.clientX
  cur.y = e.clientY

  if (pointers.size === 2) {
    panning = false
    const [p1, p2] = [...pointers.values()]
    const dist = Math.hypot(p1.x - p2.x, p1.y - p2.y)
    scale.value = Math.max(0.5, Math.min(8, (pinchStartScale * dist) / pinchStartDist))
  } else if (pointers.size === 1 && panning) {
    tx.value = panStartTx + (e.clientX - lastPanX)
    ty.value = panStartTy + (e.clientY - lastPanY)
    if (e.pointerType === 'mouse' && (e.buttons & 1) === 0) {
      onPointerUp(e)
    }
  }
}

function onPointerUp(e: PointerEvent) {
  pointers.delete(e.pointerId)
  panning = false
}

// 滚轮缩放（桌面）
function onWheel(e: WheelEvent) {
  if (!visible.value) return
  e.preventDefault()
  const factor = e.deltaY > 0 ? 0.9 : 1.1
  zoomBy(factor)
}
</script>

<style scoped>
.pinch-image {
  display: inline-block;
  position: relative;
  line-height: 0;
  cursor: zoom-in;
}
.pinch-image__thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: inherit;
}
.pinch-viewer {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(0, 0, 0, 0.88);
  display: flex;
  align-items: center;
  justify-content: center;
  touch-action: none;
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
}
.pinch-viewer__img {
  max-width: 96vw;
  max-height: 92vh;
  width: auto;
  height: auto;
  cursor: grab;
  will-change: transform;
  transition: transform 0.08s ease-out;
  object-fit: contain;
}
.pinch-viewer__img:active {
  cursor: grabbing;
}
.pv-close {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 3001;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: 18px;
  cursor: pointer;
}
.pv-nav {
  position: fixed;
  top: 50%;
  transform: translateY(-50%);
  z-index: 3001;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: 28px;
  line-height: 40px;
  text-align: center;
  cursor: pointer;
}
.pv-prev { left: 12px; }
.pv-next { right: 12px; }
.pv-zoom {
  position: fixed;
  bottom: 36px;
  z-index: 3001;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: 24px;
  line-height: 40px;
  text-align: center;
  cursor: pointer;
}
.pv-zoom-out { right: 66px; }
.pv-zoom-in { right: 12px; }
.pv-reset {
  position: fixed;
  bottom: 48px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3001;
  color: #fff;
  background: rgba(255, 255, 255, 0.15);
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 13px;
  cursor: pointer;
}

@media (max-width: 767px) {
  .pv-prev { left: 8px; }
  .pv-next { right: 8px; }
  .pv-zoom-out { right: 56px; }
  .pv-zoom-in { right: 8px; }
}
</style>