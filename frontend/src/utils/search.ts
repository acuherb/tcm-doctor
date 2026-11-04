/**
 * 前端搜索公共能力：防抖、响应竞态守卫、跨组件共享的药材字典缓存。
 *
 * 背景：全项目原先仅 BookLibrary 一处防抖、0 处请求竞态保护；处方编辑器里每味药
 * 各渲染一个 HerbSelector，各自 onMounted 拉一次全量 /herbs（N 味药 = N 个并发请求）。
 * 这里用模块级单例统一治理：搜索请求按序号只采信最后一次；药材全量列表全局只拉一次。
 */
import api from '@/utils/api'
import type { Herb } from '@/types'

export interface Debounced<A extends unknown[]> {
  (...args: A): void
  cancel(): void
}

/** 防抖：连续输入只在停止 delay 毫秒后执行一次。 */
export function debounce<A extends unknown[]>(
  fn: (...args: A) => void, delay = 300,
): Debounced<A> {
  let timer: ReturnType<typeof setTimeout> | null = null
  const wrapped = (...args: A): void => {
    if (timer !== null) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, delay)
  }
  wrapped.cancel = (): void => {
    if (timer !== null) { clearTimeout(timer); timer = null }
  }
  return wrapped as Debounced<A>
}

/**
 * 响应竞态守卫：只有最后一次发起的请求结果会被采用。
 * 比 AbortController 更稳妥——不产生被取消请求的错误提示，拦截器无需改动。
 */
export function createRequestGuard() {
  let seq = 0
  return {
    next(): number { return ++seq },
    isLatest(token: number): boolean { return token === seq },
    /** 外部状态变化（清空/重置）时让所有在途请求失效 */
    invalidate(): void { seq++ },
  }
}

// ── 药材字典共享缓存（模块级单例，跨页面/跨组件实例复用） ──
let herbCache: Herb[] | null = null
let herbPromise: Promise<Herb[]> | null = null

/** 药材被新增/编辑/删除/导入后调用，使缓存失效。 */
export function invalidateHerbCache(): void {
  herbCache = null
  herbPromise = null
}

/**
 * 获取全量药材。同一时刻的并发调用共用同一个 in-flight Promise，
 * 后续调用直接返回缓存；避免 N 个组件实例各发一次 /herbs。
 */
export function getAllHerbs(): Promise<Herb[]> {
  if (herbCache) return Promise.resolve(herbCache)
  if (herbPromise) return herbPromise
  herbPromise = api.get<Herb[]>('/herbs')
    .then((list) => {
      herbCache = list || []
      return herbCache
    })
    .catch(() => {
      herbCache = null
      return [] as Herb[]
    })
    .finally(() => { herbPromise = null })
  return herbPromise
}
