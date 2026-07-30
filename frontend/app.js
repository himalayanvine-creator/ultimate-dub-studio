const API_BASE = "http://127.0.0.1:8000";

const AppState = {
    activeProjectId: "",
    currentBaseName: "",
    sourceFileName: "",
    activeChunkId: "",
    chunksMap: {},
    chunksFolderName: "",
    dubbedFolderName: "",
    activeEventSource: null
};

let wsChunkOrig, wsChunkDub, wsFinalOrig, wsFinalDub;

function getMediaUrl(relativePath) {
    if (!relativePath) return "";
    const parts = relativePath.split('/').map(p => encodeURIComponent(p));
    return `${API_BASE}/media/${parts.join('/')}`;
}

window.addEventListener("DOMContentLoaded", () => {
    const projInput = document.getElementById("project-name");
    if (projInput) projInput.setAttribute("autocomplete", "off");

    wsChunkOrig = WaveSurfer.create({
        container: "#waveform-chunk-orig",
        waveColor: "#45475a",
        progressColor: "#a6e3a1",
        height: 60,
        barWidth: 2,
        cursorColor: "#cba6f7",
        cursorWidth: 2,
        dragToSeek: true
    });

    wsChunkDub = WaveSurfer.create({
        container: "#waveform-chunk-dub",
        waveColor: "#45475a",
        progressColor: "#89b4fa",
        height: 60,
        barWidth: 2,
        cursorColor: "#cba6f7",
        cursorWidth: 2,
        dragToSeek: true
    });

    wsFinalOrig = WaveSurfer.create({
        container: "#waveform-final-orig",
        waveColor: "#f9e2af",
        progressColor: "#fab387",
        height: 70,
        barWidth: 2,
        cursorColor: "#cba6f7",
        cursorWidth: 2,
        dragToSeek: true
    });

    wsFinalDub = WaveSurfer.create({
        container: "#waveform-final-dub",
        waveColor: "#45475a",
        progressColor: "#89b4fa",
        height: 70,
        barWidth: 2,
        cursorColor: "#cba6f7",
        cursorWidth: 2,
        dragToSeek: true
    });

    function bindWaveSurferEvents(instance, elemId) {
        instance.on('ready', () => updateTimeDisplay(elemId, instance));
        instance.on('decode', () => updateTimeDisplay(elemId, instance));
        instance.on('timeupdate', () => updateTimeDisplay(elemId, instance));
        instance.on('interaction', () => updateTimeDisplay(elemId, instance));
        instance.on('seeking', () => updateTimeDisplay(elemId, instance));
    }

    bindWaveSurferEvents(wsChunkOrig, 'sliced-chunk');
    bindWaveSurferEvents(wsChunkDub, 'dubbed-chunk');
    bindWaveSurferEvents(wsFinalOrig, 'final-orig');
    bindWaveSurferEvents(wsFinalDub, 'final-dub');

    autoLoadLatestProject();
});

function formatTime(sec) {
    if (isNaN(sec)) return "00:00.00";
    const minutes = Math.floor(sec / 60);
    const seconds = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 100);
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
}

function updateTimeDisplay(elemId, instance) {
    const duration = instance.getDuration();
    const current = instance.getCurrentTime();
    const currentFormatted = formatTime(current);
    const totalFormatted = formatTime(duration);
    
    const timeElem = document.getElementById(`time-${elemId}`);
    if (timeElem) {
        if (!isNaN(duration) && duration > 0) {
            timeElem.innerText = `${currentFormatted} / ${totalFormatted} (${duration.toFixed(2)}s)`;
        } else {
            timeElem.innerText = `${currentFormatted} / ${totalFormatted}`;
        }
    }

    if (elemId === 'sliced-chunk' || elemId === 'dubbed-chunk') {
        const container = document.getElementById(elemId === 'sliced-chunk' ? 'waveform-chunk-orig' : 'waveform-chunk-dub');
        if (container && !isNaN(duration) && duration > 0) {
            const propWidth = Math.min(100, Math.max(15, (duration / 5.0) * 100));
            container.style.width = `${propWidth}%`;
            container.style.transition = "width 0.3s ease";
        }
    }
}

function appendLog(message, isError = false) {
    const logBox = document.getElementById("log-output");
    if (!logBox) return;
    const timestamp = new Date().toLocaleTimeString();
    const style = isError ? "color: #f38ba8;" : "color: #a6e3a1;";
    logBox.innerHTML += `<br><span style="${style}">[${timestamp}] ${message}</span>`;
    logBox.scrollTop = logBox.scrollHeight;
}

