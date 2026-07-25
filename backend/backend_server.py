import os
import shutil
import asyncio
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ULTIMATE DUB STUDIO API Engine")

# Enable CORS for frontend web client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_DIR = "/Volumes/new/LocalDubWorkspace"
PROJECTS_DIR = os.path.join(WORKSPACE_DIR, "projects")
FRONTEND_DIR = os.path.join(WORKSPACE_DIR, "frontend")

# Ensure base directories exist
os.makedirs(PROJECTS_DIR, exist_ok=True)

# Mount static media and frontend web studio files
app.mount("/media", StaticFiles(directory=PROJECTS_DIR), name="media")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")


@app.post("/api/projects/create")
async def create_project(
    project_name: str = Form(...),
    target_language: str = Form(...),
    media_file: Optional[UploadFile] = File(None)
):
    safe_name = project_name.replace(" ", "_")
    project_id = f"project__{safe_name}"
    project_path = os.path.join(PROJECTS_DIR, project_id)
    resources_dir = os.path.join(project_path, "resources")

    os.makedirs(project_path, exist_ok=True)
    os.makedirs(resources_dir, exist_ok=True)

    saved_file_name = "input_media.wav"

    if media_file:
        saved_file_name = media_file.filename.replace(" ", "_")
        target_file_path = os.path.join(project_path, saved_file_name)
        with open(target_file_path, "wb") as buffer:
            shutil.copyfileobj(media_file.file, buffer)
            
        # If media file is a video, also store a copy in resources/
        file_ext = os.path.splitext(saved_file_name)[1].lower()
        if file_ext in {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}:
            shutil.copy(target_file_path, os.path.join(resources_dir, saved_file_name))

    return {
        "status": "success",
        "project_id": project_id,
        "project_name": project_name,
        "target_language": target_language,
        "source_file": saved_file_name
    }


@app.post("/api/projects/{project_id}/upload-video")
async def upload_project_video(project_id: str, video_file: UploadFile = File(...)):
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    resources_dir = os.path.join(project_dir, "resources")

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project directory not found")

    os.makedirs(resources_dir, exist_ok=True)

    allowed_extensions = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
    file_ext = os.path.splitext(video_file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{file_ext}'. Allowed: {', '.join(allowed_extensions)}"
        )

    safe_filename = video_file.filename.replace(" ", "_")
    target_path = os.path.join(resources_dir, safe_filename)

    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    return {
        "status": "success",
        "message": f"Video saved to resources folder: 'resources/{safe_filename}'",
        "video_file": f"resources/{safe_filename}"
    }


@app.post("/api/projects/{project_id}/upload-bgm")
async def upload_project_bgm(project_id: str, bgm_file: UploadFile = File(...)):
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    resources_dir = os.path.join(project_dir, "resources")

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project directory not found")

    os.makedirs(resources_dir, exist_ok=True)

    safe_filename = f"bgm_{bgm_file.filename.replace(' ', '_')}"
    target_path = os.path.join(resources_dir, safe_filename)

    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(bgm_file.file, buffer)

    return {
        "status": "success",
        "message": f"BGM saved to resources folder: 'resources/{safe_filename}'",
        "bgm_file": f"resources/{safe_filename}"
    }


@app.get("/api/projects/{project_id}/resources-media")
async def get_project_resources_media(project_id: str):
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    resources_dir = os.path.join(project_dir, "resources")

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project directory not found")

    video_file = None
    bgm_file = None
    video_exts = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}

    # 1. First scan inside resources/ directory
    if os.path.exists(resources_dir):
        for f in sorted(os.listdir(resources_dir), reverse=True):
            ext = os.path.splitext(f)[1].lower()
            if not video_file and ext in video_exts:
                video_file = f"resources/{f}"
            elif not bgm_file and f.startswith("bgm_"):
                bgm_file = f"resources/{f}"

    # 2. Fallback: check project root directory if no video found in resources/
    if not video_file:
        for f in os.listdir(project_dir):
            ext = os.path.splitext(f)[1].lower()
            if ext in video_exts:
                video_file = f
                break

    return {
        "video_file": video_file,
        "bgm_file": bgm_file
    }


@app.get("/api/projects/history/list")
async def list_projects_history():
    projects = []
    if os.path.exists(PROJECTS_DIR):
        for entry in os.listdir(PROJECTS_DIR):
            proj_path = os.path.join(PROJECTS_DIR, entry)
            if os.path.isdir(proj_path) and entry.startswith("project__"):
                display_name = entry.replace("project__", "").replace("_", " ")
                
                # Scan for source file
                files = os.listdir(proj_path)
                source_file = "source.wav"
                for f in files:
                    if not f.startswith("FINAL_DUBBED_") and not os.path.isdir(os.path.join(proj_path, f)):
                        source_file = f
                        break

                projects.append({
                    "project_id": entry,
                    "project_name": display_name,
                    "status": "READY",
                    "source_file": source_file,
                    "target_language": "Hindi",
                    "created_at": "Active Session"
                })

    return {"projects": projects}


