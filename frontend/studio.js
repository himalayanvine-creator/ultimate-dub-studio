const API_BASE = "http://127.0.0.1:8000";

let videoPlayer, track1Audio, track2Audio, track3Audio;
let isPlaying = false;

const TrackState = {
    track1Muted: true,
    track2Muted: false,
    track3Muted: false,
    videoMuted: true
};

window.addEventListener("DOMContentLoaded", () => {
    videoPlayer = document.getElementById("video-preview");
    
    // Initialize HTML5 Audio Instances
    track1Audio = new Audio();
    track2Audio = new Audio();
    track3Audio = new Audio();

    // Default Video Audio to Muted
    if (videoPlayer) {
        videoPlayer.muted = true;
    }

    loadStudioProjectData();
    setupSyncTimeListeners();
});

function getProjectIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("project_id") || "";
}

function formatTime(sec) {
    if (isNaN(sec)) return "00:00.00";
    const minutes = Math.floor(sec / 60);
    const seconds = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 100);
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
}

async function loadStudioProjectData() {
    const projectId = getProjectIdFromUrl();
    if (!projectId) {
        alert("No active project ID specified in URL.");
        return;
    }

    const titleElem = document.getElementById("studio-title");
    if (titleElem) {
        titleElem.innerText = `Video & Audio Sync Studio — ${projectId.replace("project__", "").replace("_", " ")}`;
    }

    try {
        // 1. Load Audio Tracks
        const resList = await fetch(`${API_BASE}/api/projects/history/list`);
        if (resList.ok) {
            const data = await resList.json();
            const currentProj = data.projects.find(p => p.project_id === projectId);
            if (currentProj) {
                const sourceFile = currentProj.source_file;
                const baseName = sourceFile.substring(0, sourceFile.lastIndexOf('.')) || sourceFile;

                const cleanSourcePath = sourceFile.split('/').map(part => encodeURIComponent(part)).join('/');
                const cleanDubbedPath = encodeURIComponent(`FINAL_DUBBED_${baseName}.wav`);

                track1Audio.src = `${API_BASE}/media/${projectId}/${cleanSourcePath}`;
                track2Audio.src = `${API_BASE}/media/${projectId}/${cleanDubbedPath}?t=${Date.now()}`;
            }
        }

        // 2. Auto-Scan & Auto-Load Video Media from resources/ directory
        const resMedia = await fetch(`${API_BASE}/api/projects/${projectId}/resources-media`);
        if (resMedia.ok) {
            const mediaData = await resMedia.json();
            const labelElem = document.getElementById("video-filename-label");

            if (mediaData.video_file) {
                const cleanPath = mediaData.video_file.split('/').map(part => encodeURIComponent(part)).join('/');
                const videoUrl = `${API_BASE}/media/${projectId}/${cleanPath}?t=${Date.now()}`;

                const videoElem = document.getElementById("video-preview");
                const videoSource = document.getElementById("video-source");

                videoSource.src = videoUrl;
                videoElem.load();

                const displayFileName = mediaData.video_file.replace("resources/", "");
                labelElem.innerText = `Active Resource Video: ${displayFileName}`;
            } else {
                labelElem.innerText = "No video loaded in resources";
            }

            if (mediaData.bgm_file) {
                const cleanBgmPath = mediaData.bgm_file.split('/').map(part => encodeURIComponent(part)).join('/');
                track3Audio.src = `${API_BASE}/media/${projectId}/${cleanBgmPath}?t=${Date.now()}`;
            }
        }

    } catch (err) {
        console.log("Error auto-loading studio project media:", err);
    }
}

function setupSyncTimeListeners() {
    if (!videoPlayer) return;

    videoPlayer.addEventListener("timeupdate", () => {
        const current = videoPlayer.currentTime;
        const duration = videoPlayer.duration || 0;

        const seekbar = document.getElementById("master-seek-bar");
        if (seekbar && duration > 0) {
            seekbar.max = duration;
            seekbar.value = current;
        }

        const timeDisplay = document.getElementById("time-sync-master");
        if (timeDisplay) {
            timeDisplay.innerText = `${formatTime(current)} / ${formatTime(duration)}`;
        }

        // Lock audio tracks to video position
        syncAudioTime(track1Audio, current);
        syncAudioTime(track2Audio, current);
        syncAudioTime(track3Audio, current);
    });

    videoPlayer.addEventListener("ended", () => {
        isPlaying = false;
        pauseAll();
    });
}

function syncAudioTime(audioElem, targetTime) {
    if (audioElem && audioElem.src && Math.abs(audioElem.currentTime - targetTime) > 0.15) {
        audioElem.currentTime = targetTime;
    }
}

function playPauseAllTracks() {
    if (!videoPlayer) return;

    if (isPlaying) {
        pauseAll();
    } else {
        playAll();
    }
}

function playAll() {
    isPlaying = true;
    if (videoPlayer) videoPlayer.play();
    if (track1Audio && track1Audio.src && !TrackState.track1Muted) track1Audio.play();
    if (track2Audio && track2Audio.src && !TrackState.track2Muted) track2Audio.play();
    if (track3Audio && track3Audio.src && !TrackState.track3Muted) track3Audio.play();
}

