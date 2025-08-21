import os
from fastapi import Header, HTTPException
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from core.types import ObsidianCommand
from adapters.obsidian_fs import ObsidianFSAdapter

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