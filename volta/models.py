"""VOLTA — data models and exception hierarchy."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


# ── Enumerations ──────────────────────────────────────────────────────────────

class PipelineStage(str, Enum):
    """Ordered pipeline stages."""

    CONCEPT = "concept"
    CONSISTENCY = "consistency"
    MESH = "mesh"
    RETOPO = "retopo"
    MATERIAL = "material"
    RIG = "rig"
    FACIAL = "facial"
    MOCAP = "mocap"
    ASSEMBLY = "assembly"
    BLUEPRINTS = "blueprints"
    QA = "qa"
    EXPORT = "export"


class AssetType(str, Enum):
    CHARACTER = "character"
    ENVIRONMENT = "environment"
    PROP = "prop"
    MOTION = "motion"
    FACIAL_ANIM = "facial_anim"
    MATERIAL = "material"
    BLUEPRINT = "blueprint"


class AssetTier(str, Enum):
    HERO = "hero"          # 10k–80k tris, full retopo + bake
    MID = "mid"            # 2k–10k tris, auto retopo
    PROP = "prop"          # <2k tris, raw AI output OK
    ENVIRONMENT = "env"    # Terrain/architecture, Nanite


class SkeletonStandard(str, Enum):
    HIK = "hik"                  # MotionBuilder HIK (canonical)
    UE_MANNEQUIN = "ue_mannequin"
    METAHUMAN = "metahuman"
    CUSTOM = "custom"


class ExportTarget(str, Enum):
    FILM = "film"        # EXR/ProRes via Movie Render Queue
    GAME = "game"        # UE5 packaged build
    SOCIAL = "social"    # H.264/H.265 via FFmpeg
    WEB = "web"          # Pixel Streaming / WebGL
    VR = "vr"            # Quest / SteamVR


class QAStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


# ── Exceptions ────────────────────────────────────────────────────────────────

class VoltaError(Exception):
    """Base exception for all VOLTA errors."""


class StageError(VoltaError):
    """Raised when a pipeline stage fails."""

    def __init__(self, stage: PipelineStage, reason: str) -> None:
        self.stage = stage
        super().__init__(f"Stage {stage.value} failed: {reason}")


class AssetError(VoltaError):
    """Raised for asset I/O or format issues."""

    def __init__(self, asset_uid: str, reason: str) -> None:
        self.asset_uid = asset_uid
        super().__init__(f"Asset {asset_uid}: {reason}")


class ValidationError(VoltaError):
    """Raised when a QA gate fails hard."""

    def __init__(self, check: str, detail: str) -> None:
        self.check = check
        super().__init__(f"Validation failed [{check}]: {detail}")


class ExportError(VoltaError):
    """Raised when export routing fails."""

    def __init__(self, target: ExportTarget, reason: str) -> None:
        self.target = target
        super().__init__(
            f"Export to {target.value} failed: {reason}"
        )


class ComfyError(VoltaError):
    """Raised on ComfyUI API errors."""


class MeshyError(VoltaError):
    """Raised on Meshy API errors."""


# ── Core asset dataclasses ────────────────────────────────────────────────────

@dataclass
class Asset:
    """Base record for any pipeline asset."""

    uid: str
    name: str
    asset_type: AssetType
    stage: PipelineStage
    file_path: str
    file_hash: str
    file_size: int
    tier: AssetTier = AssetTier.MID
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def uid_from_path(cls, path: Path) -> str:
        """Derive a stable UID from file path + size."""
        raw = f"{path.resolve()}:{path.stat().st_size}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class CharacterAsset(Asset):
    """A character mesh or rig asset."""

    skeleton_standard: SkeletonStandard = SkeletonStandard.HIK
    rig_path: Optional[str] = None
    lod_count: int = 1
    poly_count: Optional[int] = None
    has_blendshapes: bool = False
    metahuman_id: Optional[str] = None


@dataclass
class EnvironmentAsset(Asset):
    """An environment or level asset."""

    biome: str = ""
    is_tile_set: bool = False
    uses_nanite: bool = True


@dataclass
class MotionAsset(Asset):
    """A motion capture or AI-generated animation asset."""

    source: str = ""    # e.g. "vicon", "deepmotion", "cascadeur"
    frame_count: int = 0
    fps: float = 60.0
    duration_s: float = 0.0
    is_cleaned: bool = False
    skeleton_standard: SkeletonStandard = SkeletonStandard.HIK


@dataclass
class FacialAnimAsset(Asset):
    """An ARKit / LiveLink facial animation asset."""

    source: str = ""    # e.g. "livelink", "audio2face", "d-id"
    blendshape_count: int = 52
    frame_count: int = 0
    fps: float = 60.0
    character_uid: Optional[str] = None


# ── Pipeline run records ──────────────────────────────────────────────────────

@dataclass
class StageRun:
    """Record of a single pipeline stage execution."""

    run_id: str
    asset_uid: str
    stage: PipelineStage
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str = "running"    # running | success | failed
    tool: str = ""
    input_path: str = ""
    output_path: str = ""
    error_message: str = ""
    duration_s: float = 0.0


@dataclass
class QAResult:
    """Result of a single QA validation check."""

    run_id: str
    asset_uid: str
    stage: PipelineStage
    check_name: str
    status: QAStatus
    detail: str = ""
    checked_at: Optional[datetime] = None