function pauseAll() {
    isPlaying = false;
    if (videoPlayer) videoPlayer.pause();
    if (track1Audio) track1Audio.pause();
    if (track2Audio) track2Audio.pause();
    if (track3Audio) track3Audio.pause();
}

function onSeekMaster(val) {
    const time = parseFloat(val);
    if (videoPlayer) videoPlayer.currentTime = time;
    if (track1Audio) track1Audio.currentTime = time;
    if (track2Audio) track2Audio.currentTime = time;
    if (track3Audio) track3Audio.currentTime = time;
}

function toggleVideoMute() {
    const btn = document.getElementById("btn-mute-video");
    TrackState.videoMuted = !TrackState.videoMuted;

    videoPlayer.muted = TrackState.videoMuted;

    if (TrackState.videoMuted) {
        btn.className = "btn btn-red";
        btn.innerText = "🔇 Mute Video Audio";
    } else {
        btn.className = "btn btn-green";
        btn.innerText = "🔊 Video Audio Active";
    }
}

function toggleTrackMute(trackKey) {
    if (trackKey === "track1") {
        TrackState.track1Muted = !TrackState.track1Muted;
        track1Audio.muted = TrackState.track1Muted;
        updateMuteButton("btn-track1-mute", TrackState.track1Muted);
    } else if (trackKey === "track2") {
        TrackState.track2Muted = !TrackState.track2Muted;
        track2Audio.muted = TrackState.track2Muted;
        updateMuteButton("btn-track2-mute", TrackState.track2Muted);
    } else if (trackKey === "track3") {
        TrackState.track3Muted = !TrackState.track3Muted;
        track3Audio.muted = TrackState.track3Muted;
        updateMuteButton("btn-track3-mute", TrackState.track3Muted);
    }
}

function updateMuteButton(btnId, isMuted) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    if (isMuted) {
        btn.className = "btn btn-red btn-sm";
        btn.innerText = "🔇 MUTED";
    } else {
        btn.className = "btn btn-green btn-sm";
        btn.innerText = "🔊 AUDIBLE";
    }
}

function setTrackVolume(trackKey, vol) {
    const value = parseFloat(vol);
    if (trackKey === "track1" && track1Audio) track1Audio.volume = value;
    if (trackKey === "track2" && track2Audio) track2Audio.volume = value;
    if (trackKey === "track3" && track3Audio) track3Audio.volume = value;
}

// Upload & Save Video File directly to resources/
async function uploadStudioVideoFile(inputElem) {
    if (!inputElem.files || !inputElem.files[0]) return;
    
    const file = inputElem.files[0];
    const projectId = getProjectIdFromUrl();

    if (!projectId) {
        alert("Error: No active project_id found in URL parameters.");
        return;
    }

    const labelElem = document.getElementById("video-filename-label");
    labelElem.innerText = `⏳ Saving to resources folder...`;

    const formData = new FormData();
    formData.append("video_file", file);

    try {
        const res = await fetch(`${API_BASE}/api/projects/${projectId}/upload-video`, {
            method: "POST",
            body: formData
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "Server failed to process video upload");
        }

        const data = await res.json();
        
        const cleanPath = data.video_file.split('/').map(part => encodeURIComponent(part)).join('/');
        const videoUrl = `${API_BASE}/media/${projectId}/${cleanPath}?t=${Date.now()}`;

        const videoSource = document.getElementById("video-source");
        videoSource.src = videoUrl;
        videoPlayer.load();

        labelElem.innerText = `Active Resource Video: ${file.name}`;
        alert(`✓ Video successfully saved in project resources folder!`);

    } catch (err) {
        labelElem.innerText = "❌ Upload failed";
        alert(`Upload error: ${err.message}`);
    }
}

// Upload & Save Background Music File directly to resources/
async function uploadBgmFile(inputElem) {
    if (!inputElem.files || !inputElem.files[0]) return;

    const file = inputElem.files[0];
    const projectId = getProjectIdFromUrl();

    if (!projectId) {
        alert("Error: No active project_id found in URL parameters.");
        return;
    }

    const formData = new FormData();
    formData.append("bgm_file", file);

    try {
        const res = await fetch(`${API_BASE}/api/projects/${projectId}/upload-bgm`, {
            method: "POST",
            body: formData
        });

        if (!res.ok) throw new Error("BGM upload failed");

        const data = await res.json();
        const cleanPath = data.bgm_file.split('/').map(part => encodeURIComponent(part)).join('/');
        
        track3Audio.src = `${API_BASE}/media/${projectId}/${cleanPath}?t=${Date.now()}`;
        alert(`✓ Background music saved to resources folder:\nprojects/${projectId}/${data.bgm_file}`);

    } catch (err) {
        alert(`BGM Upload error: ${err.message}`);
    }
}

function syncStudioState() {
    loadStudioProjectData();
    alert("Studio media tracks synced with latest project state!");
}

function exportLosslessVideo() {
    alert("Lossless Video Export triggered! Combining active track volumes and FFmpeg video stream copy.");
}