import os
import sys
import json
import shutil
from pathlib import Path
from pydub import AudioSegment

# Auto-discover active project folders
media_files = [
    f for f in os.listdir(".") 
    if f.endswith((".wav", ".mp3", ".m4a", ".mp4", ".mkv", ".mov", ".webm", ".m4v")) 
    and not f.startswith("FINAL_DUBBED_") 
    and not f.startswith("EXPORTED_")
]
if not media_files:
    print("[!] ERROR: No original source media file found.")
    sys.exit(1)

source_file = media_files[0]
base_name = source_file.rsplit(".", 1)[0]

chunks_folders = [f for f in os.listdir(".") if os.path.isdir(f) and f.endswith("_chunks")]
dubbed_folders = [f for f in os.listdir(".") if os.path.isdir(f) and f.startswith("final_dubbed_")]

if not chunks_folders or not dubbed_folders:
    print("[!] ERROR: Chunks or Dubbed folders missing.")
    sys.exit(1)

chunks_dir = chunks_folders[0]
dubbed_dir = dubbed_folders[0]
output_file = f"FINAL_DUBBED_{base_name}.wav"

# Load Master Original Audio to establish exact timeline canvas
print(f"[Stitcher] Loading master source audio: '{source_file}'...")
master_orig = AudioSegment.from_file(source_file)
total_ms = len(master_orig)

print(f"[Stitcher] Master timeline duration: {total_ms / 1000.0:.3f} seconds ({total_ms} ms)")
print(f"[Stitcher] Building time-aligned silent master canvas...")
master_dubbed = AudioSegment.silent(duration=total_ms)

# Check for timeline metadata JSON from slice.py
metadata_file = os.path.join(chunks_dir, "timeline.json")
timeline_map = {}

if os.path.exists(metadata_file):
    with open(metadata_file, "r", encoding="utf-8") as f:
        timeline_map = json.load(f)

chunk_files = sorted([f for f in os.listdir(chunks_dir) if f.startswith("chunk_") and f.endswith(".wav")])

def fit_audio_to_window(dub_audio, max_allowed_ms):
    dub_len_ms = len(dub_audio)
    if dub_len_ms <= max_allowed_ms or max_allowed_ms <= 0:
        return dub_audio, 1.0
    
    speed_factor = dub_len_ms / float(max_allowed_ms)
    
    if speed_factor <= 1.35:
        altered = dub_audio._spawn(
            dub_audio.raw_data,
            overrides={"frame_rate": int(dub_audio.frame_rate * speed_factor)}
        )
        return altered.set_frame_rate(dub_audio.frame_rate), speed_factor
    else:
        trimmed = dub_audio[:max_allowed_ms]
        if len(trimmed) > 100:
            trimmed = trimmed.fade_out(50)
        return trimmed, speed_factor

print("\n" + "="*80)
print(f"{'CHUNK ID':<12} | {'ORIG TIMELINE':<18} | {'MUTE GAP':<10} | {'DUB DURATION':<14} | {'STATUS':<20}")
print("="*80)

total_speech_ms = 0
total_mute_ms = 0
prev_end_ms = 0

for i, c_file in enumerate(chunk_files):
    chunk_id = c_file.replace(".wav", "")
    orig_chunk_path = os.path.join(chunks_dir, c_file)
    dub_chunk_path = os.path.join(dubbed_dir, f"dub_{chunk_id}.wav")

    orig_chunk = AudioSegment.from_file(orig_chunk_path)
    orig_chunk_len_ms = len(orig_chunk)

    if chunk_id in timeline_map:
        start_ms = int(timeline_map[chunk_id]["start_sec"] * 1000)
        end_ms = int(timeline_map[chunk_id]["end_sec"] * 1000)
    else:
        start_ms = prev_end_ms
        end_ms = start_ms + orig_chunk_len_ms

    # Mute/Silence space before this chunk
    mute_space_ms = max(0, start_ms - prev_end_ms)
    total_mute_ms += mute_space_ms

    # Calculate available window until next chunk start or end of audio
    if i < len(chunk_files) - 1:
        next_c_file = chunk_files[i + 1]
        next_id = next_c_file.replace(".wav", "")
        if next_id in timeline_map:
            next_start_ms = int(timeline_map[next_id]["start_sec"] * 1000)
        else:
            next_start_ms = end_ms
    else:
        next_start_ms = total_ms

    max_window_ms = max(orig_chunk_len_ms, next_start_ms - start_ms)

    if os.path.exists(dub_chunk_path) and os.path.getsize(dub_chunk_path) > 0:
        dub_chunk = AudioSegment.from_file(dub_chunk_path)
        raw_dub_len_ms = len(dub_chunk)
        
        fitted_dub_chunk, speed_factor = fit_audio_to_window(dub_chunk, max_window_ms)
        final_dub_len_ms = len(fitted_dub_chunk)
        
        master_dubbed = master_dubbed.overlay(fitted_dub_chunk, position=start_ms)
        total_speech_ms += final_dub_len_ms
        
        if speed_factor > 1.0:
            status_str = f"Fit ({speed_factor:.2f}x speed)"
        else:
            status_str = "Stitched Perfectly"
        
        time_str = f"{start_ms/1000.0:.2f}s - {end_ms/1000.0:.2f}s"
        mute_str = f"{mute_space_ms}ms"
        dub_str = f"{raw_dub_len_ms}ms"
        print(f"{chunk_id:<12} | {time_str:<18} | {mute_str:<10} | {dub_str:<14} | {status_str:<20}")
    else:
        # Fallback to original audio chunk if dubbed version missing
        master_dubbed = master_dubbed.overlay(orig_chunk, position=start_ms)
        total_speech_ms += orig_chunk_len_ms
        time_str = f"{start_ms/1000.0:.2f}s - {end_ms/1000.0:.2f}s"
        mute_str = f"{mute_space_ms}ms"
        print(f"{chunk_id:<12} | {time_str:<18} | {mute_str:<10} | {'ORIG FALLBACK':<14} | {'Preserved Original':<20}")

    prev_end_ms = end_ms

# Final Mute space trailing at the end of track
trailing_mute_ms = max(0, total_ms - prev_end_ms)
total_mute_ms += trailing_mute_ms

# Guarantee exact timeline length matching master original
if len(master_dubbed) < total_ms:
    padding = AudioSegment.silent(duration=total_ms - len(master_dubbed))
    master_dubbed += padding
elif len(master_dubbed) > total_ms:
    master_dubbed = master_dubbed[:total_ms]

master_dubbed.export(output_file, format="wav")

print("="*80)
print(f"\n============================================================")
print(f"STITCHING ANALYSIS & MASTER ASSEMBLY COMPLETE")
print(f"  - Original Track Duration : {total_ms / 1000.0:.3f}s ({total_ms} ms)")
print(f"  - Final Track Duration    : {len(master_dubbed) / 1000.0:.3f}s ({len(master_dubbed)} ms)")
print(f"  - Total Speech Chunks     : {len(chunk_files)} segments ({total_speech_ms / 1000.0:.2f}s)")
print(f"  - Total Mute/Silence Gaps : {total_mute_ms / 1000.0:.2f}s preserved")
print(f"  - Master Output File      : '{output_file}'")
print(f"============================================================")