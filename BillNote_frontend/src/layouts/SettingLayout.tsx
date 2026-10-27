import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'
import { Link, Outlet } from 'react-router-dom'
import { SlidersHorizontal } from 'lucide-react'
import React from 'react'
import logo from '@/assets/icon.svg'

interface ISettingLayoutProps {
  Menu: React.ReactNode
}
const SettingLayout = ({ Menu }: ISettingLayoutProps) => {
  return (
    <div
      className="h-full w-full"
      style={{
        backgroundColor: 'var(--color-muted)',
      }}
    >
      {/* 手机：菜单变成顶部横向一行，内容在下方；md 以上保持左右两栏 */}
      <div className="flex h-dvh flex-col md:h-auto md:flex-1 md:flex-row">
        {/* 左侧部分：Header + 表单 */}
        <aside className="flex shrink-0 flex-col border-b border-neutral-200 bg-white md:w-[300px] md:border-r md:border-b-0">
          {/* Header */}
          <header className="flex h-12 items-center justify-between px-4 md:h-16 md:px-6">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center overflow-hidden rounded-2xl md:h-10 md:w-10">
                <img src={logo} alt="logo" className="h-full w-full object-contain" />
              </div>
              <div className="text-lg font-bold text-gray-800 md:text-2xl">BiliNote</div>
            </div>
            <div>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <Link to={'/'}>
                      <SlidersHorizontal className="text-muted-foreground hover:text-primary cursor-pointer" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>
                    <span>返回首页</span>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </header>

          {/* 表单内容 */}
          <div className="overflow-x-auto px-2 pb-2 [scrollbar-width:none] md:flex-1 md:overflow-auto md:p-4 md:[scrollbar-width:auto]">
            {/*<NoteForm />*/}
            {Menu}
          </div>
        </aside>

        {/* 右侧预览区域 */}
        <main className="min-h-0 flex-1 overflow-hidden md:h-screen">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
export default SettingLayout
