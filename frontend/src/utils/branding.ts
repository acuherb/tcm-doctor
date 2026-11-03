/**
 * 品牌工具：按系统配置（诊所名称 / 诊所 Logo）同步浏览器标签的标题与图标。
 * 供 App 启动、登录页、系统设置页三处共用，避免同一逻辑各写一份导致漏改。
 */

export const DEFAULT_TITLE = '中医诊所管理平台'
export const DEFAULT_FAVICON = '/favicon.svg'
export const FAVICON_ENDPOINT = '/api/v1/favicon'

/** 按诊所名称更新浏览器标签标题（空名回退默认） */
export function setTitle(name?: string | null): void {
  document.title = name?.trim() || DEFAULT_TITLE
}

/**
 * 只保留一个 rel="icon" 元素并写入目标地址。
 * 多个 icon 并存时浏览器取后一个，会导致自定义 Logo 被默认 SVG 覆盖，故写入前先清理多余的。
 */
function writeIconLink(href: string, type: string): void {
  const links = Array.from(document.head.querySelectorAll<HTMLLinkElement>('link[rel="icon"]'))
  const link = links[0] || document.head.appendChild(document.createElement('link'))
  link.rel = 'icon'
  link.href = href
  link.type = type
  links.slice(1).forEach((el) => el.remove())
}

/** 从 data URL 头部解析 MIME，如 data:image/jpeg;base64,xxx → image/jpeg */
function mimeOf(dataUrl: string): string {
  const semi = dataUrl.indexOf(';')
  return dataUrl.startsWith('data:') && semi > 5 ? dataUrl.slice(5, semi) : 'image/png'
}

/** 按 Logo 设置浏览器标签图标；传空值回退默认 SVG */
export function setFavicon(dataUrl?: string | null): void {
  if (!dataUrl) {
    writeIconLink(DEFAULT_FAVICON, 'image/svg+xml')
    return
  }
  writeIconLink(dataUrl, mimeOf(dataUrl))
}

/**
 * 让后端图标端点带上新版本号，促使已打开的标签页重新拉取。
 * 后端端点带 300 秒缓存，改 Logo 后若不换 URL，浏览器会继续显示旧图。
 */
export function bustFaviconCache(): void {
  const stamp = Date.now()
  document.head.querySelectorAll<HTMLLinkElement>('link[rel="icon"]').forEach((el) => {
    if (el.href.startsWith('data:')) return
    const base = el.href.split('?')[0]
    if (base.endsWith(FAVICON_ENDPOINT)) el.href = `${base}?v=${stamp}`
  })
}

/** 一次性同步标题与图标 */
export function applyBranding(name?: string | null, logo?: string | null): void {
  setTitle(name)
  setFavicon(logo)
  bustFaviconCache()
}