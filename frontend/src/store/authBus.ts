// 轻量登出总线：解耦 api 拦截器与 auth store，避免循环依赖与动态导入警告
type LogoutHandler = () => void

let handler: LogoutHandler | null = null

export function setLogoutHandler(fn: LogoutHandler): void {
  handler = fn
}

export function triggerLogout(): void {
  handler?.()
}