function resetLogBox() {
    const logBox = document.getElementById("log-output");
    if (logBox) {
        logBox.innerHTML = "System initialized. Ready for job launch...";
    }
}

function updateStepProgress(activeStepKey) {
    const steps = [
        { id: "step-slice", key: "slice" },
        { id: "step-transcribe", key: "transcribe" },
        { id: "step-translate", key: "translate" },
        { id: "step-dub", key: "dub" },
        { id: "step-audit", key: "audit" }
    ];

    let foundActive = false;

    steps.forEach(step => {
        const elem = document.getElementById(step.id);
        if (!elem) return;

        if (step.key === activeStepKey) {
            elem.className = "step-badge active";
            foundActive = true;
        } else if (!foundActive && activeStepKey !== "none") {
            elem.className = "step-badge completed";
        } else if (activeStepKey === "completed_all") {
            elem.className = "step-badge completed";
        } else {
            elem.className = "step-badge pending";
        }
    });
}

function startNewProjectUI() {
    if (AppState.activeProjectId) {
        if (confirm("Start a new project? Your current active workspace UI will be cleared (saved projects remain safe in history).")) {
            resetFullStudioUI();
            appendLog("Ready for a new project. Enter details above and click Start Process!");
        }
    } else {
        resetFullStudioUI();
        appendLog("Ready for a new project. Enter details above and click Start Process!");
    }
}

function resetFullStudioUI() {
    AppState.activeProjectId = "";
    AppState.currentBaseName = "";
    AppState.sourceFileName = "";
    AppState.activeChunkId = "";
    AppState.chunksMap = {};

    document.getElementById("upload-form").reset();
    document.getElementById("project-name").value = "";
    document.getElementById("media-file").value = "";
    document.getElementById("target-language").value = "Hindi";

    resetLogBox();
    updateStepProgress("none");

    document.getElementById("text-type-select").value = "";
    if (typeof onTextTypeChange === 'function') onTextTypeChange();

    document.getElementById("sliced-chunk-select").innerHTML = '<option value="">-- Select Sliced Chunk --</option>';
    document.getElementById("dubbed-chunk-select").innerHTML = '<option value="">-- Select Dubbed Chunk --</option>';

    if (wsChunkOrig) wsChunkOrig.empty();
    if (wsChunkDub) wsChunkDub.empty();
    if (wsFinalOrig) wsFinalOrig.empty();
    if (wsFinalDub) wsFinalDub.empty();
}

