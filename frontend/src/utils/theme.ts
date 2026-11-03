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

export function applyTheme(key: ThemeKey): void {
  document.documentElement.setAttribute('data-theme', key)
  localStorage.setItem(STORAGE_KEY, key)
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