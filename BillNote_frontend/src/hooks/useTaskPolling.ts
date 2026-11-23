import { useEffect, useRef } from 'react'
import { useTaskStore } from '@/store/taskStore'
import { get_task_status } from '@/services/note.ts'
import toast from 'react-hot-toast'

// A failed *request* is not a failed *task*: a phone tab in the background, a locked screen or a
// Wi-Fi blip makes polls fail while the backend keeps working. Only the server's own FAILED status
// ends a task. As a safety net, a task is given up after this many consecutive request errors
// while the page is visible (40 × 3 s ≈ 2 min of the backend being unreachable).
const MAX_CONSECUTIVE_ERRORS = 40

export const useTaskPolling = (interval = 3000) => {
  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)

  const tasksRef = useRef(tasks)
  const errorCounts = useRef(new Map<string, number>())

  // 每次 tasks 更新，把最新的 tasks 同步进去
  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  useEffect(() => {
    const timer = setInterval(async () => {
      // Background tabs get throttled and their requests often fail; poll again once visible.
      if (document.visibilityState === 'hidden') return

      const pendingTasks = tasksRef.current.filter(
        task => task.status != 'SUCCESS' && task.status != 'FAILED'
      )

      // 无活跃任务时跳过轮询
      if (pendingTasks.length === 0) return

      for (const task of pendingTasks) {
        try {
          const res = await get_task_status(task.id)
          errorCounts.current.delete(task.id)
          const { status } = res

          if (status && status !== task.status) {
            if (status === 'SUCCESS') {
              const { markdown, transcript, audio_meta } = res.result
              toast.success('笔记生成成功')
              updateTaskContent(task.id, {
                status,
                markdown,
                transcript,
                audioMeta: audio_meta,
              })
            } else if (status === 'FAILED') {
              updateTaskContent(task.id, { status })
              toast.error('笔记生成失败，请稍后重试')
              console.warn(`⚠️ 任务 ${task.id} 失败`)
            } else {
              updateTaskContent(task.id, { status })
            }
          }
        } catch (e) {
          const n = (errorCounts.current.get(task.id) ?? 0) + 1
          errorCounts.current.set(task.id, n)
          console.warn(`任务状态查询失败（第 ${n} 次），稍后重试：`, e)
          if (n >= MAX_CONSECUTIVE_ERRORS) {
            errorCounts.current.delete(task.id)
            updateTaskContent(task.id, { status: 'FAILED' })
            toast.error('无法连接后端，已停止查询该笔记状态')
          }
        }
      }
    }, interval)

    return () => clearInterval(timer)
  }, [interval])
}