async function saveActiveProject() {
    if (!AppState.activeProjectId) {
        alert("No active project loaded to save.");
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/projects/${AppState.activeProjectId}/save`, { method: "POST" });
        if (!res.ok) throw new Error("Failed to save project state");
        appendLog(`💾 Project '${AppState.activeProjectId}' state saved.`);
        fetchProjectHistory();
        alert(`Project state for '${AppState.activeProjectId}' has been saved!`);
    } catch (err) {
        appendLog(`❌ Save error: ${err.message}`, true);
        alert(`Save error: ${err.message}`);
    }
}

document.getElementById("upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("btn-submit");
    btn.disabled = true;
    btn.innerText = "Initializing...";

    const mediaFileInput = document.getElementById("media-file");
    const formData = new FormData();
    formData.append("project_name", document.getElementById("project-name").value);
    formData.append("target_language", document.getElementById("target-language").value);
    
    if (mediaFileInput.files.length > 0) {
        formData.append("media_file", mediaFileInput.files[0]);
    }

    try {
        appendLog("Checking project workspace on SSD...");
        const res = await fetch(`${API_BASE}/api/projects/create`, { method: "POST", body: formData });
        if (!res.ok) throw new Error("Failed project creation");
        const data = await res.json();
        
        AppState.activeProjectId = data.project_id;
        AppState.sourceFileName = data.source_file;
        AppState.currentBaseName = data.source_file.substring(0, data.source_file.lastIndexOf('.')) || data.source_file;

        appendLog(`✓ Workspace Connected ID: '${AppState.activeProjectId}'`);
        executePipelineStream();

    } catch (err) {
        appendLog(`❌ Error: ${err.message}`, true);
        btn.disabled = false;
        btn.innerText = "Start Process";
    }
});

function executePipelineStream() {
    appendLog("Connecting real-time process feed...");
    
    if (AppState.activeEventSource) {
        AppState.activeEventSource.close();
    }

    AppState.activeEventSource = new EventSource(`${API_BASE}/api/projects/${AppState.activeProjectId}/run-pipeline-stream`);

    AppState.activeEventSource.onmessage = async (event) => {
        const msg = event.data;

        if (msg.includes("slice.py")) updateStepProgress("slice");
        else if (msg.includes("text_grabber.py")) updateStepProgress("transcribe");
        else if (msg.includes("translator.py")) updateStepProgress("translate");

        appendLog(msg);

        if (msg.includes("[COMPLETE]")) {
            AppState.activeEventSource.close();
            AppState.activeEventSource = null;
            updateStepProgress("completed_all");
            document.getElementById("btn-submit").disabled = false;
            document.getElementById("btn-submit").innerText = "Start Process";
            await loadProjectData();
            fetchProjectHistory();
            appendLog("✅ Translation Pipeline completed! You can now review/edit texts in Section 3, then click 'Start Dubbing Pipeline' below.");
        }
    };

    AppState.activeEventSource.onerror = (err) => {
        if (AppState.activeEventSource) {
            AppState.activeEventSource.close();
            AppState.activeEventSource = null;
        }
        document.getElementById("btn-submit").disabled = false;
        document.getElementById("btn-submit").innerText = "Start Process";
    };
}

async function stopProcess() {
    if (!AppState.activeProjectId) {
        alert("No active process running to stop.");
        return;
    }

    appendLog(`🛑 Stopping execution for project '${AppState.activeProjectId}'...`, true);

    if (AppState.activeEventSource) {
        AppState.activeEventSource.close();
        AppState.activeEventSource = null;
    }

    try {
        const res = await fetch(`${API_BASE}/api/projects/${AppState.activeProjectId}/stop`, { method: "POST" });
        if (res.ok) {
            appendLog(`🛑 Process stopped cleanly! Saved to past projects history gallery.`, true);
        }
    } catch (err) {
        appendLog(`❌ Stop error: ${err.message}`, true);
    }

    document.getElementById("btn-submit").disabled = false;
    document.getElementById("btn-submit").innerText = "Start Process";
    fetchProjectHistory();
}

async function autoLoadLatestProject() {
    try {
        const res = await fetch(`${API_BASE}/api/projects/history/list`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.projects && data.projects.length > 0) {
            const latest = data.projects[0];
            AppState.activeProjectId = latest.project_id;
            AppState.sourceFileName = latest.source_file;
            AppState.currentBaseName = latest.source_file.substring(0, latest.source_file.lastIndexOf('.')) || latest.source_file;

            document.getElementById("project-name").value = latest.project_name;
            document.getElementById("target-language").value = latest.target_language || "Hindi";

            appendLog(`Session restored for project '${latest.project_name}'. Data loaded.`);
            updateStepProgress("completed_all");
            await loadProjectData();
        }
    } catch (err) {
        console.log("Auto load failed:", err);
    }
}

async function loadProjectData() {
    if (!AppState.activeProjectId) return;

    const origUrl = getMediaUrl(`${AppState.activeProjectId}/${AppState.sourceFileName}`);
    const dubUrl = getMediaUrl(`${AppState.activeProjectId}/FINAL_DUBBED_${AppState.currentBaseName}.wav`) + `?t=${Date.now()}`;

    wsFinalOrig.load(origUrl);
    wsFinalDub.load(dubUrl);

    const res = await fetch(`${API_BASE}/api/projects/${AppState.activeProjectId}/chunks`);
    if (!res.ok) return;
    const data = await res.json();

    AppState.chunksFolderName = data.chunks_folder;
    AppState.dubbedFolderName = data.dubbed_folder;

    const slicedSelect = document.getElementById("sliced-chunk-select");
    const dubbedSelect = document.getElementById("dubbed-chunk-select");

    slicedSelect.innerHTML = '<option value="">-- Select Sliced Chunk --</option>';
    dubbedSelect.innerHTML = '<option value="">-- Select Dubbed Chunk --</option>';

    if (data.chunks && data.chunks.length > 0) {
        data.chunks.forEach(c => {
            AppState.chunksMap[c.id] = c;
            slicedSelect.innerHTML += `<option value="${c.id}">${c.filename}</option>`;
            dubbedSelect.innerHTML += `<option value="${c.id}">${c.dubbed_filename}</option>`;
        });

        const firstChunk = data.chunks[0].id;
        slicedSelect.value = firstChunk;
        dubbedSelect.value = firstChunk;
        loadSlicedChunkAudio();
        loadDubbedChunkAudio();
    }

    document.getElementById("text-type-select").value = "";
    onTextTypeChange();
}

function onTextTypeChange() {
    const category = document.getElementById("text-type-select").value;
    const chunkSelect = document.getElementById("chunk-file-select");
    const editor = document.getElementById("chunk-text-editor");

    if (!category) {
        chunkSelect.innerHTML = '<option value="">-- Select Option (a) First --</option>';
        chunkSelect.disabled = true;
        editor.value = "";
        editor.disabled = true;
        AppState.activeChunkId = "";
        return;
    }

    chunkSelect.disabled = false;
    chunkSelect.innerHTML = '<option value="">-- Select Chunk File --</option>';

    Object.keys(AppState.chunksMap).forEach(chunkId => {
        const prefix = category === "nepali" ? "nepali_" : "hindi_";
        chunkSelect.innerHTML += `<option value="${chunkId}">${prefix}${chunkId}.txt</option>`;
    });

    editor.value = "";
    editor.disabled = true;
    AppState.activeChunkId = "";
}

async function onChunkFileSelect() {
    const chunkId = document.getElementById("chunk-file-select").value;
    const category = document.getElementById("text-type-select").value;
    const editor = document.getElementById("chunk-text-editor");

    if (!chunkId) {
        editor.value = "";
        editor.disabled = true;
        AppState.activeChunkId = "";
        return;
    }

    AppState.activeChunkId = chunkId;
    editor.disabled = false;

    const prefix = category === "nepali" ? "nepali_" : "hindi_";
    const fileName = `${prefix}${chunkId}.txt`;

    try {
        const res = await fetch(`${API_BASE}/api/projects/${AppState.activeProjectId}/text-files?category=${category}&file_name=${fileName}`);
        if (res.ok) {
            const data = await res.json();
            editor.value = data.text || "";
        }
    } catch (err) {
        appendLog(`❌ Error loading file '${fileName}': ${err.message}`, true);
    }
}

async function saveChunkText() {
    const category = document.getElementById("text-type-select").value;
    if (!AppState.activeProjectId || !category || !AppState.activeChunkId) {
        alert("Please select category (a) and chunk file (b) first.");
        return;
    }

    const text = document.getElementById("chunk-text-editor").value;
    const prefix = category === "nepali" ? "nepali_" : "hindi_";
    const fileName = `${prefix}${AppState.activeChunkId}.txt`;
    
    appendLog(`Saving text file '${fileName}'...`);

    try {
        const res = await fetch(`${API_BASE}/api/projects/${AppState.activeProjectId}/save-text`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                project_id: AppState.activeProjectId,
                category: category,
                chunk_id: AppState.activeChunkId,
                edited_text: text
            })
        });

        if (!res.ok) throw new Error("Save failed");
        appendLog(`✓ File '${fileName}' edited and replaced with original in ${category}_text folder!`);

    } catch (err) {
        appendLog(`❌ Save error: ${err.message}`, true);
    }
}

async function reRunTranslator() {
    if (!AppState.activeProjectId) {
        alert("No active project loaded.");
        return;
    }

    appendLog("Executing Re-run Translator for modified text chunks...");
    const eventSource = new EventSource(`${API_BASE}/api/projects/${AppState.activeProjectId}/run-step?script_name=translator.py`);

    eventSource.onmessage = async (event) => {
        appendLog(event.data);
        if (event.data.includes("[✓ EXECUTOR]")) {
            eventSource.close();
            appendLog("✓ Translator finished! All modified files replaced cleanly.");
            await loadProjectData();
        }
    };
}

async function reRunDubber() {
    if (!AppState.activeProjectId) {
        alert("No active project loaded.");
        return;
    }

    appendLog("Executing Re-run Dubber for modified translation text...");
    const eventSource = new EventSource(`${API_BASE}/api/projects/${AppState.activeProjectId}/run-step?script_name=dubber.py`);

    eventSource.onmessage = async (event) => {
        appendLog(event.data);
        if (event.data.includes("[✓ EXECUTOR]")) {
            eventSource.close();
            appendLog("✓ Dubber finished! All audio chunks re-dubbed successfully.");
            await loadProjectData();
        }
    };
}

async function runAuditorCheck() {
    if (!AppState.activeProjectId) {
        alert("Please create or load a project first.");
        return;
    }

    appendLog("🔍 Initiating Automated Quality & Chipmunk Audit Check (auditor.py)...");
    updateStepProgress("audit");

    const eventSource = new EventSource(`${API_BASE}/api/projects/${AppState.activeProjectId}/run-step?script_name=auditor.py`);

    eventSource.onmessage = (event) => {
        appendLog(event.data);
        if (event.data.includes("[✓ EXECUTOR]") || event.data.includes("AUDIT COMPLETE")) {
            eventSource.close();
            appendLog("✓ Quality Audit Check completed!");
        }
    };

    eventSource.onerror = () => {
        if (eventSource) eventSource.close();
    };
}

function loadSlicedChunkAudio() {
    const chunkId = document.getElementById("sliced-chunk-select").value;
    if (!chunkId || !AppState.chunksFolderName || !AppState.activeProjectId) return;
    document.getElementById("label-sliced-chunk").innerText = `${chunkId}.wav`;
    const origUrl = getMediaUrl(`${AppState.activeProjectId}/${AppState.chunksFolderName}/${chunkId}.wav`);
    wsChunkOrig.load(origUrl);
}

function loadDubbedChunkAudio() {
    const chunkId = document.getElementById("dubbed-chunk-select").value;
    if (!chunkId || !AppState.dubbedFolderName || !AppState.activeProjectId) return;
    document.getElementById("label-dubbed-chunk").innerText = `dub_${chunkId}.wav`;
    const dubUrl = getMediaUrl(`${AppState.activeProjectId}/${AppState.dubbedFolderName}/dub_${chunkId}.wav`) + `?t=${Date.now()}`;
    wsChunkDub.load(dubUrl);
}

function playPauseChunkOrig() { wsChunkOrig.playPause(); }
function playPauseChunkDub() { wsChunkDub.playPause(); }
function playPauseFinalOrig() { wsFinalOrig.playPause(); }
function playPauseFinalDub() { wsFinalDub.playPause(); }

async function proceedToFinalStitch() {
    if (!AppState.activeProjectId) {
        alert("No active project loaded to stitch.");
        return;
    }

    const btn = document.getElementById("btn-final-stitch");
    btn.disabled = true;
    btn.innerText = "⏳ Stitching & Combining Audio...";

    appendLog(`Combining all dubbed chunks & stitching master audio track...`);

    const eventSource = new EventSource(`${API_BASE}/api/projects/${AppState.activeProjectId}/stitch`);

    eventSource.onmessage = (event) => {
        appendLog(event.data);
        if (event.data.includes("[✓ EXECUTOR] SUCCESS: auditor.py completed!")) {
            eventSource.close();
            btn.disabled = false;
            btn.innerText = "Proceed to Stage 5 to Stitch";
            const dubUrl = getMediaUrl(`${AppState.activeProjectId}/FINAL_DUBBED_${AppState.currentBaseName}.wav`) + `?t=${Date.now()}`;
            wsFinalDub.load(dubUrl);
        }
    };
}

function runDubbingPipeline() {
    if (!AppState.activeProjectId) {
        alert("Please load or create a project first.");
        return;
    }
    
    appendLog(`🎙️ Launching Dubbing & Quality Audit Pipeline (Dubber ➔ Auditor)...`);
    updateStepProgress("dub");

    const eventSource = new EventSource(`${API_BASE}/api/projects/${encodeURIComponent(AppState.activeProjectId)}/run-dubbing-pipeline`);

    eventSource.onmessage = function(e) {
        appendLog(e.data);

        if (e.data.includes("dubber.py")) updateStepProgress("dub");
        if (e.data.includes("auditor.py")) {
            updateStepProgress("audit");
        }

        if (e.data.includes("[COMPLETE]")) {
            updateStepProgress("completed_all");
            eventSource.close();
            loadProjectData();
            appendLog("✅ Dubbing & Quality Audit Pipeline finished successfully!");
        }

        if (e.data.includes("[!] PIPELINE HALTED")) {
            eventSource.close();
            appendLog("❌ Dubbing pipeline halted due to error.", true);
        }
    };

    eventSource.onerror = function() {
        eventSource.close();
        appendLog("⚠️ Connection to dubbing stream closed.", true);
    };
}

function openStudioPage() {
    if (AppState.activeProjectId) {
        window.location.href = `studio.html?project_id=${AppState.activeProjectId}`;
    } else {
        alert("Please load or create a project first.");
    }
}

async function fetchProjectHistory() {
    try {
        const res = await fetch(`${API_BASE}/api/projects/history/list`);
        if (!res.ok) return;
        const data = await res.json();
        
        const historyContainer = document.getElementById("history-list");
        if (!data.projects || data.projects.length === 0) {
            historyContainer.innerHTML = "<div style='color: var(--text-muted); font-size:13px; grid-column: 1 / -1; text-align: center; padding: 20px;'>No past projects in history.</div>";
            return;
        }

        let html = "";
        data.projects.forEach(p => {
            const safeProjId = encodeURIComponent(p.project_id);
            const safeSourceFile = encodeURIComponent(p.source_file);
            const safeProjName = (p.project_name || "").replace(/'/g, "\\'").replace(/"/g, '&quot;');
            html += `
            <div class="project-card">
                <div>
                    <h4 style="color:#fff; font-size:14px; margin-bottom:4px;">${p.project_name}</h4>
                    <div style="font-size:12px; color:var(--text-muted);">
                        📄 File: ${p.source_file} | 🌐 Target: ${p.target_language}
                    </div>
                </div>
                <div style="display:flex; gap:8px;">
                    <button type="button" class="btn btn-blue" style="padding:5px 10px; font-size:12px;" onclick="loadProjectFromHistory('${safeProjId}', '${safeSourceFile}')">Load</button>
                    <button type="button" class="btn btn-red" style="padding:5px 10px; font-size:12px;" onclick="wipeOffProject('${safeProjId}', '${safeProjName}')">Wipe Off</button>
                </div>
            </div>`;
        });

        historyContainer.innerHTML = html;

    } catch (err) {
        console.log("Failed to fetch history:", err);
    }
}

async function wipeOffProject(encodedProjectId, projectName) {
    const projectId = decodeURIComponent(encodedProjectId);
    if (!confirm(`⚠️ ARE YOU SURE?\n\nDo you want to permanently wipe off project '${projectName}'?\n\nThis will completely delete the whole project folder, all audio chunks, transcriptions, translations, and dubbed files from disk.`)) {
        return;
    }

    try {
        appendLog(`🗑️ Wiping off project '${projectId}' from SSD...`);
        const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}`, { method: "DELETE" });
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to wipe off project from server");
        }

        if (AppState.activeProjectId === projectId) {
            AppState.activeProjectId = null;
            AppState.sourceFileName = null;
            AppState.chunksFolderName = null;
            AppState.dubbedFolderName = null;
            AppState.currentBaseName = null;
            AppState.timelineMetadata = {};
            localStorage.removeItem("active_project_id");
        }

        appendLog(`✓ Project '${projectId}' wiped off completely!`);
        alert(`✓ Project '${projectName}' wiped off successfully!`);
        await fetchProjectHistory();
        loadProjectData();

    } catch (err) {
        appendLog(`❌ Wipe off error: ${err.message}`, true);
        alert(`Failed to wipe off project: ${err.message}`);
    }
}

