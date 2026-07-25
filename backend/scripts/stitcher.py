import os
import sys
import json
import shutil
from pathlib import Path
from pydub import AudioSegment

# Auto-discover active project folders
media_files = [f for f in os.listdir(".") if f.endswith((".wav", ".mp3", ".m4a")) and not f.startswith("FINAL_DUBBED_")]
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

print(f"[Stitcher] Building time-aligned silent canvas ({total_ms} ms)...")
# Start with complete silence matching master duration
master_dubbed = AudioSegment.silent(duration=total_ms)

# Check for timeline metadata JSON from slice.py
metadata_file = os.path.join(chunks_dir, "timeline.json")
timeline_map = {}

if os.path.exists(metadata_file):
    with open(metadata_file, "r", encoding="utf-8") as f:
        timeline_map = json.load(f)

chunk_files = sorted([f for f in os.listdir(chunks_dir) if f.startswith("chunk_") and f.endswith(".wav")])

current_pos_ms = 0

for c_file in chunk_files:
    chunk_id = c_file.replace(".wav", "")
    orig_chunk_path = os.path.join(chunks_dir, c_file)
    dub_chunk_path = os.path.join(dubbed_dir, f"dub_{chunk_id}.wav")

    orig_chunk = AudioSegment.from_file(orig_chunk_path)
    chunk_len_ms = len(orig_chunk)

    # Determine exact start time for this chunk
    if chunk_id in timeline_map:
        start_ms = int(timeline_map[chunk_id]["start_sec"] * 1000)
    else:
        # Fallback to sequential position matching original chunk duration
        start_ms = current_pos_ms

    if os.path.exists(dub_chunk_path) and os.path.getsize(dub_chunk_path) > 0:
        dub_chunk = AudioSegment.from_file(dub_chunk_path)
        # Overlay dubbed chunk onto the master timeline canvas at its exact timestamp
        master_dubbed = master_dubbed.overlay(dub_chunk, position=start_ms)
        print(f"  [✓ STITCHED] {chunk_id} placed at {start_ms / 1000:.2f}s")
    else:
        print(f"  [!] Warning: {chunk_id} dubbed file missing. Preserving original gap/silence.")

    current_pos_ms = start_ms + chunk_len_ms

# Ensure final output exactly equals original master length
if len(master_dubbed) < total_ms:
    padding = AudioSegment.silent(duration=total_ms - len(master_dubbed))
    master_dubbed += padding
elif len(master_dubbed) > total_ms:
    master_dubbed = master_dubbed[:total_ms]

master_dubbed.export(output_file, format="wav")

print(f"\n============================================================")
print(f"SUCCESS: Time-aligned master dubbed track exported!")
print(f"Output File: '{output_file}' ({len(master_dubbed)} ms / {total_ms} ms)")
print(f"============================================================")