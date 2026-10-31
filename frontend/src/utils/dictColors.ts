// 字典词条颜色工具：六经/脉类/舌色/五行本色，供多处视图复用（一次拉取、模块级缓存）
import { ref } from 'vue'
import api from '@/utils/api'

// 证型=六经五色(太阳寒水黑蓝/阳明燥金白/少阳相火红/太阴湿土黄/少阴君火紫/厥阴风木青)
export const SYNDROME_MERIDIAN_COLOR: Record<string, string> = {
  '太阳': '#2c3e50', '阳明': '#cfd8dc', '少阳': '#d9434e',
  '太阴': '#e0a82e', '少阴': '#8e44ad', '厥阴': '#2e9e5b',
}
// 脉象=脉类(浮表青蓝/沉里黑/迟寒蓝/数热红/虚灰/实棕红/滑痰饮黄/涩血瘀紫/弦肝胆青绿/洪热盛橙/细血虚淡粉/缓湿黄褐/微浅灰/紧寒束深蓝)
export const PULSE_TYPE_COLOR: Record<string, string> = {
  '浮脉类': '#3498db', '沉脉类': '#2c3e50', '迟脉类': '#2980b9', '数脉类': '#d9434e',
  '虚脉类': '#95a5a6', '实脉类': '#a93226', '滑脉类': '#e0a82e', '涩脉类': '#8e44ad',
  '弦脉类': '#16a085', '洪脉类': '#e67e22', '细脉类': '#d988a0', '缓脉类': '#b9770e',
  '微脉类': '#bdc3c7', '紧脉类': '#1f618d',
}
// 舌象=色/苔关键词(有序：紫先于青、绛先于红)
export const TONGUE_KEYWORD_COLOR: [string, string][] = [
  ['绛', '#a93226'], ['紫', '#8e44ad'], ['青', '#2e9e5b'], ['红', '#d9434e'],
  ['淡', '#aebfd0'], ['白', '#cfd8dc'], ['黄', '#e0a82e'], ['灰', '#7f8c8d'],
  ['黑', '#2c3e50'], ['少', '#95a5a6'], ['无', '#95a5a6'], ['花', '#95a5a6'], ['滑', '#aed6f1'],
]
// 药材性味=五行本色(酸青苦赤甘黄辛白咸黑；四气寒蓝→温红)
export const HERB_TAG_DEFAULT_COLOR: Record<string, string> = {
  '酸': '#2e9e5b', '苦': '#d9434e', '甘': '#e0a82e', '辛': '#9fb3c8', '咸': '#2f3b47', '淡': '#b0a0c0',
  '寒': '#2f80b5', '微寒': '#5aa0cf', '平': '#7f9a6e', '微温': '#e08a3c', '温': '#d9642c', '热': '#c0392b',
}

// 由脉名推断脉类（自定义/非字典脉名时回退着色用）
const PULSE_NAME_KEYWORD: [string, string][] = [
  ['浮', '浮脉类'], ['沉', '沉脉类'], ['迟', '迟脉类'], ['数', '数脉类'],
  ['虚', '虚脉类'], ['实', '实脉类'], ['滑', '滑脉类'], ['涩', '涩脉类'],
  ['弦', '弦脉类'], ['洪', '洪脉类'], ['细', '细脉类'], ['缓', '缓脉类'],
  ['微', '微脉类'], ['紧', '紧脉类'],
]

export function tongueColor(name: string): string {
  for (const [kw, col] of TONGUE_KEYWORD_COLOR) if (name.includes(kw)) return col
  return '#909399'
}

// 默认色（字典无该色时回退），extra 携带 meridian/pulse_type 等定位字段
export function defaultColorForType(termType: string, name: string, extra?: any): string {
  if (termType === 'herb_tag') return HERB_TAG_DEFAULT_COLOR[name] || '#909399'
  if (termType === 'syndrome') {
    const mer = (extra?.meridian || '').split(',')[0]?.trim()
    return SYNDROME_MERIDIAN_COLOR[mer] || '#7f8c8d'
  }
  if (termType === 'tongue') return tongueColor(name)
  if (termType === 'pulse') {
    const pt = extra?.pulse_type || PULSE_NAME_KEYWORD.find(([k]) => name.includes(k))?.[1]
    return PULSE_TYPE_COLOR[pt || ''] || '#7f8c8d'
  }
  return '#909399'
}

// 依据颜色亮度返回可读前景色（浅色用深字/深边框，深色用浅字），避免白色等浅色导致标签不可见
export function readableInk(hex: string): string {
  const c = (hex || '').replace('#', '')
  if (c.length < 6) return '#333333'
  const r = parseInt(c.slice(0, 2), 16)
  const g = parseInt(c.slice(2, 4), 16)
  const b = parseInt(c.slice(4, 6), 16)
  const L = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return L > 0.6 ? '#333333' : '#ffffff'
}

// 模块级缓存：全应用共享一次字典拉取
const colorMap = ref<Record<string, string>>({})
let loaded = false
let loadingPromise: Promise<void> | null = null

export function useDictColors() {
  if (!loaded && !loadingPromise) {
    loadingPromise = (api.get('/dictionaries') as Promise<any>).then((res: any) => {
      const arr = Array.isArray(res) ? res : []
      const m: Record<string, string> = {}
      for (const t of arr) {
        if (t.name) m[t.name] = t.color || defaultColorForType(t.term_type, t.name, t)
      }
      colorMap.value = m
      loaded = true
    }).catch(() => { loaded = true })
  }
  // 取词条颜色：字典色优先，缺失回退默认色
  function termColor(name: string, termType: string, extra?: any): string {
    return colorMap.value[name] || defaultColorForType(termType, name, extra)
  }
  return { colorMap, termColor }
}
