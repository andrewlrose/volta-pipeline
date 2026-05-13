"""Tests for volta.mocap.ingest — BVH parsing and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from volta.mocap.ingest import ingest_bvh, validate_mocap_file
from volta.models import PipelineStage, StageError


# ── fixtures ──────────────────────────────────────────────────────────────────

BVH_MINIMAL = textwrap.dedent("""\
    HIERARCHY
    ROOT Hips
    {
        OFFSET 0.00 0.00 0.00
        CHANNELS 3 Xrotation Yrotation Zrotation
        End Site
        {
            OFFSET 0.00 5.00 0.00
        }
    }
    MOTION
    Frames: 120
    Frame Time: 0.016667
    0.0 0.0 0.0
""")

BVH_30FPS = textwrap.dedent("""\
    HIERARCHY
    ROOT Hips
    {
        OFFSET 0.00 0.00 0.00
        CHANNELS 3 Xrotation Yrotation Zrotation
        End Site
        {
            OFFSET 0.00 5.00 0.00
        }
    }
    MOTION
    Frames: 90
    Frame Time: 0.033333
    0.0 0.0 0.0
""")


@pytest.fixture()
def bvh_60fps(tmp_path: Path) -> Path:
    """A valid 120-frame, 60fps BVH file."""
    p = tmp_path / "walk_cycle.bvh"
    p.write_text(BVH_MINIMAL)
    return p


@pytest.fixture()
def bvh_30fps(tmp_path: Path) -> Path:
    """A valid 90-frame, 30fps BVH file."""
    p = tmp_path / "idle.bvh"
    p.write_text(BVH_30FPS)
    return p


# ── validate_mocap_file ───────────────────────────────────────────────────────

class TestValidateMocapFile:
    def test_valid_bvh_passes(self, bvh_60fps: Path) -> None:
        validate_mocap_file(bvh_60fps)  # Should not raise.

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "ghost.bvh"
        with pytest.raises(StageError) as exc_info:
            validate_mocap_file(missing)
        assert exc_info.value.stage == PipelineStage.MOCAP
        assert "not found" in str(exc_info.value).lower()

    def test_unsupported_extension_raises(
        self, tmp_path: Path
    ) -> None:
        bad = tmp_path / "motion.abc"
        bad.write_text("not a real file")
        with pytest.raises(StageError) as exc_info:
            validate_mocap_file(bad)
        assert "unsupported" in str(exc_info.value).lower()

    def test_fbx_is_valid_format(self, tmp_path: Path) -> None:
        fbx = tmp_path / "rig.fbx"
        fbx.write_bytes(b"\x00" * 16)  # Dummy content.
        validate_mocap_file(fbx)  # Should not raise.


# ── ingest_bvh ────────────────────────────────────────────────────────────────

class TestIngestBvh:
    def test_frame_count_parsed(self, bvh_60fps: Path) -> None:
        meta = ingest_bvh(bvh_60fps)
        assert meta["frame_count"] == 120

    def test_fps_60_parsed(self, bvh_60fps: Path) -> None:
        meta = ingest_bvh(bvh_60fps)
        assert meta["fps"] == pytest.approx(60.0, abs=1.0)

    def test_fps_30_parsed(self, bvh_30fps: Path) -> None:
        meta = ingest_bvh(bvh_30fps)
        assert meta["fps"] == pytest.approx(30.0, abs=1.0)

    def test_duration_computed(self, bvh_60fps: Path) -> None:
        meta = ingest_bvh(bvh_60fps)
        # 120 frames / 60 fps = 2.0 seconds
        assert meta["duration_s"] == pytest.approx(2.0, abs=0.1)

    def test_duration_30fps(self, bvh_30fps: Path) -> None:
        meta = ingest_bvh(bvh_30fps)
        # 90 frames / 30 fps = 3.0 seconds
        assert meta["duration_s"] == pytest.approx(3.0, abs=0.1)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(StageError):
            ingest_bvh(tmp_path / "ghost.bvh")
