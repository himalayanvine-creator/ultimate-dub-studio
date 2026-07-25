const API_BASE = "http://127.0.0.1:8000";

let waveSurfer;
let isPlaying = false;
let currentSpeed = 1.0;
let currentVolume = 1.0;
let isSliceMode = false;
let zoomLevel = 1.0;

// State Management
const DAWState = {
    projectId: "",
    audioFile: "",
    originalTimeline: [],
    currentTimeline: [],
    undoStack: [],
    redoStack: [],
    manualSlices: [],
    selectedChunk: null,
    isDirty: false,
    chunkMetadata: {}
};

window.addEventListener("DOMContentLoaded", async () => {
    initWaveSurfer();
    await loadProjectData();
    renderChunkList();
    updateHistoryDisplay();
});

function getProjectIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("project_id") || "";
}

function initWaveSurfer() {
    waveSurfer = WaveSurfer.create({
        container: "#waveform",
        waveColor: "#45475a",
        progressColor: "#a6e3a1",
        cursorColor: "#f38ba8",
        barWidth: 2,
        barRadius: 3,
        height: "auto",
        normalize: true,
        backend: "WebAudio"
    });

    // Time update listener
    waveSurfer.on("audioprocess", () => {
        updateTimeDisplay();
    });

    // Play/Pause state
    waveSurfer.on("play", () => {
        isPlaying = true;
        updatePlayButton();
    });

    waveSurfer.on("pause", () => {
        isPlaying = false;
        updatePlayButton();
    });

    // Click to add slice point
    waveSurfer.on("click", (relativeX) => {
        if (isSliceMode) {
            const duration = waveSurfer.getDuration();
            const clickTime = relativeX * duration;
            addManualSlice(clickTime);
        }
    });

    // Ready event
    waveSurfer.on("ready", () => {
        renderWaveformOverlay();
    });
}

async function loadProjectData() {
    DAWState.projectId = getProjectIdFromUrl();
    if (!DAWState.projectId) {
        alert("No project ID specified");
        return;
    }

    try {
        // Fetch project info
        const historyRes = await fetch(`${API_BASE}/api/projects/history/list`);
        if (!historyRes.ok) throw new Error("Failed to fetch project history");

        const historyData = await historyRes.json();
        const project = historyData.projects.find(p => p.project_id === DAWState.projectId);
        if (!project) throw new Error("Project not found");

        DAWState.audioFile = project.source_file;

        // Load audio into WaveSurfer
        const audioUrl = `${API_BASE}/media/${DAWState.projectId}/${encodeURIComponent(DAWState.audioFile)}`;
        await waveSurfer.load(audioUrl);

        // Fetch chunks metadata
        const chunksRes = await fetch(`${API_BASE}/api/projects/${DAWState.projectId}/chunks`);
        if (chunksRes.ok) {
            const chunksData = await chunksRes.json();
            DAWState.chunkMetadata = chunksData;

            // Parse timeline.json to get original slices
            const timelineFile = `${chunksData.chunks_folder}/timeline.json`;
            const timelineRes = await fetch(
                `${API_BASE}/media/${DAWState.projectId}/${encodeURIComponent(timelineFile)}`
            );

            if (timelineRes.ok) {
                const timelineData = await timelineRes.json();
                DAWState.originalTimeline = Object.values(timelineData).map(chunk => ({
                    start: chunk.start_sec,
                    end: chunk.end_sec,
                    duration: chunk.duration_sec,
                    chunkId: Object.keys(timelineData).find(k => timelineData[k] === chunk)
                }));
                DAWState.currentTimeline = JSON.parse(JSON.stringify(DAWState.originalTimeline));
            }
        }

        updateStatus();
    } catch (err) {
        console.error("Error loading project:", err);
        alert(`Error: ${err.message}`);
    }
}

function renderChunkList() {
    const container = document.getElementById("chunk-list-container");
    container.innerHTML = "";

    DAWState.currentTimeline.forEach((chunk, idx) => {
        const div = document.createElement("div");
        div.className = "chunk-item";
        if (DAWState.selectedChunk === idx) div.classList.add("active");

        div.innerHTML = `
            <div><strong>chunk_${String(idx + 1).padStart(3, "0")}</strong></div>
            <div class="chunk-info">
                ${formatTime(chunk.start)} → ${formatTime(chunk.end)}<br>
                Duration: ${chunk.duration.toFixed(2)}s
            </div>
        `;

        div.addEventListener("click", () => selectChunk(idx));
        container.appendChild(div);
    });
}

function selectChunk(index) {
    DAWState.selectedChunk = index;
    renderChunkList();
    
    const chunk = DAWState.currentTimeline[index];
    waveSurfer.seekTo(chunk.start / waveSurfer.getDuration());
}

