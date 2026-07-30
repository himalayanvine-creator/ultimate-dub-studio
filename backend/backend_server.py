import os
import sys
import shutil
import asyncio
import json
import time
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Body
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
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "backend", "scripts")
DB_PATH = os.path.join(WORKSPACE_DIR, "localdub_history.db")

PYTHON_EXE = os.path.join(WORKSPACE_DIR, ".venv", "bin", "python")
if not os.path.exists(PYTHON_EXE):
    PYTHON_EXE = sys.executable

# Track running processes per project_id to support clean cancellation
RUNNING_PROCESSES: dict = {}

# Ensure base directories exist
os.makedirs(PROJECTS_DIR, exist_ok=True)

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                source_file TEXT NOT NULL,
                target_language TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'created',
                project_path TEXT NOT NULL,
                updated_at TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB Init Error] {e}")

init_db()

def get_project_meta(project_id: str) -> dict:
    proj_path = os.path.join(PROJECTS_DIR, project_id)
    meta_path = os.path.join(proj_path, "project_meta.json")
    
    # 1. Check if project_meta.json exists
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"[Meta Read Error] {e}")

    # 2. Check DB
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT project_id, project_name, source_file, target_language, created_at, status, updated_at FROM projects WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            data = {
                "project_id": row[0],
                "project_name": row[1],
                "source_file": row[2],
                "target_language": row[3],
                "created_at": str(row[4]) if row[4] else "Active Session",
                "status": row[5] or "READY",
                "updated_at": str(row[6]) if row[6] else None
            }
            if os.path.exists(proj_path):
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            return data
    except Exception as db_e:
        print(f"[DB Query Error] {db_e}")

    # 3. Fallback: derive from folder name and filesystem
    display_name = project_id.replace("project__", "").replace("_", " ")
    source_file = "input_media.wav"
    if os.path.exists(proj_path):
        files = os.listdir(proj_path)
        media_exts = (".wav", ".mp3", ".m4a", ".mp4", ".mkv", ".mov", ".webm", ".m4v")
        for f in files:
            if f.lower().endswith(media_exts) and not f.startswith("FINAL_DUBBED_") and not f.startswith("EXPORTED_"):
                source_file = f; break

    default_meta = {
        "project_id": project_id,
        "project_name": display_name,
        "source_file": source_file,
        "target_language": "Hindi",
        "created_at": "Active Session",
        "status": "READY",
        "updated_at": None
    }
    if os.path.exists(proj_path):
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(default_meta, f, indent=2)
        except Exception:
            pass
    return default_meta

