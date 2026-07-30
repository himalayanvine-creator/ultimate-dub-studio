# 🎙️ ULTIMATE DUB STUDIO — Local AI Video & Audio Dubbing Engine

> **A high-performance, privacy-focused, local-first video and audio dubbing studio built for macOS.** Featuring intelligent Voice Activity Detection (VAD) slicing with 120ms gap splitting and 5.0s max chunk limits, AI-powered speech-to-text and duration-aware neural translation via Vertex AI, Enceladus TTS synthesis, anti-bleed waveform stitching, and a real-time multi-track video sync studio with lossless export.

---

## 🎯 Project Objective

The core objective of **ULTIMATE DUB STUDIO** is to provide an end-to-end, automated localized dubbing platform that:
1. **Preserves Original Timeline Integrity**: Ensures dubbed speech matches the exact timing, pauses, and cadence of the source audio through timestamp-mapped segment reconstruction rather than simple audio concatenation.
2. **Eliminates Mute Gaps Inside Speech Chunks**: Uses fine-grained Silero VAD to split audio on any silence gap $\ge 120\text{ms}$, ensuring each chunk contains tight, continuous speech bounded to a maximum duration of **5.0 seconds**.
3. **Enforces Duration-Aware Translation**: Instructs Gemini neural translation models to produce concise, rhythmic target text strictly matching original physical speech durations to prevent speech over-expansion.
4. **Prevents Audio Bleeding (`stitcher.py`)**: Analyzes available timeline windows between speech segments and auto-fits/compresses dubbed TTS chunks to keep non-speech intervals (mute gaps) pristine and untouched.
5. **Eliminates Video Quality Loss**: Renders multi-track dubbed video projects without video re-encoding (`-c:v copy`), retaining 100% of original visual fidelity and resolution.
6. **Offers Human-in-the-Loop Control & On-Demand Audit**: Provides non-destructive text editing at the chunk level and a dedicated **Quality Audit Check** button to run automated chipmunk & RMS energy verification on demand.
7. **Proportional Waveform Representation**: Displays waveforms in Step 4 scaled to their actual physical duration relative to the 5.0s window, preventing short clips from appearing artificially stretched.

---

## 🏗️ System Architecture

```text
       ┌──────────────────────────────────────────────────────────────┐
       │                WEB DASHBOARD / STUDIO UI                     │
       │            (HTML5, CSS3, JavaScript, WaveSurfer.js)          │
       └──────────────────────────────┬───────────────────────────────┘
                                      │ HTTP / Server-Sent Events (SSE)
                                      ▼
       ┌──────────────────────────────────────────────────────────────┐
       │                    FASTAPI BACKEND SERVER                    │
       │                   (Python 3.14 / Uvicorn)                    │
       └──────┬───────────────────────┬────────────────────────┬──────┘
              │                       │                        │
              ▼                       ▼                        ▼
       ┌──────────────┐      ┌────────────────┐       ┌────────────────┐
       │ PIPELINE RUN │      │ CHUNK METADATA │       │ EXPORT ENGINE  │
       │ (Subprocess) │      │  (SQLite DB)   │       │    (FFmpeg)    │
       └──────┬───────┘      └────────────────┘       └────────────────┘
              │
              ├──► 1. slice.py (Silero VAD 120ms Slicing & 5s Cap)
              ├──► 2. text_grabber.py (Vertex AI Gemini Speech-to-Text)
              ├──► 3. translator.py (Duration-Constrained Neural Translation)
              ├──► 4. dubber.py (Enceladus/Neural TTS Synthesis)
              ├──► 5. stitcher.py (Anti-Bleed Waveform & Mute Gap Stitcher)
              └──► 6. auditor.py (Chipmunk & Quality Auditor)
```

---

## 🛠️ Tech Stack & Frameworks

### 🖥️ Core Backend & API Engine
- **Language:** Python 3.14 / 3.10+ (macOS Native)
- **Framework:** FastAPI (Asynchronous Web Server)
- **Multipart Parser:** `python-multipart` for robust video/audio streaming uploads
- **ASGI Server:** Uvicorn (Port `8000`)
- **Database:** SQLite3 (`localdub_history.db`) for project history & chunk states
- **Subprocess Streaming:** Async process streams via Server-Sent Events (`EventSource`)

