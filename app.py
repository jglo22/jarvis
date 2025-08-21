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
        heading = data.get("heading", "")
        item = data.get("text", "")

        if not heading or not item:
            return JSONResponse(status_code=400, content={"error": "Missing 'heading' or 'text'"})

        # Load env vars
        token = os.environ.get("GITHUB_TOKEN")
        repo_name = os.environ.get("GITHUB_REPO")
        branch = os.environ.get("GITHUB_BRANCH")
        obsidian_file = os.environ.get("OBSIDIAN_FILE")

        if not all([token, repo_name, branch, obsidian_file]):
            return JSONResponse(status_code=500, content={"error": "Missing required environment variables"})

        # Connect to GitHub
        g = Github(token)
        repo = g.get_repo(repo_name)
        file = repo.get_contents(obsidian_file, ref=branch)
        content = file.decoded_content.decode().splitlines()

        # Insert after the heading
        new_content = []
        inserted = False
        for line in content:
            new_content.append(line)
            if not inserted and line.strip().lower() == f"# {heading.lower()}":
                new_content.append(f"- {item}")
                inserted = True

        if not inserted:
            return JSONResponse(status_code=404, content={"error": f"Heading '{heading}' not found"})

        final = "\n".join(new_content)
        repo.update_file(
            file.path,
            f"Add '{item}' under {heading}",
            final,
            file.sha,
            branch=branch
        )

        return {"ok": True, "added": item, "under": heading}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    
@app.get("/")
def home():
    return {"message": "Jarvis is online."}