"""VOLTA — MotionBuilder HIK rig management (Stage 5: Rigging).

MotionBuilder HIK (Human IK) is the canonical skeleton standard for
VOLTA. All character rigs pass through HIK before retargeting to UE5
or other DCCs.

This module manages:
- HIK character definition templates
- AccuRig automation (Reallusion AccuRig CLI)
- HIK → UE5 retarget config generation

Phase 1: Template loading + stubs with clear instructions.
Phase 2: Full AccuRig subprocess + MotionBuilder Python SDK integration.

Note: MotionBuilder Python commands run inside MB's embedded Python
interpreter, not in the VOLTA venv. Scripts intended for in-MB
execution live in templates/mb_scripts/.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from volta.models import SkeletonStandard


# Templates directory (relative to repo root)
_REPO_ROOT = Path(__file__).parent.parent.parent
TEMPLATES_DIR = _REPO_ROOT / "templates"
HIK_TEMPLATES_DIR = TEMPLATES_DIR / "hik"
MB_SCRIPTS_DIR = TEMPLATES_DIR / "mb_scripts"


@dataclass
class HIKConfig:
    """Defines a HIK character mapping for retargeting."""

    name: str
    source_standard: SkeletonStandard
    target_standard: SkeletonStandard
    template_path: Path
    notes: str = ""


def list_hik_templates() -> list[Path]:
    """Return available HIK template XML files."""
    if not HIK_TEMPLATES_DIR.exists():
        return []
    return sorted(HIK_TEMPLATES_DIR.glob("*.xml"))


def run_accurig(
    fbx_path: Path,
    out_dir: Path,
    skeleton_standard: SkeletonStandard = SkeletonStandard.HIK,
    accurig_exe: Optional[Path] = None,
) -> Path:
    """Auto-rig an FBX mesh via Reallusion AccuRig CLI.

    AccuRig CLI is available as part of Reallusion AccuRig Pro.
    Install path varies by platform; pass accurig_exe to override.

    Returns the rigged FBX output path.

    Phase 1: Stub — raises NotImplementedError until AccuRig CLI
    path is confirmed and the subprocess interface is tested.

    Manual workflow:
        1. Open AccuRig (https://www.reallusion.com/accurig/)
        2. Import FBX mesh
        3. Run auto-detection → adjust HIK joint mapping
        4. Export → FBX with HIK character definition
        5. Open in MotionBuilder → set as HIK character
    """
    raise NotImplementedError(
        "AccuRig CLI integration is Phase 2. "
        f"Rig manually in AccuRig, export HIK FBX to: {out_dir}"
    )


def generate_retarget_config(
    source: SkeletonStandard,
    target: SkeletonStandard,
    out_path: Path,
) -> Path:
    """Generate a UE5 IK Retargeter config JSON.

    Phase 1: Returns a minimal stub config.
    Phase 2: Pull bone name maps from HIK templates + UE5 Mannequin
    reference to produce a complete retarget chain.
    """
    import json

    config = {
        "source_skeleton": source.value,
        "target_skeleton": target.value,
        # Phase 2: populate from HIK template + skeleton defs
        "bone_mappings": [],
        "ik_chain_mappings": [],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(config, indent=2))
    return out_path
