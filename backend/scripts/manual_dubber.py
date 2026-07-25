import os
import sys
import wave
import shutil
import subprocess
from google import genai
from google.genai import types
from pydub import AudioSegment

def find_speech_boundaries(audio, silence_threshold_dbfs=-45.0, chunk_size_ms=10):
    """
    Finds the start and end milliseconds of speech in an AudioSegment.
    """
    duration_ms = len(audio)
    start_ms = 0
    end_ms = duration_ms
    
    # Find start of speech
    for ms in range(0, duration_ms, chunk_size_ms):
        chunk = audio[ms:ms+chunk_size_ms]
        if chunk.dbfs > silence_threshold_dbfs:
            start_ms = ms
            break
            
    # Find end of speech
    for ms in range(duration_ms, 0, -chunk_size_ms):
        chunk = audio[ms-chunk_size_ms:ms]
        if chunk.dbfs > silence_threshold_dbfs:
            end_ms = ms
            break
            
    # Safety checks
    if start_ms >= end_ms or (end_ms - start_ms) < 100:
        return 0, duration_ms
        
    return start_ms, end_ms

def align_and_export_audio(original_file, raw_tts_file, final_file):
    orig_audio = AudioSegment.from_file(original_file)
    tts_audio = AudioSegment.from_file(raw_tts_file)
    
    orig_duration = len(orig_audio)
    
    # 1. Detect speech boundaries in original audio
    orig_start, orig_end = find_speech_boundaries(orig_audio, silence_threshold_dbfs=-45.0)
    orig_speech_dur = orig_end - orig_start
    
    # 2. Detect speech boundaries in TTS audio
    tts_start, tts_end = find_speech_boundaries(tts_audio, silence_threshold_dbfs=-45.0)
    tts_speech_audio = tts_audio[tts_start:tts_end]
    tts_speech_dur = len(tts_speech_audio)
    
    # 3. Determine target speech duration and speed scale
    speed_ratio = tts_speech_dur / orig_speech_dur if orig_speech_dur > 0 else 1.0
    
    # If speed ratio is very close to 1.0, we can skip speed scaling
    if 0.95 <= speed_ratio <= 1.05 or tts_speech_dur < 100:
        scaled_speech = tts_speech_audio
    else:
        # Scale speed using FFmpeg
        temp_speech_in = raw_tts_file + ".speech_in.wav"
        temp_speech_out = raw_tts_file + ".speech_out.wav"
        tts_speech_audio.export(temp_speech_in, format="wav")
        
        # Build chained atempo filters for ratios outside [0.5, 2.0]
        filters = []
        temp_ratio = speed_ratio
        while temp_ratio > 2.0:
            filters.append("atempo=2.0")
            temp_ratio /= 2.0
        while temp_ratio < 0.5:
            filters.append("atempo=0.5")
            temp_ratio /= 0.5
        if temp_ratio != 1.0:
            filters.append(f"atempo={temp_ratio:.4f}")
            
        filter_str = ",".join(filters)
        
        subprocess.run([
            "ffmpeg", "-y", "-i", temp_speech_in,
            "-filter:a", filter_str,
            temp_speech_out
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(temp_speech_out):
            scaled_speech = AudioSegment.from_file(temp_speech_out)
            try:
                os.remove(temp_speech_in)
                os.remove(temp_speech_out)
            except:
                pass
        else:
            scaled_speech = tts_speech_audio
            
    # 4. Construct final padded chunk matching exact orig_duration
    scaled_speech_dur = len(scaled_speech)
    if scaled_speech_dur != orig_speech_dur:
        if scaled_speech_dur > orig_speech_dur:
            scaled_speech = scaled_speech[:orig_speech_dur]
        else:
            padding = AudioSegment.silent(duration=orig_speech_dur - scaled_speech_dur)
            scaled_speech = scaled_speech + padding
            
    # Combine leading silence, scaled speech, and trailing silence
    leading_silence = AudioSegment.silent(duration=orig_start)
    trailing_silence_dur = orig_duration - orig_end
    if trailing_silence_dur < 0:
        trailing_silence_dur = 0
    trailing_silence = AudioSegment.silent(duration=trailing_silence_dur)
    
    final_audio = leading_silence + scaled_speech + trailing_silence
    
    # Final safety check: force total duration to be exactly orig_duration
    final_duration = len(final_audio)
    if final_duration != orig_duration:
        if final_duration > orig_duration:
            final_audio = final_audio[:orig_duration]
        else:
            final_audio = final_audio + AudioSegment.silent(duration=orig_duration - final_duration)
            
    final_audio.export(final_file, format="wav")

if not shutil.which("ffmpeg"):
    print("[!] ERROR: 'ffmpeg' is missing from your system PATH.")
    sys.exit(1)

# ==============================================================================
# INITIALIZE VERTEX AI CLIENT (Draws 100% from $300 GCP Credit)
# ==============================================================================
GCP_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or "project-fa3866df-86dd-40ea-be7"
GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION") or os.environ.get("GCP_LOCATION") or "us-central1"

vertex_client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT_ID,
    location=GCP_LOCATION
)

# Auto-discover active project chunks folder
input_folder = None
for item in os.listdir("."):
    if os.path.isdir(item) and item.endswith("_chunks") and item != "final_dubbed_chunks":
        files = os.listdir(item)
        if any(f.startswith("chunk_") and f.endswith(".wav") for f in files):
            input_folder = item
            break

if not input_folder:
    print("[!] ERROR: No active project chunks folder found.")
    sys.exit(1)

project_base = input_folder.replace("_chunks", "")
temp_tts_folder = f"temp_raw_tts_{project_base}"
final_folder = f"final_dubbed_{project_base}"

os.makedirs(temp_tts_folder, exist_ok=True)
os.makedirs(final_folder, exist_ok=True)

print("=" * 65)
print(f"       MANUAL CHUNK REPAIR TOOL ({project_base})       ")
print("=" * 65)

while True:
    print("\n-----------------------------------------------------------------")
    chunk_input = input("Enter Chunk ID to fix (e.g., '011' or 'chunk_011', or 'q' to quit): ").strip()
    
    if chunk_input.lower() in ('q', 'quit', 'exit'):
        print("\nExiting Manual Repair Tool. Run 'python3 stitcher.py' when ready!")
        break

    # Parse chunk number cleanly
    if chunk_input.startswith("chunk_"):
        chunk_num = chunk_input.replace("chunk_", "")
    elif chunk_input.startswith("dub_chunk_"):
        chunk_num = chunk_input.replace("dub_chunk_", "").replace(".wav", "")
    else:
        chunk_num = chunk_input.replace(".wav", "")

    chunk_filename = f"chunk_{chunk_num}.wav"
    original_file = os.path.join(input_folder, chunk_filename)
    raw_tts_file = os.path.join(temp_tts_folder, f"raw_tts_chunk_{chunk_num}.wav")
    final_file = os.path.join(final_folder, f"dub_chunk_{chunk_num}.wav")

    if not os.path.exists(original_file):
        print(f"[!] ERROR: Original source file '{original_file}' not found.")
        continue

    orig_audio = AudioSegment.from_file(original_file)
    orig_duration = len(orig_audio)

    print(f"[Target Chunk]      : {chunk_filename}")
    print(f"[Original Duration]: {orig_duration} ms ({orig_duration / 1000:.2f}s)")

    # Receive manual text input from user
    hindi_text = input("Enter corrected Hindi text: ").strip()

    if not hindi_text:
        print("[!] Input was empty. Overwriting chunk with exact duration silence...")
        silent_pad = AudioSegment.silent(duration=orig_duration)
        silent_pad.export(final_file, format="wav")
        print(f"[✓ OVERWRITTEN] 'dub_chunk_{chunk_num}.wav' updated with silence.")
        continue

    # --------------------------------------------------------------------------
    # STEP B: Expressive Voice Synthesis (Exact same as dubber.py)
    # --------------------------------------------------------------------------
    try:
        print("[1/2] Generating Enceladus voice via Vertex AI...")
        
        tts_response = vertex_client.models.generate_content(
            model="gemini-3.1-flash-tts-preview",
            contents=f"Say clearly and naturally in Hindi: {hindi_text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Enceladus" 
                        )
                    )
                )
            )
        )
        
        audio_part_res = tts_response.candidates[0].content.parts[0]
        out_audio_bytes = audio_part_res.inline_data.data

        with wave.open(raw_tts_file, "wb") as wf:
            wf.setnchannels(1)      
            wf.setsampwidth(2)      
            wf.setframerate(24000)  
            wf.writeframes(out_audio_bytes)

    except Exception as e:
        print(f"[!] Enceladus TTS failed: {e}")
        continue

    # --------------------------------------------------------------------------
    # STEP C: Timeline Synchronization (Exact same as dubber.py)
    # --------------------------------------------------------------------------
    print("[2/2] Aligning voice duration to original timeline...")
    align_and_export_audio(original_file, raw_tts_file, final_file)

    print(f"[✓ REPAIRED] Saved updated file: '{final_file}'")