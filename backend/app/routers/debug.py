"""Read-only debug endpoints: logs, recent tasks, effective config — over plain HTTP.

Why: diagnosing the homelab deployment otherwise needs an SSH session to the Docker host for every
question ("why did this note fail?"). These endpoints expose the same information read-only.

Access: only from addresses in DEBUG_ALLOW_IPS (default: the homelab control node and loopback).
Behind the bundled nginx the backend sees 127.0.0.1, so the client address is taken from
X-Real-IP, which nginx always overwrites with $remote_addr (a client can't spoof it). The backend
port itself is not published by the container. Public traffic that arrives through a tunnel
comes from the tunnel host's address and is refused. Secrets are masked in every response.

  GET /api/debug/logs?name=app|backend|nginx_access|nginx_error|supervisord&lines=200&grep=REGEX
  GET /api/debug/tasks?limit=20
  GET /api/debug/config
"""
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter()

ALLOW = {ip.strip() for ip in os.getenv("DEBUG_ALLOW_IPS", "192.168.50.99,127.0.0.1").split(",") if ip.strip()}

LOGS = {
    "app": "logs/app.log",
    "backend": "/var/log/supervisor/backend.log",
    "supervisord": "/var/log/supervisor/supervisord.log",
    "nginx_access": "/var/log/nginx/access.log",
    "nginx_error": "/var/log/nginx/error.log",
}
MAX_TAIL_BYTES = 8 * 1024 * 1024

_SECRETS = [
    (re.compile(r"(sk-(?:ant-)?)[A-Za-z0-9_\-]{6,}"), r"\1…"),
    (re.compile(r"\b(AIza|AQ\.)[A-Za-z0-9_\-\.]{8,}"), r"\1…"),
    (re.compile(r"(?i)\b(SESSDATA|bili_jct|DedeUserID__ckMd5|buvid\d?|sid|msToken|ttwid|odin_tt|passport_csrf_token)=[^;\s'\"&]+"), r"\1=…"),
    (re.compile(r"(?i)(\"?(?:api_key|apikey|token|password|secret|cookie)\"?\s*[:=]\s*)(['\"])([^'\"]{4,})(['\"])"), r"\1\2…\4"),
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9_\-\.]{8,}"), r"\1…"),
]


def _redact(text: str) -> str:
    for pat, rep in _SECRETS:
        text = pat.sub(rep, text)
    return text


def _client_ip(request: Request) -> str:
    host = request.client.host if request.client else ""
    if host in ("127.0.0.1", "::1"):
        return request.headers.get("x-real-ip", host)
    return host


def _guard(request: Request) -> None:
    ip = _client_ip(request)
    if ip not in ALLOW:
        raise HTTPException(status_code=403, detail=f"debug endpoints are not available from {ip}")


def _tail(path: Path, lines: int) -> str:
    size = path.stat().st_size
    with path.open("rb") as f:
        f.seek(max(0, size - MAX_TAIL_BYTES))
        data = f.read().decode("utf-8", errors="replace")
    # yt-dlp progress lines use \r; make each update its own line
    rows = data.replace("\r", "\n").splitlines()
    return rows[-lines:] if lines else rows


@router.get("/debug/logs")
def debug_logs(request: Request, name: str = Query("app"), lines: int = Query(200, ge=1, le=5000),
               grep: str | None = Query(None)):
    _guard(request)
    rel = LOGS.get(name)
    if rel is None:
        raise HTTPException(status_code=400, detail=f"unknown log; one of {sorted(LOGS)}")
    path = Path(rel)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{rel} does not exist")
    rows = _tail(path, 0 if grep else lines)
    if grep:
        try:
            rx = re.compile(grep)
        except re.error as e:
            raise HTTPException(status_code=400, detail=f"bad regex: {e}")
        rows = [r for r in rows if rx.search(r)][-lines:]
    return PlainTextResponse(_redact("\n".join(rows)) + "\n")


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


@router.get("/debug/tasks")
def debug_tasks(request: Request, limit: int = Query(20, ge=1, le=200)):
    _guard(request)
    out_dir = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
    reqs = sorted(out_dir.glob("*_request.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    tasks = []
    for rp in reqs:
        tid = rp.name[: -len("_request.json")]
        req = _read_json(rp) or {}
        status = _read_json(out_dir / f"{tid}.status.json") or {}
        files = {}
        for suffix in ("_request.json", "_audio.json", "_transcript.json", "_markdown.md", ".json", ".status.json"):
            fp = out_dir / f"{tid}{suffix}"
            if fp.exists():
                st = fp.stat()
                files[suffix] = {"mtime": st.st_mtime, "bytes": st.st_size}
        transcript = _read_json(out_dir / f"{tid}_transcript.json") or {}
        raw = transcript.get("raw") or {}
        audio = _read_json(out_dir / f"{tid}_audio.json") or {}
        tasks.append({
            "task_id": tid,
            "created_at": req.get("created_at"),
            "video_url": req.get("video_url"),
            "provider_id": req.get("provider_id"),
            "model_name": req.get("model_name"),
            "video_understanding": req.get("video_understanding"),
            "format": req.get("format"),
            "status": status.get("status"),
            "message": status.get("message"),
            "title": audio.get("title"),
            "duration_s": audio.get("duration"),
            "transcript": {
                "language": transcript.get("language"),
                "segments": len(transcript.get("segments") or []),
                "engine": "bcut" if "utterances" in raw else ("openai-compatible" if "segments" in raw else None),
            } if transcript else None,
            "files": files,
        })
    return JSONResponse(json.loads(_redact(json.dumps({"tasks": tasks}, ensure_ascii=False))))


@router.get("/debug/config")
def debug_config(request: Request):
    _guard(request)
    from app.services.provider import ProviderService
    from app.routers.config import _build_info

    providers = []
    try:
        for p in ProviderService.get_all_providers() or []:
            p = dict(p) if not isinstance(p, dict) else p
            providers.append({"id": p.get("id"), "name": p.get("name"), "base_url": p.get("base_url"),
                              "enabled": p.get("enabled"), "has_api_key": bool(p.get("api_key"))})
    except Exception as e:
        providers = [{"error": str(e)}]
    cfg = {
        "build": _build_info(),
        "transcriber": _read_json(Path("config/transcriber.json")),
        "cookies_configured": sorted((_read_json(Path("config/downloader.json")) or {}).keys()),
        "env": {k: os.getenv(k) for k in ("TRANSCRIBER_TYPE", "GROQ_TRANSCRIBER_MODEL", "GROQ_TRANSCRIBE_TIMEOUT",
                                          "TASK_MAX_WORKERS", "NOTE_OUTPUT_DIR", "DATABASE_URL", "WHISPER_MODEL_SIZE")},
        "providers": providers,
        "debug_allow_ips": sorted(ALLOW),
    }
    return JSONResponse(json.loads(_redact(json.dumps(cfg, ensure_ascii=False))))
