"""服务端笔记历史：让任何浏览器 / 设备都能看到同一份历史。

前端历史原本只存在各自浏览器的 IndexedDB 里，而笔记本身一直在 NOTE_OUTPUT_DIR。
这里把 NOTE_OUTPUT_DIR 作为历史的唯一来源：列出所有已完成的笔记，并支持真正删除。
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.engine import get_db
from app.db.models.video_tasks import VideoTask
from app.utils.logger import get_logger
from app.utils.response import ResponseWrapper as R

logger = get_logger(__name__)
router = APIRouter()

NOTE_OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
# 最终结果文件形如 <uuid4>.json；_audio / _transcript / .status 等缓存文件不匹配
RESULT_FILE = re.compile(r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.json$")
TASK_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _audio_meta(task_id: str) -> dict:
    # _audio.json 只有几百字节；缺失时（老版本笔记）才去读完整结果文件
    meta = _read_json(NOTE_OUTPUT_DIR / f"{task_id}_audio.json")
    if meta is None:
        meta = (_read_json(NOTE_OUTPUT_DIR / f"{task_id}.json") or {}).get("audio_meta") or {}
    meta.pop("raw_info", None)
    return meta


def note_created_at(task_id: str) -> str | None:
    """笔记的创建时间，所有设备都按它排序。

    提交时记在 <task_id>_request.json 的 created_at 里，重试 / 重新生成都沿用（见 routers/note.py）。
    之前的老笔记没有记录：取该任务所有文件里最早的 mtime（转写 / 音频缓存，最接近提交时间）；
    结果文件的 mtime 是完成时间，重新生成后还会变。一个文件都没有时返回 None。
    """
    request = _read_json(NOTE_OUTPUT_DIR / f"{task_id}_request.json") or {}
    if request.get("created_at"):
        return request["created_at"]

    mtimes = []
    for path in NOTE_OUTPUT_DIR.glob(f"{task_id}*"):
        try:
            mtimes.append(path.stat().st_mtime)
        except OSError:
            pass
    if not mtimes:
        return None
    return datetime.fromtimestamp(min(mtimes), tz=timezone.utc).isoformat()


@router.get("/note_list")
def note_list():
    if not NOTE_OUTPUT_DIR.exists():
        return R.success([])

    notes = []
    for entry in os.scandir(NOTE_OUTPUT_DIR):
        match = RESULT_FILE.match(entry.name)
        if not match:
            continue
        task_id = match.group(1)
        form_data = _read_json(NOTE_OUTPUT_DIR / f"{task_id}_request.json")
        if form_data:
            form_data.pop("created_at", None)
        notes.append({
            "task_id": task_id,
            "created_at": note_created_at(task_id),
            "audio_meta": _audio_meta(task_id),
            "form_data": form_data,
        })

    notes.sort(key=lambda n: n["created_at"], reverse=True)
    return R.success(notes)


class DeleteNoteRequest(BaseModel):
    task_id: str


@router.post("/delete_note")
def delete_note(data: DeleteNoteRequest):
    task_id = data.task_id
    if not TASK_ID.match(task_id):
        return R.error(msg="非法的 task_id", code=400)

    removed = []
    for path in NOTE_OUTPUT_DIR.glob(f"{task_id}*"):
        try:
            path.unlink()
            removed.append(path.name)
        except Exception as e:
            logger.warning(f"删除笔记文件失败 {path}: {e}")

    db = next(get_db())
    try:
        db.query(VideoTask).filter_by(task_id=task_id).delete()
        db.commit()
    except Exception as e:
        logger.warning(f"删除任务记录失败 (task_id={task_id}): {e}")
    finally:
        db.close()

    try:
        from app.services.vector_store import VectorStoreManager
        VectorStoreManager().delete_index(task_id)
    except Exception as e:
        logger.warning(f"删除向量索引失败（不影响删除）: {e}")

    logger.info(f"已删除笔记 {task_id}: {removed}")
    return R.success({"task_id": task_id, "removed": removed})
