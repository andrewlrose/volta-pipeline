"""VOLTA — QA validation gates (Stage 10: Quality Assurance).

Each validator checks a specific quality criterion for a pipeline
asset. Validators are composable — run them in sequence to build
a full QA suite.

All validators return a list of QAResult records. They never raise
on failure — they return FAIL status so the caller can decide
whether to halt.

Usage:
    results = run_qa_suite(asset)
    if not qa_passed(results):
        sys.exit(1)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Protocol

from volta.models import (
    Asset,
    AssetTier,
    CharacterAsset,
    PipelineStage,
    QAResult,
    QAStatus,
)


# ── Validator protocol ────────────────────────────────────────────────────────

class Validator(Protocol):
    """Interface all QA validators must satisfy."""

    def validate(
        self, asset: Asset, run_id: str
    ) -> list[QAResult]:
        """Run checks. Returns a flat list of results."""
        ...


# ── Tier-based poly count budgets ─────────────────────────────────────────────

POLY_BUDGET: dict[AssetTier, int] = {
    AssetTier.HERO: 80_000,
    AssetTier.MID: 10_000,
    AssetTier.PROP: 2_000,
    AssetTier.ENVIRONMENT: 200_000,   # Pre-Nanite budget
}


# ── Concrete validators ───────────────────────────────────────────────────────

class FileExistsValidator:
    """Checks that the asset's file_path exists on disk."""

    def validate(
        self, asset: Asset, run_id: str
    ) -> list[QAResult]:
        path = Path(asset.file_path)
        if path.exists():
            return [
                _ok(run_id, asset, "file_exists", "File found.")
            ]
        return [
            _fail(
                run_id,
                asset,
                "file_exists",
                f"File not found: {asset.file_path}",
            )
        ]


class FileSizeValidator:
    """Warns if a file is suspiciously small (likely corrupt)."""

    def __init__(self, min_bytes: int = 1024) -> None:
        self.min_bytes = min_bytes

    def validate(
        self, asset: Asset, run_id: str
    ) -> list[QAResult]:
        if asset.file_size >= self.min_bytes:
            return [
                _ok(
                    run_id,
                    asset,
                    "file_size",
                    f"{asset.file_size:,} bytes",
                )
            ]
        return [
            _warn(
                run_id,
                asset,
                "file_size",
                f"File size {asset.file_size} bytes is below "
                f"minimum {self.min_bytes} bytes — "
                f"possible corrupt file.",
            )
        ]


class PolyCountValidator:
    """Checks that a mesh is within its tier's poly budget.

    Phase 1: Reads poly_count from CharacterAsset.poly_count.
    Phase 2: Parse FBX/OBJ/GLB directly to count triangles.
    """

    def validate(
        self, asset: Asset, run_id: str
    ) -> list[QAResult]:
        poly_count: int | None = None
        if isinstance(asset, CharacterAsset):
            poly_count = asset.poly_count
        if poly_count is None:
            return [
                _skip(
                    run_id,
                    asset,
                    "poly_count",
                    "poly_count not set — run mesh analysis first.",
                )
            ]
        budget = POLY_BUDGET.get(asset.tier, 10_000)
        if poly_count <= budget:
            return [
                _ok(
                    run_id,
                    asset,
                    "poly_count",
                    f"{poly_count:,} tris ≤ {budget:,} budget.",
                )
            ]
        return [
            _fail(
                run_id,
                asset,
                "poly_count",
                f"{poly_count:,} tris exceeds {budget:,} budget "
                f"for tier {asset.tier.value}.",
            )
        ]


class StageProgressValidator:
    """Records the current stage — always passes."""

    def validate(
        self, asset: Asset, run_id: str
    ) -> list[QAResult]:
        return [
            _ok(
                run_id,
                asset,
                "stage_progress",
                f"Current stage: {asset.stage.value}",
            )
        ]


# ── Default QA suite ──────────────────────────────────────────────────────────

DEFAULT_VALIDATORS: list[Validator] = [
    FileExistsValidator(),
    FileSizeValidator(),
    PolyCountValidator(),
    StageProgressValidator(),
]


def run_qa_suite(
    asset: Asset,
    validators: list[Validator] | None = None,
) -> list[QAResult]:
    """Run all validators against an asset. Returns flat list."""
    run_id = str(uuid.uuid4())
    suite = (
        validators
        if validators is not None
        else DEFAULT_VALIDATORS
    )
    results: list[QAResult] = []
    for v in suite:
        results.extend(v.validate(asset, run_id))
    return results


def qa_passed(results: list[QAResult]) -> bool:
    """Return True only if there are no FAIL results."""
    return all(r.status != QAStatus.FAIL for r in results)


# ── Result factory helpers ────────────────────────────────────────────────────

def _make(
    run_id: str,
    asset: Asset,
    check: str,
    status: QAStatus,
    detail: str,
) -> QAResult:
    return QAResult(
        run_id=run_id,
        asset_uid=asset.uid,
        stage=asset.stage,
        check_name=check,
        status=status,
        detail=detail,
        checked_at=datetime.utcnow(),
    )


def _ok(
    run_id: str, asset: Asset, check: str, detail: str
) -> QAResult:
    return _make(run_id, asset, check, QAStatus.PASS, detail)


def _fail(
    run_id: str, asset: Asset, check: str, detail: str
) -> QAResult:
    return _make(run_id, asset, check, QAStatus.FAIL, detail)


def _warn(
    run_id: str, asset: Asset, check: str, detail: str
) -> QAResult:
    return _make(run_id, asset, check, QAStatus.WARN, detail)


def _skip(
    run_id: str, asset: Asset, check: str, detail: str
) -> QAResult:
    return _make(run_id, asset, check, QAStatus.SKIP, detail)
