"""VOLTA — Unreal Engine 5 Python scripts (Stage 9: Blueprints).

IMPORTANT: Functions in this module that call `import unreal` are
intended to run inside UE5's embedded Python interpreter, NOT in
the VOLTA venv.

To use these scripts inside UE5:
    1. Enable the Python Editor Script Plugin.
    2. Open Window → Python Console (or use py.exec commandlet).
    3. Add the repo to sys.path:
           import sys
           sys.path.append(r"C:/projects/Volta")
           from volta.unreal import pcg

Running outside UE5 will raise RuntimeError — this is expected.

Phase 1: PCG and Blueprint generation stubs.
Phase 2: Full PCG graph creation, NVIDIA ACE NPC integration,
         LLM → Blueprint node graph generation.
"""

from __future__ import annotations

from typing import Any


def is_running_in_unreal() -> bool:
    """Return True if running inside UE5's Python interpreter."""
    try:
        import unreal  # noqa: F401
        return True
    except ImportError:
        return False


def create_pcg_graph(
    asset_path: str,
    name: str,
    seed: int = 42,
) -> Any:
    """Create a new PCG graph asset in the UE5 content browser.

    Phase 1: Stub.
    Phase 2: Use unreal.PCGGraphInterface to create and configure
    a Procedural Content Generation graph for environment scatter.

    Args:
        asset_path: UE content path, e.g. '/Game/PCG/ForestFloor'
        name: Asset name
        seed: PCG random seed

    Must be called from inside UE5.
    """
    if not is_running_in_unreal():
        raise RuntimeError(
            "create_pcg_graph must be called from inside UE5. "
            "Enable the Python Editor Script Plugin."
        )
    raise NotImplementedError(
        "PCG graph creation is Phase 2."
    )


def generate_blueprint_from_description(
    description: str,
    asset_path: str,
    parent_class: str = "Actor",
) -> Any:
    """Generate a UE5 Blueprint from a natural language description.

    Uses VOLTA's LLM bridge to convert a description into a
    Blueprint node graph, then creates it via unreal.BlueprintFactory.

    Phase 1: Stub.
    Phase 2: LLM → Blueprint JSON → unreal.BlueprintFactory.

    Example:
        generate_blueprint_from_description(
            "NPC that patrols between waypoints and "
            "runs when player is within 500 units",
            "/Game/Blueprints/BP_NPC_Patrol",
        )

    Must be called from inside UE5.
    """
    if not is_running_in_unreal():
        raise RuntimeError(
            "generate_blueprint_from_description must run "
            "inside UE5."
        )
    raise NotImplementedError(
        "AI Blueprint generation is Phase 2. "
        "Requires VOLTA LLM bridge + unreal.BlueprintFactory."
    )


def setup_livelink_face_receiver(
    character_asset_path: str,
) -> Any:
    """Wire a LiveLink Face source to a MetaHuman or custom rig.

    Enables iPhone TrueDepth → ARKit 52 blendshapes → UE5.

    Phase 1: Stub.
    Phase 2: unreal.LiveLinkComponent + LiveLinkFaceSubjectSettings.

    Must be called from inside UE5.
    """
    if not is_running_in_unreal():
        raise RuntimeError(
            "setup_livelink_face_receiver must run inside UE5."
        )
    raise NotImplementedError(
        "LiveLink Face receiver setup is Phase 2."
    )
