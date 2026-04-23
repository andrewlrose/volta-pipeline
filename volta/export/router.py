"""VOLTA — Export routing layer (Stage 11: Export).

Routes pipeline output to delivery targets:

- SOCIAL: FFmpeg H.264/H.265 transcode (Phase 1 — implemented)
- FILM:   UE5 Movie Render Queue → EXR/ProRes (Phase 2 — stub)
- GAME:   UE5 packaged build via RunUAT (Phase 2 — stub)
- WEB:    UE5 Pixel Streaming or WebGL (Phase 2 — stub)
- VR:     Quest / SteamVR package (Phase 2 — stub)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from volta.models import ExportError, ExportTarget


# ── Social presets (FFmpeg) ───────────────────────────────────────────────────

SOCIAL_PRESETS: dict[str, dict] = {
    "youtube_4k": {
        "vcodec": "libx264",
        "video_bitrate": "40000k",
        "acodec": "aac",
        "audio_bitrate": "192k",
        "pix_fmt": "yuv420p",
    },
    "youtube_1080": {
        "vcodec": "libx264",
        "video_bitrate": "8000k",
        "acodec": "aac",
        "audio_bitrate": "192k",
        "pix_fmt": "yuv420p",
    },
    "instagram_reel": {
        "vcodec": "libx264",
        "video_bitrate": "3500k",
        "acodec": "aac",
        "audio_bitrate": "128k",
        "pix_fmt": "yuv420p",
    },
    "tiktok": {
        "vcodec": "libx264",
        "video_bitrate": "2500k",
        "acodec": "aac",
        "audio_bitrate": "128k",
        "pix_fmt": "yuv420p",
    },
}


def export_social(
    input_path: Path,
    out_dir: Path,
    preset: str = "youtube_1080",
    overwrite: bool = False,
) -> Path:
    """Transcode a video for social/streaming delivery via FFmpeg.

    Returns the output file path.
    """
    if not shutil.which("ffmpeg"):
        raise ExportError(
            ExportTarget.SOCIAL,
            "ffmpeg not found on PATH. "
            "Install from https://ffmpeg.org/download.html",
        )
    if preset not in SOCIAL_PRESETS:
        raise ExportError(
            ExportTarget.SOCIAL,
            f"Unknown preset '{preset}'. "
            f"Available: {', '.join(SOCIAL_PRESETS)}",
        )
    params = SOCIAL_PRESETS[preset]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{input_path.stem}_{preset}.mp4"
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-c:v", params["vcodec"],
        "-b:v", params["video_bitrate"],
        "-c:a", params["acodec"],
        "-b:a", params["audio_bitrate"],
        "-pix_fmt", params["pix_fmt"],
        "-movflags", "+faststart",
    ]
    if overwrite:
        cmd.append("-y")
    cmd.append(str(out_path))
    try:
        subprocess.run(
            cmd, check=True, capture_output=True
        )
    except subprocess.CalledProcessError as exc:
        raise ExportError(
            ExportTarget.SOCIAL,
            f"FFmpeg failed: {exc.stderr.decode()[:500]}",
        ) from exc
    return out_path


# ── Film export (Phase 2 stub) ────────────────────────────────────────────────

def export_film(
    sequence_dir: Path,
    out_dir: Path,
    fmt: str = "prores",
) -> Path:
    """Export EXR sequence or ProRes via UE5 Movie Render Queue.

    Phase 1: Stub.
    Phase 2: Invoke Movie Render Queue via UE5 Python API or
    commandlet: UnrealEditor -run=MoviePipelineLocalExecutor

    Manual workflow in UE5:
        Window → Movie Render Queue → configure settings → render
    """
    raise NotImplementedError(
        "Film export via Movie Render Queue is Phase 2. "
        "In UE5: Window → Movie Render Queue → Render."
    )


# ── Game packaging (Phase 2 stub) ─────────────────────────────────────────────

def export_game(
    project_path: Path,
    target_platform: str = "Win64",
    out_dir: Optional[Path] = None,
) -> Path:
    """Package a UE5 project for a target platform.

    Phase 1: Stub.
    Phase 2: Call RunUAT.bat/sh with BuildCookRun arguments.

    Manual workflow in UE5:
        Platforms → Windows → Package Project
    """
    raise NotImplementedError(
        "Game packaging is Phase 2. "
        "In UE5: Platforms → Windows → Package Project."
    )
