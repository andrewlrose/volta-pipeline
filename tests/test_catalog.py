"""Tests for volta.catalog — CatalogDB CRUD operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from volta.catalog import CatalogDB
from volta.models import (
    Asset,
    AssetTier,
    AssetType,
    PipelineStage,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def catalog(tmp_path: Path) -> CatalogDB:
    """An initialised in-memory-style CatalogDB in a temp dir."""
    db = CatalogDB(tmp_path / "test.db")
    db.init()
    return db


def _make_asset(
    name: str = "test_motion",
    uid: str = "deadbeef00000001",
    asset_type: AssetType = AssetType.MOTION,
    stage: PipelineStage = PipelineStage.MOCAP,
) -> Asset:
    return Asset(
        uid=uid,
        name=name,
        asset_type=asset_type,
        stage=stage,
        file_path=f"/mock/{name}.bvh",
        file_hash="abc123",
        file_size=1024,
        tier=AssetTier.MID,
    )


# ── init ──────────────────────────────────────────────────────────────────────

class TestCatalogInit:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "subdir" / "catalog.db"
        catalog = CatalogDB(db_path)
        catalog.init()
        assert db_path.exists()

    def test_idempotent(self, catalog: CatalogDB) -> None:
        catalog.init()  # Second call should not raise.
        catalog.init()


# ── upsert + get ──────────────────────────────────────────────────────────────

class TestUpsertAndGet:
    def test_insert_and_retrieve(self, catalog: CatalogDB) -> None:
        asset = _make_asset()
        with catalog.session() as conn:
            catalog.upsert_asset(conn, asset)
        with catalog.session() as conn:
            retrieved = catalog.get_asset(conn, asset.uid)
        assert retrieved is not None
        assert retrieved.uid == asset.uid
        assert retrieved.name == asset.name

    def test_get_missing_returns_none(
        self, catalog: CatalogDB
    ) -> None:
        with catalog.session() as conn:
            result = catalog.get_asset(conn, "nonexistent")
        assert result is None

    def test_upsert_updates_existing(
        self, catalog: CatalogDB
    ) -> None:
        asset = _make_asset()
        with catalog.session() as conn:
            catalog.upsert_asset(conn, asset)

        updated = _make_asset()
        updated.notes = "updated note"
        with catalog.session() as conn:
            catalog.upsert_asset(conn, updated)

        with catalog.session() as conn:
            retrieved = catalog.get_asset(conn, asset.uid)
        assert retrieved is not None
        assert retrieved.notes == "updated note"

    def test_asset_type_roundtrip(
        self, catalog: CatalogDB
    ) -> None:
        asset = _make_asset(
            uid="char0001",
            asset_type=AssetType.CHARACTER,
        )
        with catalog.session() as conn:
            catalog.upsert_asset(conn, asset)
            retrieved = catalog.get_asset(conn, asset.uid)
        assert retrieved is not None
        assert retrieved.asset_type == AssetType.CHARACTER


# ── stats ─────────────────────────────────────────────────────────────────────

class TestStats:
    def test_empty_catalog_stats(
        self, catalog: CatalogDB
    ) -> None:
        with catalog.session() as conn:
            s = catalog.stats(conn)
        assert s["total_assets"] == 0
        assert s["motions"] == 0

    def test_stats_count_by_type(
        self, catalog: CatalogDB
    ) -> None:
        assets = [
            _make_asset(
                uid="m1", asset_type=AssetType.MOTION
            ),
            _make_asset(
                uid="m2", asset_type=AssetType.MOTION
            ),
            _make_asset(
                uid="c1", asset_type=AssetType.CHARACTER
            ),
        ]
        with catalog.session() as conn:
            for a in assets:
                catalog.upsert_asset(conn, a)
        with catalog.session() as conn:
            s = catalog.stats(conn)
        assert s["total_assets"] == 3
        assert s["motions"] == 2
        assert s["characters"] == 1


# ── get_assets_by_stage ───────────────────────────────────────────────────────

class TestGetAssetsByStage:
    def test_returns_matching_stage(
        self, catalog: CatalogDB
    ) -> None:
        mocap_asset = _make_asset(
            uid="m1", stage=PipelineStage.MOCAP
        )
        mesh_asset = _make_asset(
            uid="mesh1", stage=PipelineStage.MESH
        )
        with catalog.session() as conn:
            catalog.upsert_asset(conn, mocap_asset)
            catalog.upsert_asset(conn, mesh_asset)
        with catalog.session() as conn:
            results = catalog.get_assets_by_stage(
                conn, PipelineStage.MOCAP
            )
        assert len(results) == 1
        assert results[0].uid == "m1"
