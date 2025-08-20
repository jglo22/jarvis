from fastapi import FastAPI, Request
import os
from github import Github

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/alert")
async def alert(request: Request):
    data = await request.json()
    return {"ok": True, "received": data["message"]}

@app.post("/obsidian")
async def obsidian(request: Request):
    data = await request.json()
    text = data.get("text", "")

    # Load env vars
    token = os.environ["GITHUB_TOKEN"]
    repo_name = os.environ["GITHUB_REPO"]
    branch = os.environ["GITHUB_BRANCH"]
    obsidian_file = os.environ["OBSIDIAN_FILE"]

    # Connect to GitHub
    g = Github(token)
    repo = g.get_repo(repo_name)

    # Get the file
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

@app.route('/')
def home():
    return "Jarvis is online."