function loadProjectFromHistory(encodedId, encodedFile) {
    const id = decodeURIComponent(encodedId);
    const file = decodeURIComponent(encodedFile);
    AppState.activeProjectId = id;
    AppState.sourceFileName = file;
    AppState.currentBaseName = file.substring(0, file.lastIndexOf('.')) || file;
    
    appendLog(`📂 Session loaded for project '${id}'.`);
    loadProjectData();
    closeHistoryPanel();
}

function loadHistoryPanel() { fetchProjectHistory(); document.getElementById("history-modal").style.display = "block"; }
function closeHistoryPanel() { document.getElementById("history-modal").style.display = "none"; }

// ==========================================
// 📱 PWA Service Worker & Desktop Installation
// ==========================================
let deferredPwaPrompt = null;

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(reg => console.log('[PWA] ServiceWorker registered with scope:', reg.scope))
            .catch(err => console.log('[PWA] ServiceWorker registration failed:', err));
    });
}

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPwaPrompt = e;
    const installBtn = document.getElementById('pwa-install-btn');
    if (installBtn) {
        installBtn.style.display = 'inline-block';
    }
});

function triggerPwaInstall() {
    if (!deferredPwaPrompt) {
        alert("PWA installation is ready! In Chrome/Edge, click the install icon in the address bar (or Menu -> 'Install ULTIMATE DUB STUDIO'). In Safari, click Share -> 'Add to Dock'.");
        return;
    }
    deferredPwaPrompt.prompt();
    deferredPwaPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === 'accepted') {
            console.log('[PWA] User accepted the install prompt');
            const installBtn = document.getElementById('pwa-install-btn');
            if (installBtn) installBtn.style.display = 'none';
        }
        deferredPwaPrompt = null;
    });
}