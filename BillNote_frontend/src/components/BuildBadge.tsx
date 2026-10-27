import { useEffect, useState } from 'react'
import request from '@/utils/request'

// 构建标识角标：显示当前页面是哪次构建；若后端已是新构建而页面还是旧的
//（例如被 Cloudflare 之类的缓存按 TTL 留住），提示刷新
const SHA = __BUILD_SHA__
const TIME = __BUILD_TIME__

const formatTime = (iso: string) => {
  const d = new Date(iso)
  if (!iso || Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export const buildLabel = () =>
  SHA
    ? `v${__APP_VERSION__} · ${SHA.slice(0, 7)} · ${formatTime(TIME)}`
    : `v${__APP_VERSION__} · dev`

const BuildBadge = ({ className = '' }: { className?: string }) => {
  const [stale, setStale] = useState(false)

  useEffect(() => {
    if (!SHA) return
    const check = async () => {
      try {
        const health = (await request.get('/sys_health', { suppressToast: true })) as unknown as {
          build?: { sha?: string } | null
        }
        const serverSha = health?.build?.sha
        setStale(!!serverSha && serverSha !== SHA)
      } catch {
        // 后端不可达由其它组件提示，这里不打扰
      }
    }
    check()
    const onVisible = () => {
      if (document.visibilityState === 'visible') check()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [])

  if (stale) {
    return (
      <button
        onClick={() => window.location.reload()}
        className={`text-xs font-medium text-amber-600 hover:underline ${className}`}
        title="服务端已更新，当前页面来自旧的构建（可能被缓存）"
      >
        页面是旧版本，点此刷新
      </button>
    )
  }

  return (
    <span
      className={`text-muted-foreground font-mono text-[11px] whitespace-nowrap ${className}`}
      title={SHA ? `构建 ${SHA}\n时间 ${TIME}` : '本地开发构建'}
    >
      {buildLabel()}
    </span>
  )
}

export default BuildBadge