def save_project_meta(project_id: str, project_name: str = None, target_language: str = None, source_file: str = None, status: str = "READY") -> dict:
    proj_path = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(proj_path, exist_ok=True)
    
    current_meta = get_project_meta(project_id)
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    if project_name:
        current_meta["project_name"] = project_name
    if target_language:
        current_meta["target_language"] = target_language
    if source_file:
        current_meta["source_file"] = source_file
    if status:
        current_meta["status"] = status

    current_meta["updated_at"] = now_str
    if "created_at" not in current_meta or current_meta["created_at"] == "Active Session":
        current_meta["created_at"] = now_str

    meta_path = os.path.join(proj_path, "project_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(current_meta, f, indent=2)

    # Upsert SQLite database
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO projects (project_id, project_name, source_file, target_language, created_at, status, project_path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                project_name = excluded.project_name,
                source_file = excluded.source_file,
                target_language = excluded.target_language,
                status = excluded.status,
                updated_at = excluded.updated_at
        """, (
            project_id,
            current_meta["project_name"],
            current_meta["source_file"],
            current_meta["target_language"],
            current_meta["created_at"],
            current_meta["status"],
            proj_path,
            now_str
        ))
        conn.commit()
        conn.close()
    except Exception as db_e:
        print(f"[DB Upsert Error] {db_e}")

    return current_meta

# Mount static media and frontend web studio files
app.mount("/media", StaticFiles(directory=PROJECTS_DIR), name="media")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")


async def run_script_generator(script_name: str, project_dir: str, project_id: str):
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        yield f"data: [!] ERROR: Script '{script_name}' not found at {script_path}\n\n"
        return

    yield f"data: [EXECUTOR] Launching '{script_name}'...\n\n"
    
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    process = await asyncio.create_subprocess_exec(
        PYTHON_EXE, script_path,
        cwd=project_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
        limit=1024 * 1024 * 10  # 10MB buffer limit for long stdout lines
    )

    RUNNING_PROCESSES[project_id] = process

    return_code = -1
    try:
        while True:
            try:
                line = await process.stdout.readline()
            except asyncio.LimitOverrunError as overrun_err:
                chunk = await process.stdout.read(overrun_err.consumed or 65536)
                text = chunk.decode("utf-8", errors="replace").rstrip()
                if text:
                    yield f"data: {text}\n\n"
                continue

            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                yield f"data: {text}\n\n"

        await process.wait()
        return_code = process.returncode
    except Exception as e:
        yield f"data: [!] EXECUTOR EXCEPTION in {script_name}: {str(e)}\n\n"
    finally:
        RUNNING_PROCESSES.pop(project_id, None)

    if return_code == 0:
        yield f"data: [✓ EXECUTOR] SUCCESS: '{script_name}' completed!\n\n"
    else:
        yield f"data: [!] EXECUTOR ERROR: '{script_name}' exited with code {return_code}\n\n"


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

    # Save project metadata
    meta = save_project_meta(
        project_id=project_id,
        project_name=project_name,
        target_language=target_language,
        source_file=saved_file_name,
        status="created"
    )

    return {
        "status": "success",
        "project_id": project_id,
        "project_name": meta["project_name"],
        "target_language": meta["target_language"],
        "source_file": meta["source_file"]
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
        entries = sorted(os.listdir(PROJECTS_DIR), reverse=True)
        for entry in entries:
            proj_path = os.path.join(PROJECTS_DIR, entry)
            if os.path.isdir(proj_path) and entry.startswith("project__"):
                meta = get_project_meta(entry)
                projects.append(meta)

    return {"projects": projects}


@app.get("/api/projects/{project_id}/meta")
async def get_project_metadata(project_id: str):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Project not found")
    return get_project_meta(project_id)


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
async def save_project_state(project_id: str, data: Optional[dict] = Body(None)):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Project not found")

    p_name = data.get("project_name") if data else None
    t_lang = data.get("target_language") if data else None
    s_file = data.get("source_file") if data else None

    meta = save_project_meta(
        project_id=project_id,
        project_name=p_name,
        target_language=t_lang,
        source_file=s_file,
        status="READY"
    )

    return {
        "status": "success",
        "message": f"Project '{meta['project_name']}' state saved successfully.",
        "project": meta
    }


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    print(f"[Wipe Off] Attempting to delete project folder: {project_path}")
    
    if os.path.exists(project_path):
        try:
            shutil.rmtree(project_path)
            print(f"[Wipe Off] Successfully deleted project folder: {project_path}")
        except Exception as e:
            print(f"[Wipe Off] Non-fatal error deleting folder: {e}")
            shutil.rmtree(project_path, ignore_errors=True)
            
    try:
        db_path = os.path.join(WORKSPACE_DIR, "localdub_history.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            conn.commit()
            conn.close()
    except Exception as db_e:
        print(f"[Wipe Off] DB deletion note: {db_e}")

    return {"status": "success", "message": f"Project '{project_id}' deleted completely."}


@app.get("/api/projects/{project_id}/run-pipeline-stream")
async def run_pipeline_stream(project_id: str):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Project directory not found")

    async def event_generator():
        yield f"data: [START] Initializing Execution Engine for '{project_id}'...\n\n"
        
        pipeline_scripts = [
            "slice.py",
            "text_grabber.py",
            "translator.py"
        ]

        for step_idx, script in enumerate(pipeline_scripts, 1):
            yield f"data: --- Stage [{step_idx}/{len(pipeline_scripts)}]: {script} ---\n\n"
            step_failed = False
            async for log_event in run_script_generator(script, project_path, project_id):
                yield log_event
                if "[!] EXECUTOR ERROR:" in log_event or "[!] ERROR:" in log_event:
                    step_failed = True
            if step_failed:
                yield f"data: [!] PIPELINE HALTED: Failed at stage '{script}'.\n\n"
                return

        yield "data: [COMPLETE] Pipeline execution finished successfully!\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/run-dubbing-pipeline")
async def run_dubbing_pipeline_stream(project_id: str):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Project directory not found")

    async def event_generator():
        yield f"data: [START] Launching Dubbing & Quality Audit Pipeline (dubber.py ➔ auditor.py) for '{project_id}'...\n\n"
        pipeline_scripts = ["dubber.py", "auditor.py"]

        for step_idx, script in enumerate(pipeline_scripts, 1):
            yield f"data: --- Stage [{step_idx}/{len(pipeline_scripts)}]: {script} ---\n\n"
            step_failed = False
            async for log_event in run_script_generator(script, project_path, project_id):
                yield log_event
                if "[!] EXECUTOR ERROR:" in log_event or "[!] ERROR:" in log_event:
                    step_failed = True
            if step_failed:
                yield f"data: [!] PIPELINE HALTED: Failed at stage '{script}'.\n\n"
                return

        yield "data: [COMPLETE] Dubbing & Quality Audit Pipeline finished successfully!\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/stitch")
async def run_stitch_stream(project_id: str):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Project directory not found")

    async def event_generator():
        yield f"data: Assembling audio tracks for '{project_id}'...\n\n"
        for script in ["stitcher.py", "auditor.py"]:
            async for log_event in run_script_generator(script, project_path, project_id):
                yield log_event

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/run-step")
async def run_single_step(project_id: str, script_name: str = Query(...)):
    project_path = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Project directory not found")

    async def event_generator():
        async for log_event in run_script_generator(script_name, project_path, project_id):
            yield log_event

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/projects/{project_id}/stop")
async def stop_project_execution(project_id: str):
    process = RUNNING_PROCESSES.get(project_id)
    if process:
        try:
            process.terminate()
            await asyncio.sleep(0.2)
            if process.returncode is None:
                process.kill()
        except Exception:
            pass
        RUNNING_PROCESSES.pop(project_id, None)
        return {"status": "success", "message": f"Execution for '{project_id}' terminated."}
    return {"status": "success", "message": "No active process was running."}