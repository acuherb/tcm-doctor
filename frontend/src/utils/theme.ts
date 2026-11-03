export type ThemeKey = 'herbal' | 'ink' | 'vermilion' | 'jade'

export interface ThemeOption {
  key: ThemeKey
  label: string
  desc: string
  swatches: string[]
}

export const THEMES: ThemeOption[] = [
  { key: 'herbal', label: '本草', desc: '深褐暖金，经典中药色调', swatches: ['#8B4513', '#D4A574', '#2C1810'] },
  { key: 'ink', label: '墨色', desc: '墨青灰蓝，沉静克制', swatches: ['#2F4858', '#7FB3C7', '#1E282D'] },
  { key: 'vermilion', label: '朱砂', desc: '红木朱红，典雅庄重', swatches: ['#A0362A', '#E0A080', '#3D1D18'] },
  { key: 'jade', label: '青玉', desc: '竹长青玉，清雅舒缓', swatches: ['#4A7C59', '#A8CBAF', '#22372A'] },
]

const STORAGE_KEY = 'tcm-theme'
const DEFAULT_THEME: ThemeKey = 'herbal'

// 主题变更订阅（ECharts 等无法读取 CSS 变量的场景，需要在切换后重绘）
const listeners = new Set<() => void>()

export function onThemeChange(fn: () => void): () => void {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

/* 读取当前主题变量（图表配置是 JS 对象，读不到 CSS 变量，需运行时取值） */
export function themeVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/* 同步主题变量（attrs 名称 → 值），用于 ECharts 配置 */
export function themeVars(names: string[]): Record<string, string> {
  const out: Record<string, string> = {}
  names.forEach((n) => {
    out[n] = themeVar(n)
  })
  return out
}

export function applyTheme(key: ThemeKey): void {
  document.documentElement.setAttribute('data-theme', key)
  localStorage.setItem(STORAGE_KEY, key)
  // 等样式重算完成后再通知，确保订阅方读到的变量已是新主题的值
  if (typeof requestAnimationFrame !== 'undefined') {
    requestAnimationFrame(() => {
      listeners.forEach((fn) => fn())
    })
  } else {
    listeners.forEach((fn) => fn())
  }
}

export function getStoredTheme(): ThemeKey {
  const stored = localStorage.getItem(STORAGE_KEY) as ThemeKey | null
  return stored && THEMES.some((t) => t.key === stored) ? stored : DEFAULT_THEME
}

export function isThemeKey(value: string): value is ThemeKey {
  return THEMES.some((t) => t.key === value)
}

export function initTheme(): void {
  applyTheme(getStoredTheme())
}