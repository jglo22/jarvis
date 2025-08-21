from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from core.types import ObsidianCommand

APP_VERSION = "0.1.0"

app = FastAPI(title="Jarvis API", version=APP_VERSION)

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

# NEW unified endpoint: accepts the obsidian.command envelope and only validates for now.
# The actual filesystem/GitHub/URI adapter will be wired in next steps.
@app.post("/obsidian/command")
async def obsidian_command(cmd: ObsidianCommand, request: Request):
    try:
        # If we reached here, FastAPI + Pydantic already validated the payload shape.
        # We stub the action handler for now and simply echo back the essentials.
        return {
            "status": "ok",
            "action": cmd.action,
            "path": cmd.payload.path,
            "trace_id": (cmd.payload.meta.trace_id if cmd.payload.meta else None),
        }
    except ValidationError as ve:
        # This block is mostly defensive; FastAPI would convert Pydantic errors to 422 by default.
        return JSONResponse(status_code=400, content={"error": "validation_error", "details": ve.errors()})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/")
def home():
    return {"message": "Jarvis is online."}