# 🎙️ ULTIMATE DUB STUDIO — Local AI Video & Audio Dubbing Engine

> **A high-performance, privacy-focused, local-first video and audio dubbing studio built for macOS.** Featuring intelligent Voice Activity Detection (VAD) slicing, AI-powered transcription and translation via Vertex AI, neural speech synthesis, exact-timestamp waveform alignment, and a real-time multi-track video sync studio with lossless export.

---

## 🎯 Project Objective

The core objective of **ULTIMATE DUB STUDIO** is to provide an end-to-end, automated localized dubbing platform that:
1. **Preserves Original Timeline Integrity**: Ensures dubbed speech matches the exact timing, pauses, and cadence of the source audio through timestamp-mapped segment reconstruction rather than simple audio concatenation.
2. **Eliminates Quality Loss**: Renders multi-track dubbed video projects without video re-encoding (`-c:v copy`), retaining 100% of original visual fidelity and resolution.
3. **Offers Human-in-the-Loop Control**: Provides non-destructive text editing at the chunk level, allowing users to fine-tune transcriptions/translations and re-synthesize individual audio segments on demand.
4. **Delivers Real-time Progress Tracking**: Delivers line-by-line terminal and browser logs via Server-Sent Events (SSE) alongside a visual stage stepper.
5. **Provides Widescreen Multi-Track Syncing**: Features a 16:9 YouTube aspect ratio Sync Studio canvas with auto-resource detection, video-independent audio muting, and background music integration.

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
              ├──► 1. slice.py (Silero VAD Slicing & Timeline Mapping)
              ├──► 2. text_grabber.py (Vertex AI Gemini Speech-to-Text)
              ├──► 3. translator.py (Vertex AI Gemini Neural Translation)
              ├──► 4. dubber.py (Neural Text-to-Speech Synthesis)
              ├──► 5. stitcher.py (Exact-Timestamp Waveform Assembly)
              └──► 6. auditor.py (Audio Quality & Speed Factor Verification)
```

## 🛠️ Tech Stack & Frameworks

### 🖥️ Core Backend & API Engine
- **Language:** Python 3.14 / 3.10+ (macOS Native)
- **Framework:** FastAPI (Asynchronous Web Server)
- **Multipart Parser:** `python-multipart` for robust video/audio streaming uploads
- **ASGI Server:** Uvicorn
- **Database:** SQLite3 (`localdub_history.db`) for project history & chunk states
- **Subprocess Streaming:** Python `asyncio` + Server-Sent Events (`EventSource`)

### 🧠 AI Services & Machine Learning
- **VAD (Voice Activity Detection):** PyTorch + Silero VAD (`snakers4/silero-vad`)
- **LLM / Speech Processing:** Google GenAI SDK (`google-genai`) routed via Vertex AI (`vertexai=True` on GCP)
- **Model:** `gemini-2.5-flash` for high-speed transcription & context-aware target translation

### 🎥 Audio & Video Processing
- **Audio Engineering:** PyDub, `wave`, `ffmpeg`
- **Lossless Video Muxing:** FFmpeg (`-c:v copy` stream copying, `-filter_complex amix`)

### 🎨 Frontend & User Interface
- **Interface:** Standard HTML5, CSS3 (Catppuccin Mocha Variable System, 80vw Centered Layout), ES6 JavaScript
- **Audio Waveform Visualization:** WaveSurfer.js v7 (Interactive multi-track scrubbers & timecodes)
- **Streaming Protocol:** Server-Sent Events (`EventSource`) for real-time log output and progress updates

---

## 📂 Directory & Project Workspace Structure

```text
/Volumes/new/LocalDubWorkspace/
├── readme.md                           # Comprehensive System Documentation
├── localdub_history.db                 # SQLite Database for session storage
├── backend/
│   ├── backend_server.py               # Main FastAPI server script
│   └── scripts/
│       ├── slice.py                    # VAD Slicing & timeline.json generation
│       ├── text_grabber.py             # Audio transcription via Vertex AI
│       ├── translator.py               # Target language translation
│       ├── dubber.py                   # Enceladus/Neural TTS generation
│       ├── stitcher.py                 # Time-aligned master audio reconstructor
│       └── auditor.py                  # Chipmunk & duration quality auditor
├── frontend/
│   ├── index.html                      # Main Dub Studio Dashboard UI (80vw centered)
│   ├── studio.html                     # Multi-track Sync Studio UI (16:9 frame)
│   ├── styles.css                      # Unified design tokens & Catppuccin dark theme
│   ├── app.js                          # Main Dashboard app controller & state manager
│   └── studio.js                       # Multi-track sync mixer & auto-resource loader
└── projects/                           # Project SSD Storage
    └── project_<id>/                   # Isolated workspace per project
        ├── source_file.wav             # Primary imported audio/video
        ├── <name>_chunks/              # Sliced audio chunks + timeline.json
        ├── nepali_text_<id>/           # Transcribed text files
        ├── hindi_text_<id>/            # Translated target text files
        ├── final_dubbed_<id>/          # Dubbed audio chunks
        ├── FINAL_DUBBED_<name>.wav     # Stitched final dubbed master audio
        └── resources/                  # Dedicated Video files & Background music
            ├── #14_Let's_Play.mp4
            └── bgm_track.wav
