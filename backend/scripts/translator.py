import os
import sys
import time
from google import genai
from google.genai import types

# Initialize Vertex AI Client ($300 GCP Credit)
GCP_PROJECT_ID = "project-fa3866df-86dd-40ea-be7"
GCP_LOCATION = "us-central1"

vertex_client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT_ID,
    location=GCP_LOCATION
)

nepali_folders = [f for f in os.listdir(".") if os.path.isdir(f) and f.startswith("nepali_text_")]
if not nepali_folders:
    print("[!] ERROR: No Nepali transcript folder found in workspace.")
    sys.exit(1)

source_folder = nepali_folders[0]
project_suffix = source_folder.replace("nepali_text_", "")
target_folder = f"hindi_text_{project_suffix}"
os.makedirs(target_folder, exist_ok=True)

nepali_files = sorted([f for f in os.listdir(source_folder) if f.endswith(".txt")])

print(f"[Translator Pipeline] Source: '{source_folder}/'")
print(f"[Translator Pipeline] Target: '{target_folder}/'\n")

completed_count = 0
updated_count = 0
skipped_count = 0

for file_name in nepali_files:
    chunk_id = file_name.replace("nepali_", "").replace(".txt", "")
    source_path = os.path.join(source_folder, file_name)
    target_path = os.path.join(target_folder, f"hindi_{chunk_id}.txt")

    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        if os.path.getmtime(target_path) >= os.path.getmtime(source_path):
            print(f"[SKIP] {chunk_id} unchanged. Skipping...")
            skipped_count += 1
            continue
        else:
            print(f"[UPDATE] Nepali transcript for {chunk_id} modified. Re-translating...")
            updated_count += 1

    with open(source_path, "r", encoding="utf-8") as f:
        nepali_text = f.read().strip()

    if not nepali_text:
        with open(target_path, "w", encoding="utf-8") as tf:
            tf.write("")
        continue

    print(f"--- Translating {chunk_id} ---")
    print(f"  Nepali: \"{nepali_text}\"")

    try:
        chunks_folders = [f for f in os.listdir(".") if os.path.isdir(f) and f.endswith("_chunks")]
        audio_part = None
        if chunks_folders:
            audio_file = os.path.join(chunks_folders[0], f"{chunk_id}.wav")
            if os.path.exists(audio_file):
                with open(audio_file, "rb") as af:
                    audio_bytes = af.read()
                audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")

        prompt = (
            f"Translate this Nepali speech chunk into natural professional Hindi text: '{nepali_text}'. "
            "Ignore conversational filler words like 'hai', 'haina'. Localize technical terms cleanly. "
            "Return ONLY the plain Hindi text string."
        )

        contents = [prompt, audio_part] if audio_part else prompt

        response = vertex_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents
        )

        hindi_text = response.text.strip().replace('"', '')
        print(f"  Hindi:  \"{hindi_text}\"")

        with open(target_path, "w", encoding="utf-8") as tf:
            tf.write(hindi_text)

        print(f"[✓ REPLACED] hindi_{chunk_id}.txt updated successfully in '{target_folder}/'!")
        completed_count += 1
        time.sleep(0.3)

    except Exception as e:
        print(f"[!] Translation error for {chunk_id}: {e}")

print("\n" + "=" * 60)
print(f"TRANSLATION SUMMARY:")
print(f"  - Total chunks processed: {len(nepali_files)}")
print(f"  - Skipped (Unchanged): {skipped_count}")
print(f"  - Newly translated / Updated: {completed_count}")
print("============================================================")