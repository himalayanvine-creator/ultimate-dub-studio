"""
Slice Editor Microservice Endpoints
Handles DAW-style slice editing, validation, and chunk re-export
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import json
import os
import shutil
from pydub import AudioSegment
from pathlib import Path

router = APIRouter(prefix="/api/projects", tags=["slice-editor"])

class SlicePoint(BaseModel):
    start_sec: float
    end_sec: float
    duration_sec: float

class SaveSlicesRequest(BaseModel):
    project_id: str
    slices: List[SlicePoint]

@router.post("/{project_id}/save-slices")
async def save_slices(project_id: str, request: SaveSlicesRequest):
    """
    Save manually edited slices and re-export chunks with automatic renaming.
    
    Process:
    1. Validate slice boundaries (no overlaps, correct order)
    2. Re-export audio chunks from source file with new boundaries
    3. Auto-rename chunks (chunk_001, chunk_002, etc.)
    4. Update timeline.json with new metadata
    5. Clear downstream generated files (dubber output, etc.)
    6. Return status for pipeline re-run
    """
    try:
        # Find project workspace
        workspace_path = Path("projects") / project_id
        if not workspace_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")

        # Get source audio file
        project_dir = workspace_path
        source_files = [
            f for f in os.listdir(project_dir)
            if f.endswith((".wav", ".mp3", ".m4a", ".mp4", ".mkv", ".mov"))
            and not f.startswith("FINAL_DUBBED_")
            and not f.startswith("EXPORTED_")
        ]
        
        if not source_files:
            raise HTTPException(status_code=400, detail="No source audio file found")

        source_file = source_files[0]
        source_path = project_dir / source_file
        base_name = source_file.rsplit(".", 1)[0]

        # Validate slices
        validate_slices(request.slices)

        # Load source audio
        audio = AudioSegment.from_file(str(source_path))
        total_duration_ms = len(audio)

        # Create new chunks directory
        chunks_dir = project_dir / f"{base_name}_chunks"
        old_chunks = list(chunks_dir.glob("chunk_*.wav")) if chunks_dir.exists() else []

        # Clear old chunks
        if chunks_dir.exists():
            shutil.rmtree(chunks_dir)
        chunks_dir.mkdir(parents=True, exist_ok=True)

        # Export new chunks with auto-naming
        timeline_metadata = {}
        for idx, slice_point in enumerate(request.slices, start=1):
            chunk_id = f"chunk_{str(idx).zfill(3)}"
            start_ms = int(slice_point.start_sec * 1000)
            end_ms = int(slice_point.end_sec * 1000)

            # Extract chunk from audio
            chunk_audio = audio[start_ms:end_ms]
            chunk_file = chunks_dir / f"{chunk_id}.wav"
            chunk_audio.export(str(chunk_file), format="wav")

            # Store metadata
            timeline_metadata[chunk_id] = {
                "filename": f"{chunk_id}.wav",
                "start_sec": round(slice_point.start_sec, 3),
                "end_sec": round(slice_point.end_sec, 3),
                "duration_sec": round(slice_point.duration_sec, 3)
            }

        # Save updated timeline.json
        timeline_path = chunks_dir / "timeline.json"
        with open(timeline_path, "w") as f:
            json.dump(timeline_metadata, f, indent=2)

        # Clear downstream generated files
        clear_downstream_files(project_dir, base_name)

        return {
            "status": "success",
            "message": f"Saved {len(request.slices)} slices. Chunks renamed and re-exported.",
            "chunks_count": len(request.slices),
            "timeline_path": str(timeline_path),
            "action": "SLICE_SAVED"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving slices: {str(e)}")


@router.get("/{project_id}/slice-timeline")
async def get_slice_timeline(project_id: str):
    """
    Get current slice timeline for DAW editor visualization.
    Returns both original and current state.
    """
    try:
        workspace_path = Path("projects") / project_id
        if not workspace_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")

        # Find chunks directory and timeline.json
        chunks_dirs = list(workspace_path.glob("*_chunks"))
        if not chunks_dirs:
            raise HTTPException(status_code=400, detail="No slices found")

        chunks_dir = chunks_dirs[0]
        timeline_path = chunks_dir / "timeline.json"

        if not timeline_path.exists():
            raise HTTPException(status_code=400, detail="Timeline metadata not found")

        with open(timeline_path, "r") as f:
            timeline = json.load(f)

        slices = [
            {
                "chunk_id": chunk_id,
                "start_sec": data["start_sec"],
                "end_sec": data["end_sec"],
                "duration_sec": data["duration_sec"]
            }
            for chunk_id, data in timeline.items()
        ]

        return {
            "project_id": project_id,
            "slices": slices,
            "total_slices": len(slices),
            "total_duration": sum(s["duration_sec"] for s in slices)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching timeline: {str(e)}")


@router.post("/{project_id}/validate-slices")
async def validate_slices_endpoint(project_id: str, request: SaveSlicesRequest):
    """
    Validate slice boundaries without saving.
    Used for preview in DAW editor.
    """
    try:
        validate_slices(request.slices)
        return {
            "status": "valid",
            "message": "All slices are valid",
            "slices_count": len(request.slices)
        }
    except ValueError as e:
        return {
            "status": "invalid",
            "message": str(e),
            "slices_count": len(request.slices)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


@router.post("/{project_id}/preview-slices")
async def preview_slices(project_id: str, request: SaveSlicesRequest):
    """
    Generate waveform preview data for DAW editor.
    Returns visual representation of slices.
    """
    try:
        workspace_path = Path("projects") / project_id
        if not workspace_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")

        # Generate visual markers for each slice
        preview_data = {
            "slices": [
                {
                    "index": idx,
                    "start_sec": s.start_sec,
                    "end_sec": s.end_sec,
                    "duration_sec": s.duration_sec,
                    "chunk_name": f"chunk_{str(idx).zfill(3)}"
                }
                for idx, s in enumerate(request.slices, start=1)
            ],
            "total_duration": sum(s.duration_sec for s in request.slices),
            "total_chunks": len(request.slices)
        }

        return preview_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview error: {str(e)}")


# Helper Functions

def validate_slices(slices: List[SlicePoint]) -> bool:
    """
    Validate slice boundaries:
    - No negative times
    - No overlaps
    - Correct chronological order
    - Minimum duration per slice (100ms)
    """
    if not slices:
        raise ValueError("At least one slice required")

    if slices[0].start_sec < 0:
        raise ValueError("Slice start time cannot be negative")

    for idx, slice_point in enumerate(slices):
        # Check minimum duration
        if slice_point.duration_sec < 0.1:
            raise ValueError(f"Slice {idx + 1} duration too short (min 100ms)")

        # Check chronological order
        if idx > 0:
            prev_slice = slices[idx - 1]
            if slice_point.start_sec < prev_slice.end_sec:
                raise ValueError(f"Slice {idx + 1} overlaps with previous slice")

        # Verify duration calculation
        calculated_duration = slice_point.end_sec - slice_point.start_sec
        if abs(calculated_duration - slice_point.duration_sec) > 0.001:
            raise ValueError(f"Slice {idx + 1} duration mismatch")

    return True


def clear_downstream_files(project_dir: Path, base_name: str):
    """
    Clear files generated downstream from slicing:
    - Dubbed audio chunks
    - Transcriptions (can be refreshed from re-sliced chunks)
    - Final stitched audio
    - Audit logs
    """
    downstream_patterns = [
        f"*_text_*",  # Transcription folders
        f"final_dubbed_*",  # Dubbed chunks
        f"FINAL_DUBBED_*.wav",  # Final stitched audio
        f"EXPORTED_*.mp4",  # Exported videos
    ]

    for pattern in downstream_patterns:
        for item in project_dir.glob(pattern):
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            elif item.is_file():
                item.unlink(missing_ok=True)


def calculate_slice_statistics(slices: List[SlicePoint]) -> dict:
    """Calculate statistics about slices for UI display."""
    if not slices:
        return {
            "total_duration": 0,
            "avg_duration": 0,
            "max_duration": 0,
            "min_duration": 0
        }

    durations = [s.duration_sec for s in slices]
    return {
        "total_duration": sum(durations),
        "avg_duration": sum(durations) / len(durations),
        "max_duration": max(durations),
        "min_duration": min(durations),
        "total_chunks": len(slices)
    }
