import Provider from '@/components/Form/modelForm/Provider.tsx'
import { Outlet } from 'react-router-dom'

const Model = () => {
  return (
    // 手机上列表和表单上下堆叠、整页滚动；md 以上左右分栏各自滚动
    <div
      className={
        'flex h-full min-h-0 flex-col overflow-y-auto bg-white md:flex-row md:overflow-hidden'
      }
    >
      <div
        className={
          'border-b border-neutral-200 p-2 md:min-h-0 md:flex-1/5 md:overflow-y-auto md:border-r md:border-b-0'
        }
      >
        <Provider></Provider>
      </div>
      <div className={'md:min-h-0 md:flex-4/5 md:overflow-y-auto'}>
        <Outlet />
      </div>
    </div>
  )
}
export default Model
