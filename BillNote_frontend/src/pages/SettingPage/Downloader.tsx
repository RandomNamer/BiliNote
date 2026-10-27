import { Outlet } from 'react-router-dom'
import Options from '@/components/Form/DownloaderForm/Options.tsx'
import ProxyConfig from '@/components/Form/DownloaderForm/ProxyConfig.tsx'
const Downloader = () => {
  return (
    // 手机上上下堆叠、整页滚动；md 以上左右分栏
    <div className={'flex h-full flex-col overflow-y-auto bg-white md:flex-row md:overflow-hidden'}>
      <div
        className={
          'flex flex-col gap-3 border-b border-neutral-200 p-2 md:flex-1/5 md:overflow-y-auto md:border-r md:border-b-0'
        }
      >
        <ProxyConfig />
        <Options></Options>
      </div>
      <div className={'md:flex-4/5'}>
        <Outlet />
      </div>
    </div>
  )
}
export default Downloader
