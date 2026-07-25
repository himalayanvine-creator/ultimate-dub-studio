import os
import sys
import time
from pathlib import Path
from google import genai
from google.genai import types

# Explicitly route to Google Cloud Console Vertex AI ($300 GCP Credit)
GCP_PROJECT_ID = "project-fa3866df-86dd-40ea-be7"
GCP_LOCATION = "us-central1"

vertex_client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT_ID,
    location=GCP_LOCATION
)

# Discover project chunks folder dynamically
chunks_folders = [f for f in os.listdir(".") if os.path.isdir(f) and f.endswith("_chunks") and f != "final_dubbed_chunks"]

if not chunks_folders:
    print("[!] ERROR: No active project chunks folder found.")
    sys.exit(1)

chunks_dir = chunks_folders[0]
project_base = chunks_dir.replace("_chunks", "")
output_dir = f"nepali_text_{project_base}"
os.makedirs(output_dir, exist_ok=True)

wav_files = sorted([f for f in os.listdir(chunks_dir) if f.startswith("chunk_") and f.endswith(".wav")])

print(f"[Text Grabber] Processing {len(wav_files)} chunks from '{chunks_dir}/' via Vertex AI...")
print(f"[Text Grabber] Saving transcriptions to '{output_dir}/'\n")

success_count = 0
skipped_count = 0

for wav_file in wav_files:
    chunk_id = wav_file.replace(".wav", "")
    wav_path = os.path.join(chunks_dir, wav_file)
    txt_path = os.path.join(output_dir, f"nepali_{chunk_id}.txt")

    # Resiliency Check: Skip if already transcribed and non-empty
    if os.path.exists(txt_path) and os.path.getsize(txt_path) > 0:
        print(f"[SKIP] {chunk_id} transcript exists. Skipping...")
        skipped_count += 1
        continue

    print(f"--- Transcribing {chunk_id} ---")
    
    try:
        with open(wav_path, "rb") as f:
            audio_bytes = f.read()

        audio_part = types.Part.from_bytes(
            data=audio_bytes,
            mime_type="audio/wav"
        )

        prompt = (
            "Transcribe the spoken language in this audio segment accurately. "
            "Return ONLY the plain transcript string. Do not add quotes or markdown."
        )

        response = vertex_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, audio_part]
        )

        transcript = response.text.strip().replace('"', '')
        print(f"  Transcript: \"{transcript}\"")

        with open(txt_path, "w", encoding="utf-8") as tf:
            tf.write(transcript)

        print(f"[✓ TRANSCRIBED] Saved nepali_{chunk_id}.txt")
        success_count += 1
        time.sleep(0.3)

    except Exception as e:
        print(f"[!] Transcription failed for {chunk_id}: {e}")

print("\n" + "=" * 60)
print(f"TRANSCRIPTION SUMMARY:")
print(f"  - Total chunks: {len(wav_files)}")
print(f"  - Skipped (Already exists): {skipped_count}")
print(f"  - Newly Transcribed: {success_count}")
print("============================================================")