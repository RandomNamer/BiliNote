import { useEffect, useState } from 'react'

// 与 Tailwind 的 md 断点（768px）一致：窄于它按手机布局渲染
const QUERY = '(max-width: 767px)'

export const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(() => window.matchMedia(QUERY).matches)

  useEffect(() => {
    const media = window.matchMedia(QUERY)
    const onChange = () => setIsMobile(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  return isMobile
}
