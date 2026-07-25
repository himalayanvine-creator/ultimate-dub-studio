# DAW Slice Editor — feature/daw-slice-editor Branch

This document describes the technology, architecture, and components specific to the feature/daw-slice-editor branch of the Ultimate Dub Studio repository.

Overview
--------
The feature/daw-slice-editor branch adds a DAW-style slice editor to the frontend, enabling manual editing of VAD-derived audio slices (chunks). The slice editor is a single-page HTML UI (slice-editor.html) backed by JavaScript (slice-editor.js) which integrates WaveSurfer.js for waveform rendering and playback.

Files added/changed on this branch
---------------------------------
- frontend/slice-editor.html — DAW Slice Editor UI (new)
- frontend/slice-editor.js — Slice editor client logic (new)
- frontend/index.html, app.js, studio.html, studio.js, styles.css — existing UI files present; slice-editor integrates with backend via existing API.

Tech stack
----------
- Frontend:
  - HTML5, CSS3
  - Vanilla JavaScript (ES6)
  - WaveSurfer.js v7 for waveform rendering, zooming, playback, and interaction
- Backend (unchanged):
  - FastAPI (Python) provides REST endpoints and static file serving
  - Filesystem-based project storage under WORKSPACE_DIR (/Volumes/new/LocalDubWorkspace by default)
- External tools:
  - FFmpeg for audio/video processing (backend scripts)
  - Vertex AI (google-genai) used by backend scripts for transcription/translation/TTS

Architecture & Data Flow
------------------------
1. Initialization
   - The slice editor SPA is loaded via /static/slice-editor.html served by FastAPI.
   - On load, slice-editor.js reads project_id from the query string and requests project history from /api/projects/history/list to discover the target project.

2. Audio and metadata loading
   - The app retrieves the source audio file URL from the project entry and loads it into WaveSurfer from /media/{project_id}/{source_file}.
   - It requests chunk metadata from /api/projects/{project_id}/chunks, which returns the chunks folder name and list of chunk files.
   - The editor then fetches timeline.json from the chunks folder (served via /media) to populate original slice timestamps.

3. Editing workflow
   - The UI supports manual slice mode (toggle), where clicking the waveform adds a slice point inside an existing chunk.
   - Users can split chunks at the cursor, merge adjacent chunks, undo/redo edits, and reset to auto slices.
   - Edits are tracked in an undo/redo stack and flagged as dirty until saved.

4. Saving changes
   - When the user saves, the client POSTs a JSON payload to /api/projects/{project_id}/save-slices containing an array of {start_sec, end_sec, duration_sec} entries.
   - The backend is expected to re-export or rename chunk WAV files per the new timeline and update the chunks folder and timeline.json.

Client-side capabilities
------------------------
- Waveform visualization (playback, seeking, zoom, volume, playback rate)
- Interactive slice markers with drag support scaffolding
- Undo/redo history and visual edit history list
- Chunk list with chunk selection and navigation
- Basic modal confirmation dialogs

Backend contract (endpoints used)
---------------------------------
The slice editor relies on the backend API (backend_server.py) with these endpoints:
- GET /api/projects/history/list — discover projects and source file names
- GET /media/{project_id}/{chunks_folder}/timeline.json — retrieve auto-generated timeline mapping
- GET /api/projects/{project_id}/chunks — get chunks folder and chunk list
- POST /api/projects/{project_id}/save-slices — (expected) to accept updated slice list and apply edits
  - Note: In the main branch backend_server.py does not currently implement /save-slices; this branch assumes the endpoint exists or the backend will be extended.

Important implementation notes / gaps
-----------------------------------
- The UI POSTs to /api/projects/{project_id}/save-slices, but backend/backend_server.py in main does not implement this endpoint. Ensure the backend exposes this route or provide a patch to handle it.
- The frontend uses a hardcoded API_BASE = "http://127.0.0.1:8000"; consider making this relative or configurable to support different deployments.
- Timeline parsing in slice-editor.js expects timeline.json to be an object mapping chunk IDs to objects with start_sec and end_sec. Confirm the timeline.json schema produced by slice.py matches this structure.
- WaveSurfer zoom uses waveSurfer.zoom(zoomLevel * 50) — large zoom multipliers may be platform-dependent.
- Drag-and-drop marker reposition logic is scaffolded but not fully implemented (drop handler reads dataTransfer but does not update the timeline). Additional event handling is required to support marker drag-resize behavior.

Security & operational notes
---------------------------
- The same repository-level concerns apply: wide-open CORS, hardcoded workspace path, lack of authentication — these are relevant if the slice editor is exposed in production.
- The slice editor loads timeline.json and WAV files directly from the /media static mount; ensure proper access checks if sensitive files exist.

Recommendations for branch completion
-------------------------------------
1. Implement backend endpoint POST /api/projects/{project_id}/save-slices to:
   - Validate incoming slice array, ensure non-overlapping and within audio duration
   - Create a new chunks folder or update existing chunk WAV filenames safely
   - Regenerate timeline.json and update chunk metadata
   - Provide atomicity (e.g., write new folder then swap) and lock per project to prevent concurrent edits

2. Complete drag-to-resize marker support in slice-editor.js (compute new time from drop position and update chunk start/end).

3. Make API_BASE configurable and avoid hardcoded host/port in frontend.

4. Add visual confirmation for destructive actions and better error handling for network failures.

5. Add unit/integration tests for save-slices backend logic and an end-to-end test covering the editor save flow.

6. Add rate-limiting / auth for sensitive operations if this runs on a publicly-accessible server.

Summary
-------
The feature/daw-slice-editor branch introduces a rich, client-side DAW slice editor integrated with the existing filesystem-driven pipeline. The branch's focus is primarily frontend capabilities (waveform visualization, manual slicing, undo/redo). To fully enable the feature, the backend must implement an endpoint to accept and persist slice edits and ensure safe, atomic updates to project chunk data.