```

---

## ⚡ Step-by-Step Processing Pipeline

### 1. Smart VAD Slicing (`slice.py`)
- Uses **PyTorch Silero VAD** to detect active speech boundaries.
- **Applies a 100ms Silence Rule:** Gaps `< 100 ms` are preserved inside sentence chunks to avoid artificial cutting; gaps `≥ 100 ms` split audio into distinct speech chunks (capped at `6.0s`).
- Exports chunk `.wav` files and generates `timeline.json` mapping each chunk to its exact start and end seconds on the master audio timeline.

### 2. Audio Transcription (`text_grabber.py`)
- Sends each chunk to **Vertex AI** (`gemini-2.5-flash`) for precise speech-to-text conversion.
- Saves transcriptions as individual text files (e.g., `nepali_chunk_001.txt`).

### 3. Neural Translation (`translator.py`)
- Translates transcribed speech into the target language (e.g., Hindi, Hinglish, English, Nepali, Spanish).
- Performs **timestamp-aware translation** to ensure target phrase length naturally matches original chunk duration.

### 4. Voice TTS Synthesis (`dubber.py`)
- Synthesizes audio using neural TTS for each translated text chunk.
- Outputs individual dubbed WAV files (e.g., `dub_chunk_001.wav`).

### 5. Time-Aligned Segment Assembly (`stitcher.py`)
- Reads `timeline.json` to extract precise millisecond start timestamps for every chunk.
- Generates a silent canvas equal to the exact duration of the original audio track.
- Overlays each dubbed chunk at its explicit start timestamp—preserving every original breath, silence, and pause seamlessly across the timeline.

### 6. Lossless Video Export (`backend_server.py`)
- Combines original video, dubbed audio, and background music using FFmpeg.
- Uses `-c:v copy` to duplicate video streams with zero re-encoding or resolution loss.

---

## 🎬 Sync Studio & Asset Features

- **16:9 Widescreen YouTube Frame:** Embedded HTML5 video container with `aspect-ratio: 16 / 9` and `object-fit: contain` for balanced widescreen previewing.
- **Auto-Resource Directory Scanner:** Automatically detects and auto-loads uploaded videos and background music directly from `projects/<project_id>/resources/` upon session open or hard refresh.
- **URL-Encoded Special Characters Handling:** Automatically handles filenames containing special characters, spaces, or symbols (e.g., `#14 Let's Play.mp4`) via URI encoding to prevent HTML5 player breakage.
- **Independent Video Mute Control:** Mute or unmute embedded video stream audio separately from the master dubbed audio track (🔇 `Mute Video Audio`).
- **Multi-Track Mixer:** Synchronizes three independent audio layers with live scrubbing:
  - **Track 1:** Original Main Audio Track
  - **Track 2:** Final Stitched Dubbed Audio Track
  - **Track 3:** Background Music & FX Track (`resources/bgm_*`)

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- macOS with Python 3.10+ or 3.14 installed.
- **FFmpeg** installed and accessible in your system path:
  ```bash
  brew install ffmpeg
  ```

### 2. Environment Configuration
Clone/navigate to your workspace directory and install required Python dependencies:
```bash
cd /Volumes/new/LocalDubWorkspace
python3 -m pip install fastapi uvicorn python-multipart pydub torch wave google-genai certifi
```

---

## 🚀 Running the Application

### 1. Start the FastAPI Backend Engine
Launch the backend server from the project root:
```bash
cd /Volumes/new/LocalDubWorkspace
python3 -m uvicorn backend.backend_server:app --reload --host 127.0.0.1 --port 8000
```

### 2. Open the Web Studio Dashboard
Open your web browser and navigate to:
- 👉 **Dashboard Workstation:** [http://127.0.0.1:8000/static/index.html](http://127.0.0.1:8000/static/index.html)
- 👉 **Video Sync Studio:** [http://127.0.0.1:8000/static/studio.html?project_id=<project_id>](http://127.0.0.1:8000/static/studio.html?project_id=%3Cproject_id%3E)

---

## 🛡️ Resilience & Non-Destructive Editing Features

- **GCP Credit Routing:** Configured exclusively for Google Cloud Vertex AI (`vertexai=True`), preventing AI Studio prepayment depletion errors.
- **Non-Destructive Text Edits:** Allows live text editing of any chunk. Saving a text file updates disk files directly without altering adjacent chunks.
- **Smart Incremental Execution:** `translator.py` and `dubber.py` analyze modification timestamps (`mtime`) and skip unchanged chunks during re-runs.
- **Clean Workspace Wipe-Off:** The "Wipe Off" feature permanently deletes all local project assets, cleans SQLite database records, and reloads the studio interface, leaving zero traces behind.
