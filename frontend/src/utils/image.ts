/**
 * 图片压缩工具：将相机/相册大图在前端用 canvas 压缩为 webp，
 * 用于（1）绕过后端 5MB 上传限制；（2）大幅减小存进数据库的体积。
 */

// 压缩后的图片最长边
const MAX_DIM = 1600
// webp 编码质量
const QUALITY = 0.8
// 小于该体积的图片直接放行，避免无谓重绘
const SKIP_THRESHOLD = 300 * 1024

/**
 * 将图片文件压缩为 webp Blob。
 * 返回压缩后的 Blob（文件名与原文件相同，便于 FormData 上传）。
 */
export function compressImageFile(file: File): Promise<File> {
  return new Promise((resolve, reject) => {
    if (file.size < SKIP_THRESHOLD) {
      resolve(file)
      return
    }
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      URL.revokeObjectURL(url)
      let { width, height } = img
      if (width > MAX_DIM || height > MAX_DIM) {
        if (width >= height) {
          height = Math.round((height * MAX_DIM) / width)
          width = MAX_DIM
        } else {
          width = Math.round((width * MAX_DIM) / height)
          height = MAX_DIM
        }
      }
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        reject(new Error('canvas 不可用'))
        return
      }
      ctx.drawImage(img, 0, 0, width, height)
      // 优先 webp，不支持则回退 jpeg
      const mime = canvas.toDataURL('image/webp', QUALITY).startsWith('data:image/webp')
        ? 'image/webp'
        : 'image/jpeg'
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error('图片压缩失败'))
            return
          }
          const ext = mime === 'image/webp' ? 'webp' : 'jpg'
          const name = file.name.replace(/\.[^.]+$/, '') + '.' + ext
          resolve(new File([blob], name, { type: mime }))
        },
        mime,
        QUALITY
      )
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      resolve(file)
    }
    img.src = url
  })
}

// 品牌 Logo 用途的最大边长：页面展示仅 72px，取 256 兼顾 2 倍屏清晰度
const LOGO_MAX_DIM = 256

/**
 * 将图片压缩为 webp data URL，供诊所 Logo 等需要以字符串入库的场景使用。
 * 与 compressImageFile 的区别：不做体积放行判断，小图同样转码，保证格式统一为 webp。
 */
export function compressToDataUrl(file: File, maxDim = LOGO_MAX_DIM, quality = QUALITY): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      URL.revokeObjectURL(url)
      let { width, height } = img
      if (width > maxDim || height > maxDim) {
        if (width >= height) {
          height = Math.round((height * maxDim) / width)
          width = maxDim
        } else {
          width = Math.round((width * maxDim) / height)
          height = maxDim
        }
      }
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        reject(new Error('canvas 不可用'))
        return
      }
      // 透明背景填充白色，避免 webp 透明区在处方笺白纸上显示异常
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, width, height)
      ctx.drawImage(img, 0, 0, width, height)
      // 优先 webp，不支持则回退 jpeg
      const dataUrl = canvas.toDataURL('image/webp', quality)
      resolve(dataUrl.startsWith('data:image/webp') ? dataUrl : canvas.toDataURL('image/jpeg', quality))
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片读取失败'))
    }
    img.src = url
  })
}