"""VOLTA — Motion capture ingest and cleanup (Stage 7: Mocap).

Handles:
- BVH / FBX ingest from optical systems (Vicon, OptiTrack)
- AI-generated motion ingest (Plask, DeepMotion)
- Cascadeur physics cleanup (subprocess)
- Output: clean FBX ready for MotionBuilder HIK retarget

Phase 1: File validation + BVH header parsing.
Phase 2: Cascadeur headless CLI, Plask/DeepMotion API clients.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from volta.models import PipelineStage, StageError


SUPPORTED_FORMATS = {".bvh", ".fbx", ".c3d"}


@dataclass
class MocapIngestResult:
    """Result of a mocap ingest operation."""

    source_path: Path
    output_fbx: Path
    frame_count: int
    fps: float
    duration_s: float
    is_cleaned: bool
    source_system: str


def validate_mocap_file(path: Path) -> None:
    """Raise StageError if the file format is unsupported."""
    if not path.exists():
        raise StageError(
            PipelineStage.MOCAP,
            f"File not found: {path}",
        )
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise StageError(
            PipelineStage.MOCAP,
            f"Unsupported format: {path.suffix}. "
            f"Expected one of: {', '.join(SUPPORTED_FORMATS)}",
        )


def ingest_bvh(bvh_path: Path) -> dict:
    """Parse a BVH file and return motion metadata.

    Phase 1: Reads frame count and fps from BVH header.
    Phase 2: Full joint hierarchy extraction.
    """
    validate_mocap_file(bvh_path)
    frame_count = 0
    fps = 60.0
    with bvh_path.open() as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("Frames:"):
                frame_count = int(
                    stripped.split(":", 1)[1].strip()
                )
            elif stripped.startswith("Frame Time:"):
                frame_time = float(
                    stripped.split(":", 1)[1].strip()
                )
                fps = (
                    round(1.0 / frame_time)
                    if frame_time > 0
                    else 60.0
                )
            if frame_count and fps:
                break
    return {
        "frame_count": frame_count,
        "fps": fps,
        "duration_s": frame_count / fps if fps > 0 else 0.0,
    }


def run_cascadeur_cleanup(
    input_fbx: Path,
    out_dir: Path,
    cascadeur_exe: Optional[Path] = None,
) -> Path:
    """Run Cascadeur physics cleanup on an FBX file.

    Phase 1: Stub.
    Phase 2: Subprocess call to Cascadeur headless CLI.

    Manual workflow:
        1. Open Cascadeur (https://cascadeur.com)
        2. Import FBX
        3. Run AutoPhysics
        4. Export → FBX
    """
    raise NotImplementedError(
        "Cascadeur headless CLI integration is Phase 2. "
        "Clean manually in Cascadeur, export FBX to: "
        f"{out_dir}"
    )


def ingest_from_plask(
    video_path: Path,
    api_key: Optional[str] = None,
) -> str:
    """Submit a video to Plask for AI motion extraction.

    Returns a job_id to poll for completion.

    Phase 1: Stub.
    Phase 2: Plask REST API integration.
    See: https://docs.plask.ai
    """
    raise NotImplementedError(
        "Plask API integration is Phase 2. "
        "Visit https://plask.ai to process the video manually."
    )
