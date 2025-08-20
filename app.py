from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
from github import Github

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/alert")
async def alert(request: Request):
    if request.headers.get("Content-Type") != "application/json":
        return JSONResponse(status_code=400, content={"error": "Invalid content type"})

    try:
        data = await request.json()
        return {"ok": True, "received": data["message"]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/obsidian")
async def obsidian(request: Request):
    if request.headers.get("Content-Type") != "application/json":
        return JSONResponse(status_code=400, content={"error": "Invalid content type"})

    try:
        data = await request.json()
        text = data.get("text", "")
        if not text:
            return JSONResponse(status_code=400, content={"error": "Missing 'text' in request"})

        # Load env vars safely
        token = os.environ.get("GITHUB_TOKEN")
        repo_name = os.environ.get("GITHUB_REPO")
        branch = os.environ.get("GITHUB_BRANCH")
        obsidian_file = os.environ.get("OBSIDIAN_FILE")

        # Ensure all required env vars are present
        if not all([token, repo_name, branch, obsidian_file]):
            return JSONResponse(status_code=500, content={"error": "Missing required environment variables"})

        # Connect to GitHub
        g = Github(token)
        repo = g.get_repo(repo_name)

        # Get the file contents
        file = repo.get_contents(obsidian_file, ref=branch)
        current_content = file.decoded_content.decode()

        # Append the text
        new_content = current_content + "\n" + text

        # Commit back
        repo.update_file(
            file.path,
            f"Append via Jarvis: {text}",
            new_content,
            file.sha,
            branch=branch
        )

        return {"ok": True, "appended": text}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/")
def home():
    return {"message": "Jarvis is online."}