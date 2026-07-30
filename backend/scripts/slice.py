import os
import sys
import json
import ssl
import urllib.request
import numpy as np
import torch
import shutil
from pathlib import Path
from pydub import AudioSegment

# Bypass macOS Python SSL Certificate Verification Error
ssl._create_default_https_context = ssl._create_unverified_context
torch.hub._validate_not_a_forked_repo = lambda *args, **kwargs: True

if not shutil.which("ffmpeg"):
    print("[!] ERROR: 'ffmpeg' is missing from your system PATH.")
    sys.exit(1)

# Find active original media file in workspace
media_files = [
    f for f in os.listdir(".") 
    if f.endswith((".wav", ".mp3", ".m4a", ".mp4", ".mkv", ".mov", ".webm", ".m4v")) 
    and not f.startswith("FINAL_DUBBED_") 
    and not f.startswith("EXPORTED_")
]

if not media_files:
    print("[!] ERROR: No source audio/video file found in workspace.")
    sys.exit(1)

source_file = media_files[0]
base_name = source_file.rsplit('.', 1)[0]
chunks_dir = f"{base_name}_chunks"
os.makedirs(chunks_dir, exist_ok=True)

timeline_json_path = os.path.join(chunks_dir, "timeline.json")

print(f"[Silero VAD] Loading source media: '{source_file}'...")
audio = AudioSegment.from_file(source_file)
total_duration_sec = len(audio) / 1000.0

# Prepare 16kHz mono audio array for Silero VAD processing
audio_16k = audio.set_frame_rate(16000).set_channels(1)
samples = np.array(audio_16k.get_array_of_samples(), dtype=np.float32) / 32768.0
wav_tensor = torch.from_numpy(samples)

print("[Silero VAD] Initializing PyTorch Voice Activity Detection model...")

def find_optimal_split(audio_segment, start_sec, end_sec, max_chunk_sec=5.0, min_chunk_sec=2.5):
    """
    Finds the optimal quietest point to split a long audio segment.
    Scans the window from start_sec + min_chunk_sec to start_sec + max_chunk_sec
    and returns the second with the minimum RMS energy.
    """
    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000)
    max_chunk_ms = int(max_chunk_sec * 1000)
    min_chunk_ms = int(min_chunk_sec * 1000)
    
    search_start = start_ms + min_chunk_ms
    search_end = min(start_ms + max_chunk_ms, end_ms - 200)
    
    if search_start >= search_end:
        return start_sec + (end_sec - start_sec) / 2.0
        
    best_split_ms = search_start
    min_rms = float('inf')
    step_ms = 30
    window_ms = 80
    
    for ms in range(search_start, search_end, step_ms):
        chunk = audio_segment[ms:ms+window_ms]
        rms = chunk.rms
        if rms < min_rms:
            min_rms = rms
            best_split_ms = ms + (window_ms // 2)
            
    return best_split_ms / 1000.0

try:
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,
        onnx=False,
        trust_repo=True
    )
    (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils

    print("[Silero VAD] Detecting speech segments in timeline (min silence gap: 120ms)...")
    speech_timestamps = get_speech_timestamps(
        wav_tensor,
        model,
        sampling_rate=16000,
        threshold=0.5,
        min_speech_duration_ms=200,
        min_silence_duration_ms=120  # Split on any silence gap >= 120ms (100-150ms window)
    )
except Exception as e:
    print(f"[!] Silero VAD processing failed: {e}. Falling back to 5s slice generator...")
    speech_timestamps = []

if not speech_timestamps:
    print("[!] Fallback Mode: Slicing audio into 5-second uniform chunks...")
    speech_timestamps = []
    curr_sample = 0
    max_sample = int(total_duration_sec * 16000)
    step = 5 * 16000
    while curr_sample < max_sample:
        speech_timestamps.append({'start': curr_sample, 'end': min(curr_sample + step, max_sample)})
        curr_sample += step

# Refine timestamps to enforce max chunk length (5.0 seconds max)
MAX_CHUNK_SEC = 5.0
final_segments = []

for ts in speech_timestamps:
    start_sec = ts['start'] / 16000.0
    end_sec = ts['end'] / 16000.0
    seg_dur = end_sec - start_sec

    if seg_dur <= MAX_CHUNK_SEC:
        final_segments.append({'start_sec': round(start_sec, 3), 'end_sec': round(end_sec, 3)})
    else:
        sub_curr = start_sec
        while (end_sec - sub_curr) > MAX_CHUNK_SEC:
            split_sec = find_optimal_split(audio, sub_curr, end_sec, max_chunk_sec=MAX_CHUNK_SEC, min_chunk_sec=2.5)
            final_segments.append({'start_sec': round(sub_curr, 3), 'end_sec': round(split_sec, 3)})
            sub_curr = split_sec
        final_segments.append({'start_sec': round(sub_curr, 3), 'end_sec': round(end_sec, 3)})

print(f"[Silero VAD] Extracted {len(final_segments)} continuous speech chunk segments (Max duration <= 5.0s).")

# Clean existing chunk files to avoid leftover stale chunks
for existing_file in os.listdir(chunks_dir):
    if existing_file.startswith("chunk_") and existing_file.endswith(".wav"):
        try:
            os.remove(os.path.join(chunks_dir, existing_file))
        except:
            pass

timeline_metadata = {}

for idx, seg in enumerate(final_segments, start=1):
    chunk_id = f"chunk_{idx:03d}"
    start_ms = int(seg['start_sec'] * 1000)
    end_ms = int(seg['end_sec'] * 1000)

    chunk_audio = audio[start_ms:end_ms]
    out_file = os.path.join(chunks_dir, f"{chunk_id}.wav")
    chunk_audio.export(out_file, format="wav")

    timeline_metadata[chunk_id] = {
        "filename": f"{chunk_id}.wav",
        "start_sec": seg['start_sec'],
        "end_sec": seg['end_sec'],
        "duration_sec": round(seg['end_sec'] - seg['start_sec'], 3)
    }
    print(f"  [✓ SLICED] {chunk_id}.wav ({seg['start_sec']:.2f}s - {seg['end_sec']:.2f}s | {seg['end_sec'] - seg['start_sec']:.2f}s duration)")

# Save timeline metadata JSON for stitcher.py and backend_server.py
with open(timeline_json_path, "w", encoding="utf-8") as f:
    json.dump(timeline_metadata, f, indent=2)

print(f"\n============================================================")
print(f"SLICING COMPLETE:")
print(f"  - Total continuous chunks saved: {len(timeline_metadata)}")
print(f"  - Silence Gap Split Threshold   : 120ms")
print(f"  - Max Chunk Duration            : 5.0s")
print(f"  - Target Folder                 : '{chunks_dir}/'")
print(f"  - Metadata Log                  : '{timeline_json_path}'")
print(f"============================================================")