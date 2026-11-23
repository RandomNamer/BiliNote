"""Token-protected, read-only access to any file in the container, over HTTP.

Why: diagnosing a deployment otherwise needs a shell on the Docker host for every question
("why did this note fail?", "what's in the DB?"). This serves logs, task files, the SQLite
database, config and anything mounted, read-only, without having to change the code each time
something new needs looking at.

Enabled only when DEBUG_TOKEN is set (otherwise every route here is 404). Every request must send
`Authorization: Bearer <DEBUG_TOKEN>` (or `X-Debug-Token: <DEBUG_TOKEN>`). Set the token at deploy
time (compose `.env`), never in code or git.

  GET /api/debug/ls?path=/app/backend/data                 directory listing (JSON)
  GET /api/debug/file?path=…&tail=200&grep=REGEX&redact=1   text view (tail/grep/offset+limit)
  GET /api/debug/file?path=…&raw=1                          the file as-is (binary, e.g. the DB)

Relative paths resolve against the backend's working directory (/app/backend). Text views mask
API keys, cookies and bearer tokens by default (`redact=0` turns it off) so secrets don't end up
in transcripts or terminals; raw downloads are never altered.
"""
import hmac
import os
import re
import stat
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

router = APIRouter()

MAX_TEXT_BYTES = 16 * 1024 * 1024

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


def _authorize(request: Request) -> None:
    token = os.getenv("DEBUG_TOKEN", "")
    if not token:
        raise HTTPException(status_code=404, detail="Not Found")
    auth = request.headers.get("authorization", "")
    given = auth[7:] if auth.lower().startswith("bearer ") else request.headers.get("x-debug-token", "")
    if not given or not hmac.compare_digest(given.encode(), token.encode()):
        raise HTTPException(status_code=401, detail="missing or wrong debug token")


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else Path.cwd() / p


@router.get("/debug/ls")
def debug_ls(request: Request, path: str = Query(".")):
    _authorize(request)
    d = _resolve(path)
    if not d.exists():
        raise HTTPException(status_code=404, detail=f"{d} does not exist")
    if not d.is_dir():
        raise HTTPException(status_code=400, detail=f"{d} is not a directory")
    entries = []
    for e in sorted(d.iterdir(), key=lambda x: x.name):
        try:
            st = e.lstat()
            kind = "dir" if stat.S_ISDIR(st.st_mode) else "link" if stat.S_ISLNK(st.st_mode) else "file"
            entries.append({"name": e.name, "type": kind, "bytes": st.st_size, "mtime": st.st_mtime})
        except OSError as err:
            entries.append({"name": e.name, "error": str(err)})
    return JSONResponse({"path": str(d), "entries": entries})


@router.get("/debug/file")
def debug_file(request: Request, path: str = Query(...), raw: bool = Query(False),
               tail: int | None = Query(None, ge=1), grep: str | None = Query(None),
               offset: int = Query(0, ge=0), limit: int = Query(1_000_000, ge=1),
               redact: bool = Query(True)):
    _authorize(request)
    f = _resolve(path)
    if not f.is_file():
        raise HTTPException(status_code=404, detail=f"{f} is not a file")
    if raw:
        return FileResponse(f, filename=f.name)

    size = f.stat().st_size
    with f.open("rb") as fh:
        if tail is not None or grep:
            fh.seek(max(0, size - MAX_TEXT_BYTES))  # tail/grep look at the last 16 MB
        else:
            fh.seek(offset)
        data = fh.read(MAX_TEXT_BYTES if (tail is not None or grep) else min(limit, MAX_TEXT_BYTES))
    text = data.decode("utf-8", errors="replace")
    if tail is not None or grep:
        rows = text.replace("\r", "\n").splitlines()  # yt-dlp progress uses \r
        if grep:
            try:
                rx = re.compile(grep)
            except re.error as e:
                raise HTTPException(status_code=400, detail=f"bad regex: {e}")
            rows = [r for r in rows if rx.search(r)]
        if tail is not None:
            rows = rows[-tail:]
        text = "\n".join(rows) + "\n"
    headers = {"X-File-Size": str(size)}
    return PlainTextResponse(_redact(text) if redact else text, headers=headers)