function formatTime(sec) {
    const mins = Math.floor(sec / 60);
    const secs = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 100);
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(ms).padStart(2, "0")}`;
}

function updateTimeDisplay() {
    const currentTime = waveSurfer.getCurrentTime();
    document.getElementById("current-time").textContent = formatTime(currentTime);
}

function togglePlay() {
    waveSurfer.playPause();
}

function updatePlayButton() {
    const btn = document.getElementById("btn-play");
    btn.textContent = isPlaying ? "⏸" : "▶";
    btn.style.background = isPlaying ? "#f38ba8" : "#313244";
}

function stopPlayback() {
    waveSurfer.pause();
    waveSurfer.seekTo(0);
}

function skipToStart() {
    waveSurfer.seekTo(0);
}

function skipToEnd() {
    waveSurfer.seekTo(1);
}

function changeSpeed(delta) {
    setSpeed(Math.max(0.25, Math.min(2.0, currentSpeed + delta)));
}

function setSpeed(speed) {
    currentSpeed = parseFloat(speed);
    waveSurfer.setPlaybackRate(currentSpeed);
    document.getElementById("speed-slider").value = currentSpeed;
    document.getElementById("speed-value").textContent = currentSpeed.toFixed(2) + "x";
}

function setVolume(vol) {
    currentVolume = parseFloat(vol);
    waveSurfer.setVolume(currentVolume);
}

function toggleSliceMode() {
    isSliceMode = !isSliceMode;
    const btn = document.getElementById("btn-slice");
    btn.classList.toggle("active", isSliceMode);
    
    const indicator = document.getElementById("mode-indicator");
    if (isSliceMode) {
        indicator.textContent = "MANUAL";
        indicator.classList.add("manual");
    } else {
        indicator.textContent = "AUTO";
        indicator.classList.remove("manual");
    }

    updateStatus();
}

function addManualSlice(time) {
    // Find which chunk this time falls into
    const chunkIdx = DAWState.currentTimeline.findIndex(
        chunk => time >= chunk.start && time <= chunk.end
    );

    if (chunkIdx === -1) return;

    // Save current state to undo stack
    saveToUndoStack();

    const chunk = DAWState.currentTimeline[chunkIdx];
    
    // Split the chunk at the click point
    const newChunks = [
        { start: chunk.start, end: time, duration: time - chunk.start },
        { start: time, end: chunk.end, duration: chunk.end - time }
    ];

    DAWState.currentTimeline.splice(chunkIdx, 1, ...newChunks);
    DAWState.isDirty = true;

    renderChunkList();
    renderWaveformOverlay();
    updateStatus();
    showUnsavedIndicator();
}

function splitAtCursor() {
    if (DAWState.selectedChunk === null) {
        alert("Please select a chunk to split");
        return;
    }

    const cursorTime = waveSurfer.getCurrentTime();
    const chunk = DAWState.currentTimeline[DAWState.selectedChunk];

    if (cursorTime <= chunk.start || cursorTime >= chunk.end) {
        alert("Cursor must be within the selected chunk");
        return;
    }

    saveToUndoStack();

    const newChunks = [
        { start: chunk.start, end: cursorTime, duration: cursorTime - chunk.start },
        { start: cursorTime, end: chunk.end, duration: chunk.end - cursorTime }
    ];

    DAWState.currentTimeline.splice(DAWState.selectedChunk, 1, ...newChunks);
    DAWState.isDirty = true;

    renderChunkList();
    renderWaveformOverlay();
    updateStatus();
    showUnsavedIndicator();
}

function mergeChunks() {
    if (DAWState.selectedChunk === null || DAWState.selectedChunk >= DAWState.currentTimeline.length - 1) {
        alert("Please select a chunk to merge (not the last one)");
        return;
    }

    saveToUndoStack();

    const chunk1 = DAWState.currentTimeline[DAWState.selectedChunk];
    const chunk2 = DAWState.currentTimeline[DAWState.selectedChunk + 1];

    const merged = {
        start: chunk1.start,
        end: chunk2.end,
        duration: chunk2.end - chunk1.start
    };

    DAWState.currentTimeline.splice(DAWState.selectedChunk, 2, merged);
    DAWState.isDirty = true;

    renderChunkList();
    renderWaveformOverlay();
    updateStatus();
    showUnsavedIndicator();
}

function resetSlices() {
    if (!confirm("Reset all manual changes? This cannot be undone immediately.")) return;

    saveToUndoStack();
    DAWState.currentTimeline = JSON.parse(JSON.stringify(DAWState.originalTimeline));
    DAWState.isDirty = true;

    renderChunkList();
    renderWaveformOverlay();
    updateStatus();
    showUnsavedIndicator();
}

function undoEdit() {
    if (DAWState.undoStack.length === 0) {
        alert("Nothing to undo");
        return;
    }

    DAWState.redoStack.push(JSON.parse(JSON.stringify(DAWState.currentTimeline)));
    DAWState.currentTimeline = DAWState.undoStack.pop();

    renderChunkList();
    renderWaveformOverlay();
    updateHistoryDisplay();
    showUnsavedIndicator();
}

function redoEdit() {
    if (DAWState.redoStack.length === 0) {
        alert("Nothing to redo");
        return;
    }

    DAWState.undoStack.push(JSON.parse(JSON.stringify(DAWState.currentTimeline)));
    DAWState.currentTimeline = DAWState.redoStack.pop();

    renderChunkList();
    renderWaveformOverlay();
    updateHistoryDisplay();
    showUnsavedIndicator();
}

function saveToUndoStack() {
    DAWState.undoStack.push(JSON.parse(JSON.stringify(DAWState.currentTimeline)));
    DAWState.redoStack = []; // Clear redo stack on new action
    updateHistoryDisplay();
}

function updateHistoryDisplay() {
    const container = document.getElementById("history-container");
    container.innerHTML = "";

    DAWState.undoStack.forEach((state, idx) => {
        const div = document.createElement("div");
        div.className = "history-item";
        div.textContent = `Edit ${idx + 1} (${state.length} chunks)`;
        div.addEventListener("click", () => {
            DAWState.currentTimeline = JSON.parse(JSON.stringify(state));
            DAWState.undoStack.splice(idx);
            DAWState.redoStack = [];
            renderChunkList();
            renderWaveformOverlay();
            updateHistoryDisplay();
            showUnsavedIndicator();
        });
        container.appendChild(div);
    });

    if (DAWState.undoStack.length === 0) {
        const div = document.createElement("div");
        div.className = "history-item";
        div.textContent = "No edits yet";
        container.appendChild(div);
    }
}

function renderWaveformOverlay() {
    const container = document.getElementById("waveform-wrapper");
    
    // Remove existing markers
    container.querySelectorAll(".slice-marker").forEach(m => m.remove());

    const duration = waveSurfer.getDuration();
    if (duration === 0) return;

    DAWState.currentTimeline.forEach((chunk, idx) => {
        const startPercent = (chunk.start / duration) * 100;
        const endPercent = (chunk.end / duration) * 100;

        // Start marker
        const startMarker = document.createElement("div");
        startMarker.className = "slice-marker";
        startMarker.style.left = startPercent + "%";
        startMarker.draggable = true;
        startMarker.addEventListener("dragstart", () => {
            startMarker.dataset.type = "start";
            startMarker.dataset.chunkIdx = idx;
        });
        container.appendChild(startMarker);

        // End marker
        const endMarker = document.createElement("div");
        endMarker.className = "slice-marker";
        endMarker.style.left = endPercent + "%";
        endMarker.draggable = true;
        endMarker.addEventListener("dragstart", () => {
            endMarker.dataset.type = "end";
            endMarker.dataset.chunkIdx = idx;
        });
        container.appendChild(endMarker);
    });

    // Drag listeners
    container.addEventListener("dragover", (e) => e.preventDefault());
    container.addEventListener("drop", (e) => {
        e.preventDefault();
        const marker = e.dataTransfer.getData("marker");
    });
}

function zoomIn() {
    setZoom(Math.min(10, zoomLevel + 0.5));
}

function zoomOut() {
    setZoom(Math.max(1, zoomLevel - 0.5));
}

function setZoom(zoom) {
    zoomLevel = parseFloat(zoom);
    document.getElementById("zoom-slider").value = zoomLevel;
    waveSurfer.zoom(zoomLevel * 50); // Scale zoom for WaveSurfer
}

function updateStatus() {
    document.getElementById("status-chunks").textContent = `Chunks: ${DAWState.currentTimeline.length}`;
    
    const totalDuration = DAWState.currentTimeline.reduce((sum, c) => sum + c.duration, 0);
    document.getElementById("status-duration").textContent = `Duration: ${formatTime(totalDuration)}`;
    
    const mode = isSliceMode ? "MANUAL" : "AUTO";
    document.getElementById("status-mode").textContent = `Mode: ${mode}`;
}

function showUnsavedIndicator() {
    document.getElementById("status-unsaved").style.display = "block";
}

function hideUnsavedIndicator() {
    document.getElementById("status-unsaved").style.display = "none";
}

async function saveSliceChanges() {
    if (!DAWState.isDirty && DAWState.undoStack.length === 0) {
        alert("No changes to save");
        return;
    }

    try {
        const payload = {
            project_id: DAWState.projectId,
            slices: DAWState.currentTimeline.map(chunk => ({
                start_sec: chunk.start,
                end_sec: chunk.end,
                duration_sec: chunk.duration
            }))
        };

        const res = await fetch(`${API_BASE}/api/projects/${DAWState.projectId}/save-slices`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error("Failed to save slices");

        const data = await res.json();
        
        alert("✓ Slices saved successfully! Chunks have been renamed and re-exported.");
        
        // Reset state
        DAWState.isDirty = false;
        DAWState.undoStack = [];
        DAWState.redoStack = [];
        hideUnsavedIndicator();
        
        // Reload project data
        await loadProjectData();
        renderChunkList();
        updateHistoryDisplay();

    } catch (err) {
        alert(`Error saving slices: ${err.message}`);
    }
}

function syncSliceState() {
    location.reload();
}

// Modal functions
function showModal(title, message, callback) {
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-message").textContent = message;
    window.modalCallback = callback;
    document.getElementById("confirm-modal").style.display = "flex";
}

function closeModal() {
    document.getElementById("confirm-modal").style.display = "none";
}

function confirmAction() {
    if (window.modalCallback) {
        window.modalCallback();
    }
    closeModal();
}
