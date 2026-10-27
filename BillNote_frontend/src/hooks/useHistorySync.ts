import { useEffect } from 'react'
import { useTaskStore, type Task } from '@/store/taskStore'
import { get_note_list, get_note_result, type ServerNote } from '@/services/note.ts'

// 本地 IndexedDB 只是缓存：以服务端 note_results 为准同步历史，任何浏览器 / 设备看到同一份列表

const waitForHydration = () =>
  new Promise<void>(resolve => {
    if (useTaskStore.persist.hasHydrated()) return resolve()
    const unsub = useTaskStore.persist.onFinishHydration(() => {
      unsub()
      resolve()
    })
  })

const VIDEO_URL: Record<string, (id: string) => string> = {
  bilibili: id => `https://www.bilibili.com/video/${id}`,
  youtube: id => `https://www.youtube.com/watch?v=${id}`,
  douyin: id => `https://www.douyin.com/video/${id}`,
}

const toTask = async (note: ServerNote): Promise<Task | null> => {
  const res = await get_note_result(note.task_id)
  if (res?.status !== 'SUCCESS' || !res.result) return null

  const { markdown, transcript, audio_meta } = res.result
  const createdAt = new Date(note.created_at).toISOString()
  const platform = note.form_data?.platform || audio_meta?.platform || ''
  // 老笔记没有保存请求参数，按平台 + 视频 ID 还原链接，其余留空
  const formData = note.form_data ?? {
    video_url: VIDEO_URL[platform]?.(audio_meta?.video_id) ?? '',
    platform,
  }

  return {
    id: note.task_id,
    status: 'SUCCESS',
    markdown: [
      {
        ver_id: `${note.task_id}-server`,
        content: markdown,
        style: formData.style || '',
        model_name: formData.model_name || '',
        created_at: createdAt,
      },
    ],
    transcript,
    audioMeta: audio_meta,
    createdAt,
    platform,
    formData,
  } as Task
}

export const useHistorySync = (enabled: boolean) => {
  useEffect(() => {
    if (!enabled) return

    let running = false
    const sync = async () => {
      if (running) return
      running = true
      try {
        await waitForHydration()
        const notes = await get_note_list()
        const known = new Set(useTaskStore.getState().tasks.map(t => t.id))

        const fetched: Task[] = []
        for (const note of notes.filter(n => !known.has(n.task_id))) {
          try {
            const task = await toTask(note)
            if (task) fetched.push(task)
          } catch (e) {
            console.warn('同步笔记失败', note.task_id, e)
          }
        }

        useTaskStore.getState().mergeServerNotes(notes, fetched)
      } catch (e) {
        console.warn('同步服务端历史失败', e)
      } finally {
        running = false
      }
    }

    sync()
    const onVisible = () => {
      if (document.visibilityState === 'visible') sync()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [enabled])
}
