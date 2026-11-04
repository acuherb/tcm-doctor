/**
 * 搜索输入防抖：连续输入只在停止 delay 毫秒后执行一次。
 * 用于患者远程搜索下拉，避免逐键触发 HTTP 请求。
 */
export interface Debounced<A extends unknown[]> {
  (...args: A): void
  cancel(): void
}

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
