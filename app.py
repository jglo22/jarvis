from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Alert(BaseModel):
    message: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/alert")
def alert(payload: Alert):
    return {"ok": True, "received": payload.message}
