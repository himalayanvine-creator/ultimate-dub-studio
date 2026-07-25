import sys

# Try importing audioop (which is provided by audioop-lts on Python 3.13+) before importing pydub
try:
    import audioop
except ImportError:
    print("[!] ERROR: The 'audioop' module is required but missing.")
    print("    Python 3.13+ has removed 'audioop' from the standard library.")
    print("    Please install 'audioop-lts' to resolve this:")
    print("        pip install audioop-lts")
    sys.exit(1)

import os
import shutil
from datetime import datetime
from pydub import AudioSegment

print("=" * 60)
print("       AUTOMATED AUDIO QUALITY & CHIPMUNK AUDITOR       ")
print("=" * 60)

# 1. Auto-discover active final_dubbed folder
dubbed_folder = None
for item in os.listdir("."):
    if os.path.isdir(item) and item.startswith("final_dubbed_"):
        dubbed_folder = item
        break

if not dubbed_folder:
    print("[!] ERROR: No 'final_dubbed_*' directory found in this project folder.")
    sys.exit(1)

project_base = dubbed_folder.replace("final_dubbed_", "")
raw_tts_folder = f"temp_raw_tts_{project_base}"
log_filename = f"scrambled_audio_log_{project_base}.txt"

print(f"Project Target : '{project_base}'")
print(f"Dubbed Folder  : '{dubbed_folder}/'")
print(f"Log File Output: '{log_filename}'\n")

dub_files = sorted(
    [f for f in os.listdir(dubbed_folder) if f.startswith("dub_") and f.endswith(".wav")]
)

if not dub_files:
    print("[!] ERROR: No 'dub_*.wav' files found to audit.")
    sys.exit(1)

scrambled_flagged = []
clean_count = 0

def inspect_waveform(dub_path, chunk_id):
    """
    Analyzes wave data to detect:
    1. Chipmunk / Hyper-speed time compression (RED FLAG when speed_ratio > 2.0x)
    2. Zero RMS energy / dead silence glitches
    3. Unplayable 0:00 corrupted headers
    4. Severe digital clipping saturation
    """
    try:
        audio = AudioSegment.from_file(dub_path)
        duration_ms = len(audio)

        # CHECK 1: Corrupted / 0:00 Header Duration Glitch
        if duration_ms < 100:
            return True, "[RED FLAG 🚨] Unplayable / Corrupted Header Duration (0:00 bug)"

        # CHECK 2: Dead Silence / Zero Energy Fail
        if audio.rms < 5:
            return True, "[RED FLAG 🚨] Dead Audio Output (Zero RMS Energy)"

        # CHECK 3: Chipmunk Speed-Compression Ratio Check (> 2.0x)
        raw_file = os.path.join(raw_tts_folder, f"raw_tts_{chunk_id}.wav")
        if os.path.exists(raw_file):
            raw_audio = AudioSegment.from_file(raw_file)
            raw_duration = len(raw_audio)

            if duration_ms > 0:
                speed_ratio = raw_duration / duration_ms
                if speed_ratio > 2.0:
                    return True, f"[RED FLAG 🚨] Severe Chipmunk Distortion ({speed_ratio:.2f}x speed-up)"
                elif speed_ratio > 1.25:
                    return True, f"[WARNING ⚠️] Moderate Speed Compression ({speed_ratio:.2f}x speed-up)"

        # CHECK 4: Hard Digital Clipping Distortion
        raw_samples = audio.get_array_of_samples()
        if len(raw_samples) == 0:
            return True, "[RED FLAG 🚨] Empty Audio Sample Buffer"

        max_possible = audio.max_possible_amplitude
        clipped_samples = sum(1 for s in raw_samples if abs(s) >= max_possible * 0.98)
        clip_ratio = clipped_samples / len(raw_samples)

        if clip_ratio > 0.12:
            return True, f"[RED FLAG 🚨] Severe Amplitude Clipping ({clip_ratio * 100:.1f}% distorted)"

        return False, "Clean"

    except Exception as e:
        return True, f"[RED FLAG 🚨] File Decode Error ({str(e)})"


# Execute Scan
print(f"Scanning {len(dub_files)} audio chunks...\n")

for dub_file in dub_files:
    file_path = os.path.join(dubbed_folder, dub_file)
    chunk_id = dub_file.replace("dub_", "").replace(".wav", "")

    is_bad, reason = inspect_waveform(file_path, chunk_id)

    if is_bad:
        # Prints RED FLAG directly to terminal console
        print(f"[❌ FLAGGED] {dub_file} -> {reason}")
        scrambled_flagged.append((dub_file, reason))
    else:
        print(f"[✓ OK] {dub_file}")
        clean_count += 1

# Generate Audit Report File
with open(log_filename, "w", encoding="utf-8") as f:
    f.write(f"===========================================================\n")
    f.write(f"     AUDIO AUDIT REPORT: {project_base}\n")
    f.write(f"     Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"===========================================================\n\n")
    f.write(f"Total Chunks Scanned : {len(dub_files)}\n")
    f.write(f"Clean Waveforms      : {clean_count}\n")
    f.write(f"Flagged Segments     : {len(scrambled_flagged)}\n\n")

    if scrambled_flagged:
        f.write("--- FLAGGED CHUNKS LIST (RED FLAGS MUST BE FIXED MANUALLY) ---\n")
        for file_name, issue in scrambled_flagged:
            f.write(f"• File: {file_name:<18} | Issue: {issue}\n")
    else:
        f.write("🎉 Perfect Project! No scrambled or chipmunk (>2x) waveforms detected.\n")

print("\n" + "=" * 60)
print(f"AUDIT COMPLETE!")
print(f"Passed: {clean_count}/{len(dub_files)}")
print(f"Flagged: {len(scrambled_flagged)} issue(s)")
print(f"Report saved to: '{log_filename}'")
print("=" * 60)