### 🧠 AI Services & Machine Learning
- **VAD (Voice Activity Detection):** PyTorch + Silero VAD (`snakers4/silero-vad`) with NumPy PyTorch tensor conversion (bypassing `torchaudio.load()` codec restrictions).
- **LLM / Speech Processing:** Google GenAI SDK (`google-genai`) routed via Vertex AI (`vertexai=True` on GCP project `project-fa3866df-86dd-40ea-be7`, location `us-central1`).
- **Models:**
  - `gemini-2.5-flash` for high-speed transcription & duration-constrained translation.
  - `gemini-3.1-flash-tts-preview` with `Enceladus` prebuilt voice config for speech synthesis.

### 🎥 Audio & Video Processing
- **Audio Engineering:** PyDub, NumPy, PyTorch, `wave`, `ffmpeg`
- **Lossless Video Muxing:** FFmpeg (`-c:v copy` stream copying, `-filter_complex amix`)

### 🎨 Frontend & User Interface
- **Interface:** Standard HTML5, CSS3 (Catppuccin Mocha Dark Theme, 80vw Centered Layout), ES6 JavaScript
- **Audio Waveform Visualization:** WaveSurfer.js v7 with URI-encoded segment URLs (`%23`), interactive scrubbing (`dragToSeek: true`), and proportional duration scaling.
- **Streaming Protocol:** Server-Sent Events (`EventSource`) for real-time terminal output streaming.

---

## 📂 Directory & Workspace Structure

```text
/Volumes/new/LocalDubWorkspace/
├── README.md                           # Comprehensive System Documentation
├── localdub_history.db                 # SQLite Database for session storage
├── backend/
│   ├── backend_server.py               # Main FastAPI server & process stream engine
│   └── scripts/
│       ├── slice.py                    # VAD 120ms gap slicing & 5s max chunk cap
│       ├── text_grabber.py             # Audio transcription via Vertex AI
│       ├── translator.py               # Duration-aware target translation
│       ├── dubber.py                   # Enceladus TTS synthesis & time-scaling
│       ├── stitcher.py                 # Anti-bleed master waveform assembly
│       └── auditor.py                  # RMS energy & chipmunk quality auditor
├── frontend/
│   ├── index.html                      # Main Dub Studio Dashboard UI (Section 1-5 + Audit Btn)
│   ├── studio.html                     # Multi-track Sync Studio UI (16:9 frame)
│   ├── styles.css                      # Unified Catppuccin dark styling tokens
│   ├── app.js                          # Main Dashboard controller & WaveSurfer manager
│   └── studio.js                       # Multi-track sync mixer & auto-resource loader
└── projects/                           # Local SSD Storage
    └── project_<id>/                   # Isolated workspace per project
        ├── source_file.wav             # Primary imported audio/video
        ├── <name>_chunks/              # Sliced WAV chunks + timeline.json
        ├── nepali_text_<id>/           # Transcribed text files
        ├── hindi_text_<id>/            # Translated target text files
        ├── final_dubbed_<id>/          # Dubbed TTS audio chunks
        ├── FINAL_DUBBED_<name>.wav     # Stitched final master audio track
        └── resources/                  # Video media & Background music tracks
```

---

## ⚡ Step-by-Step Processing Pipeline

### 1. Smart VAD Slicing (`slice.py`)
- **120ms Silence Threshold:** Splits audio on any silence gap $\ge 120\text{ms}$ (`min_silence_duration_ms=120`), ensuring mute gaps are removed from speech chunks.
- **5.0s Maximum Chunk Cap:** Limits maximum chunk duration to **5.0 seconds**. Continuous speech blocks $> 5.0\text{s}$ are scanned for lowest RMS energy frames (breath pauses) and split into chunks $\le 5.0\text{s}$.
- Exports chunk `.wav` files and updates `timeline.json` mapping each chunk's `start_sec`, `end_sec`, and `duration_sec`.

### 2. Audio Transcription (`text_grabber.py`)
- Sends each chunk to **Vertex AI** (`gemini-2.5-flash`) for precise speech-to-text conversion.
- Saves transcriptions as individual text files (e.g., `nepali_chunk_001.txt`).

