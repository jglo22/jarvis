import os
from fastapi import Header, HTTPException
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from core.types import ObsidianCommand

# Robust import that works both locally and on Render
try:
    from adapters.obsidian_fs import ObsidianFSAdapter
except ModuleNotFoundError:
    # Fallback: ensure project root is on sys.path, then retry
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from adapters.obsidian_fs import ObsidianFSAdapter  # retry
    except ModuleNotFoundError:
        # Final fallback: lightweight inline filesystem adapter so deployment still works
        from pathlib import Path
        from datetime import datetime
        from typing import Optional, List

        class ObsidianFSAdapter:
            def __init__(self):
                base = os.getenv("OBSIDIAN_VAULT_PATH") or str((Path.cwd() / "_vault").resolve())
                self.base = Path(base)
                self.base.mkdir(parents=True, exist_ok=True)

            def _note_path(self, path: str) -> Path:
                # Normalize and ensure directories exist
                p = (self.base / path).resolve()
                p.parent.mkdir(parents=True, exist_ok=True)
                return p

            def note_create(self, path: str, title: str, body_md: str, vault: Optional[str] = None) -> str:
                p = self._note_path(path)
                content = ""
                if title and not body_md.lstrip().startswith("#"):
                    content += f"# {title}\n\n"
                content += body_md or ""
                p.write_text(content, encoding="utf-8")
                return path

            def note_update(self, path: str, body_md: str, vault: Optional[str] = None) -> str:
                p = self._note_path(path)
                p.write_text(body_md or "", encoding="utf-8")
                return path

            def note_append(self, path: str, body_md: str, position: str = "bottom", heading: Optional[str] = None, vault: Optional[str] = None) -> str:
                p = self._note_path(path)
                if not p.exists():
                    p.write_text("", encoding="utf-8")
                lines = p.read_text(encoding="utf-8").splitlines()
                insert_block = (body_md or "")
                if position == "after_heading" and heading:
                    # Find heading line that matches exactly (ignoring leading # and spaces)
                    target_idx = None
                    target_key = heading.strip().lower()
                    for i, line in enumerate(lines):
                        stripped = line.lstrip("#").strip().lower()
                        if stripped == target_key:
                            target_idx = i
                            break
                    if target_idx is not None:
                        # Insert after the heading and any immediate blank line
                        insert_at = target_idx + 1
                        if insert_at < len(lines) and lines[insert_at].strip() == "":
                            insert_at += 1
                        new_lines = lines[:insert_at] + [insert_block] + lines[insert_at:]
                        p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                        return path
                # Default: append to bottom with a separating blank line
                if lines and lines[-1].strip() != "":
                    lines.append("")
                lines.append(insert_block)
                p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return path

            def task_create(self, path: str, task_text: str, due: Optional[str] = None, tags: Optional[List[str]] = None, vault: Optional[str] = None) -> str:
                p = self._note_path(path)
                if not p.exists():
                    p.write_text("", encoding="utf-8")
                line = f"- [ ] {task_text}"
                meta_bits = []
                if due:
                    meta_bits.append(f"🗓 {due}")
                if tags:
                    meta_bits.append(" ".join(f"#{t}" for t in tags if t))
                if meta_bits:
                    line += "  " + " ".join(meta_bits)
                content = p.read_text(encoding="utf-8")
                if content and not content.endswith("\n"):
                    content += "\n"
                content += line + "\n"
                p.write_text(content, encoding="utf-8")
                return path

            def task_toggle(self, path: str, task_state: str = "done", task_text: Optional[str] = None, vault: Optional[str] = None) -> str:
                p = self._note_path(path)
                if not p.exists():
                    raise FileNotFoundError(f"note not found: {path}")
                lines = p.read_text(encoding="utf-8").splitlines()
                want = "x" if task_state == "done" else " "
                changed = False
                for i, line in enumerate(lines):
                    if not line.strip().startswith("- ["):
                        continue
                    if task_text and task_text not in line:
                        continue
                    # Replace the checkbox marker
                    lines[i] = "- [" + want + "]" + line[line.find("]") + 1 :]
                    changed = True
                    if task_text:
                        break
                if not changed:
                    raise ValueError("matching task not found to toggle")
                p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return path

APP_VERSION = "0.1.0"

app = FastAPI(title="Jarvis API", version=APP_VERSION)

adapter = ObsidianFSAdapter()

AUTH_TOKEN = os.getenv("AUTH_TOKEN")

def check_auth(authorization: str | None):
    if not AUTH_TOKEN:
        return  # auth disabled if no token set
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/version")
def version():
    return {"version": APP_VERSION}

@app.post("/alert")
async def alert(request: Request):
    if request.headers.get("Content-Type") != "application/json":
        return JSONResponse(status_code=400, content={"error": "Invalid content type"})

    try:
        data = await request.json()
        return {"ok": True, "received": data.get("message")}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/obsidian/command")
async def obsidian_command(cmd: ObsidianCommand, request: Request, authorization: str | None = Header(default=None)):
    check_auth(authorization)
    try:
        # Route to adapter based on action
        if cmd.action == "note.create":
            record_id = adapter.note_create(
                path=cmd.payload.path,
                title=cmd.payload.title or "",
                body_md=cmd.payload.body_md or "",
                vault=cmd.payload.vault,
            )
        elif cmd.action == "note.append":
            record_id = adapter.note_append(
                path=cmd.payload.path,
                body_md=cmd.payload.body_md or "",
                position=(cmd.payload.position or "bottom"),
                heading=cmd.payload.heading,
                vault=cmd.payload.vault,
            )
        elif cmd.action == "note.update":
            record_id = adapter.note_update(
                path=cmd.payload.path,
                body_md=cmd.payload.body_md or "",
                vault=cmd.payload.vault,
            )
        elif cmd.action == "task.create":
            record_id = adapter.task_create(
                path=cmd.payload.path,
                task_text=cmd.payload.task_text or "",
                due=cmd.payload.due,
                tags=cmd.payload.tags,
                vault=cmd.payload.vault,
            )
        elif cmd.action == "task.toggle":
            record_id = adapter.task_toggle(
                path=cmd.payload.path,
                task_state=(cmd.payload.task_state or "done"),
                task_text=cmd.payload.task_text,
                vault=cmd.payload.vault,
            )
        else:
            return JSONResponse(status_code=400, content={"error": f"unsupported action {cmd.action}"})

        return {
            "status": "ok",
            "action": cmd.action,
            "record_id": record_id,
            "trace_id": (cmd.payload.meta.trace_id if cmd.payload.meta else None),
        }
    except ValidationError as ve:
        return JSONResponse(status_code=400, content={"error": "validation_error", "details": ve.errors()})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.get("/")
def home():
    return {"message": "Jarvis is online."}