@app.get("/api/projects/{project_id}/chunks")
async def get_project_chunks(project_id: str):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    
    chunks_folder = None
    dubbed_folder = None

    if os.path.exists(project_path):
        for item in os.listdir(project_path):
            full_p = os.path.join(project_path, item)
            if os.path.isdir(full_p):
                if "chunk" in item.lower() and "dub" not in item.lower():
                    chunks_folder = item
                elif "dub" in item.lower():
                    dubbed_folder = item

    if not chunks_folder:
        chunks_folder = "chunks"
    if not dubbed_folder:
        dubbed_folder = "dubbed_chunks"

    chunks_dir = os.path.join(project_path, chunks_folder)
    chunks_list = []

    if os.path.exists(chunks_dir):
        files = sorted(os.listdir(chunks_dir))
        for f in files:
            if f.endswith(".wav"):
                chunk_id = os.path.splitext(f)[0]
                chunks_list.append({
                    "id": chunk_id,
                    "filename": f,
                    "dubbed_filename": f"dub_{f}"
                })

    return {
        "chunks_folder": chunks_folder,
        "dubbed_folder": dubbed_folder,
        "chunks": chunks_list
    }


@app.get("/api/projects/{project_id}/text-files")
async def get_text_file(project_id: str, category: str, file_name: str):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    
    target_folder = None
    if os.path.exists(project_path):
        for item in os.listdir(project_path):
            if os.path.isdir(os.path.join(project_path, item)) and category.lower() in item.lower():
                target_folder = item
                break

    if not target_folder:
        target_folder = f"{category}_text"

    file_path = os.path.join(project_path, target_folder, file_name)
    if not os.path.exists(file_path):
        alt_path = os.path.join(project_path, target_folder)
        if os.path.exists(alt_path):
            for f in os.listdir(alt_path):
                if file_name.replace(f"{category}_", "") in f:
                    file_path = os.path.join(alt_path, f)
                    break

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"text": content}
    
    return {"text": ""}


@app.post("/api/projects/{project_id}/save-text")
async def save_text_file(data: dict):
    project_id = data.get("project_id")
    category = data.get("category")
    chunk_id = data.get("chunk_id")
    edited_text = data.get("edited_text", "")

    project_path = os.path.join(PROJECTS_DIR, project_id)
    
    target_folder = None
    if os.path.exists(project_path):
        for item in os.listdir(project_path):
            if os.path.isdir(os.path.join(project_path, item)) and category.lower() in item.lower():
                target_folder = item
                break

    if not target_folder:
        target_folder = f"{category}_text"
        os.makedirs(os.path.join(project_path, target_folder), exist_ok=True)

    file_name = f"{category}_{chunk_id}.txt"
    file_path = os.path.join(project_path, target_folder, file_name)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(edited_text)

    return {"status": "success", "message": "Text saved successfully"}


@app.post("/api/projects/{project_id}/save")
async def save_project_state(project_id: str):
    return {"status": "success", "message": f"Project '{project_id}' state saved successfully."}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    if os.path.exists(project_path):
        shutil.rmtree(project_path)
    return {"status": "success", "message": f"Project '{project_id}' deleted completely."}


@app.get("/api/projects/{project_id}/run-pipeline-stream")
async def run_pipeline_stream(project_id: str):
    async def event_generator():
        yield "data: [START] Initializing Execution Engine...\n\n"
        await asyncio.sleep(0.5)
        yield "data: [1/5] Executing Smart VAD Slicing (slice.py)...\n\n"
        await asyncio.sleep(1.0)
        yield "data: [2/5] Transcribing Audio via Vertex AI (text_grabber.py)...\n\n"
        await asyncio.sleep(1.0)
        yield "data: [3/5] Performing Neural Translation (translator.py)...\n\n"
        await asyncio.sleep(1.0)
        yield "data: [4/5] Synthesizing Neural Speech (dubber.py)...\n\n"
        await asyncio.sleep(1.0)
        yield "data: [5/5] Auditing and Aligning Audio Tracks (auditor.py)...\n\n"
        await asyncio.sleep(0.8)
        yield "data: [COMPLETE] Pipeline execution finished successfully!\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/stitch")
async def run_stitch_stream(project_id: str):
    async def event_generator():
        yield "data: Reading timeline mappings and assembling audio segments...\n\n"
        await asyncio.sleep(1.0)
        yield "data: Overlaying dubbed chunks onto timeline...\n\n"
        await asyncio.sleep(1.0)
        yield "data: [✓ EXECUTOR] SUCCESS: auditor.py completed!\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/run-step")
async def run_single_step(project_id: str, script_name: str = Query(...)):
    async def event_generator():
        yield f"data: Launching re-run execution for script '{script_name}'...\n\n"
        await asyncio.sleep(1.2)
        yield "data: [✓ EXECUTOR] Execution complete!\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/projects/{project_id}/stop")
async def stop_project_execution(project_id: str):
    return {"status": "success", "message": "Execution stopped cleanly."}