### 3. Duration-Aware Neural Translation (`translator.py`)
- Reads exact speech durations from `timeline.json`.
- Instructs Vertex AI Gemini to translate text concisely matching original physical speech duration:
  > *"CRITICAL TIMING & LENGTH RULE: The translated text MUST match the exact length and duration of the original speech window. Keep it concise, direct, and rhythmic."*

### 4. Voice TTS Synthesis & Alignment (`dubber.py`)
- Synthesizes audio using Vertex AI Gemini TTS (`gemini-3.1-flash-tts-preview` with `Enceladus` voice).
- Automatically scales TTS speech via FFmpeg `atempo` filter to match the speech window of the original chunk.

### 5. Anti-Bleed Master Assembly (`stitcher.py`)
- Establishes a millisecond-exact master audio canvas matching source audio length.
- Calculates available window for each chunk (`next_start_ms - start_ms`).
- Auto-fits (`fit_audio_to_window`) any dubbed chunk exceeding its window to prevent audio bleeding into adjacent speech chunks or corrupting mute gaps.
- Preserves non-speech mute gaps as pure silence intervals.

### 6. Automated Quality Audit (`auditor.py`)
- Scans all master chunks for dead audio (zero RMS), chipmunk speedup distortion, and length anomalies.
- Generates `scrambled_audio_log_<project>.txt`.
- Executable on demand via the **`Run Quality Audit Check`** button in Section 2 of the Web Dashboard.

---

## 🎬 Dashboard & Step 4 Enhancements

- **Proportional Waveform Scaling in Step 4**:
  - Waveforms in Step 4 scale their visual container width proportionally to the actual duration relative to the 5.0s max chunk window (`width = (duration / 5.0) * 100%`).
  - Displays explicit duration readouts (e.g., `00:00.00 / 00:01.66 (1.66s)`).
- **URI-Encoded Media URLs (`getMediaUrl`)**:
  - All media paths containing `#`, spaces, or special characters are encoded (`encodeURIComponent`) to ensure `200 OK` responses without URL fragment stripping.
- **Interactive Waveform Scrubbing**:
  - Enabled `dragToSeek: true` and bound `ready`, `decode`, `timeupdate`, `seeking`, `interaction` events on WaveSurfer instances.
- **Dedicated Audit Check Button**:
  - Added in Section 2 right below the terminal log window to trigger `auditor.py` on demand and stream results live.

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- macOS with Python 3.10+ or 3.14 installed.
- **FFmpeg** installed and accessible in system PATH:
  ```bash
  brew install ffmpeg
  ```

### 2. Environment Setup
```bash
cd /Volumes/new/LocalDubWorkspace
python3 -m pip install fastapi uvicorn python-multipart pydub torch numpy wave google-genai certifi
```

---

## 🚀 Running the Application

### 1. Start FastAPI Backend Engine
```bash
cd /Volumes/new/LocalDubWorkspace
.venv/bin/python -m uvicorn backend.backend_server:app --reload --host 127.0.0.1 --port 8000
```

### 2. Open Web Studio Dashboard
- 👉 **Dashboard Workstation:** [http://127.0.0.1:8000/static/index.html](http://127.0.0.1:8000/static/index.html)
- 👉 **Video Sync Studio:** [http://127.0.0.1:8000/static/studio.html?project_id=<project_id>](http://127.0.0.1:8000/static/studio.html?project_id=%3Cproject_id%3E)

---

## 🛡️ Key System Guidelines for Developers & Future Agents

1. **Keep GCP Routing Intact**:
   - Always initialize GenAI Client with `vertexai=True`, `project="project-fa3866df-86dd-40ea-be7"`, `location="us-central1"` to utilize active GCP credits ($300 GCP credit).
2. **Preserve URI Encoding**:
   - When referencing files in `projects/`, always use `getMediaUrl()` or `encodeURIComponent` on path segments so `#` in project folder names does not break HTTP requests.
3. **Maintain 120ms Silence Threshold & 5s Cap in `slice.py`**:
   - Do not revert `min_silence_duration_ms` above 150ms or `MAX_CHUNK_SEC` above 5.0s to ensure clean speech chunks and prevent internal mute gaps.
4. **Incremental Execution**:
   - `translator.py` and `dubber.py` check file modification timestamps (`mtime`) to skip re-processing unchanged chunks unless modified.
