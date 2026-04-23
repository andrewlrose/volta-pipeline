"""VOLTA — SQLite asset catalog (pipeline state store)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from volta.models import (
    Asset,
    AssetTier,
    AssetType,
    PipelineStage,
    QAResult,
    QAStatus,
    StageRun,
)


_CREATE_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS assets (
    uid            TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    asset_type     TEXT NOT NULL,
    stage          TEXT NOT NULL,
    file_path      TEXT NOT NULL,
    file_hash      TEXT NOT NULL,
    file_size      INTEGER NOT NULL,
    tier           TEXT NOT NULL DEFAULT 'mid',
    tags           TEXT NOT NULL DEFAULT '[]',
    notes          TEXT NOT NULL DEFAULT '',
    created_at     TEXT,
    updated_at     TEXT
);

CREATE TABLE IF NOT EXISTS stage_runs (
    run_id         TEXT PRIMARY KEY,
    asset_uid      TEXT NOT NULL REFERENCES assets(uid),
    stage          TEXT NOT NULL,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    status         TEXT NOT NULL DEFAULT 'running',
    tool           TEXT NOT NULL DEFAULT '',
    input_path     TEXT NOT NULL DEFAULT '',
    output_path    TEXT NOT NULL DEFAULT '',
    error_message  TEXT NOT NULL DEFAULT '',
    duration_s     REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS qa_results (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT NOT NULL,
    asset_uid      TEXT NOT NULL REFERENCES assets(uid),
    stage          TEXT NOT NULL,
    check_name     TEXT NOT NULL,
    status         TEXT NOT NULL,
    detail         TEXT NOT NULL DEFAULT '',
    checked_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_assets_type
    ON assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_stage
    ON assets(stage);
CREATE INDEX IF NOT EXISTS idx_stage_runs_asset
    ON stage_runs(asset_uid);
CREATE INDEX IF NOT EXISTS idx_qa_results_asset
    ON qa_results(asset_uid);
"""


class CatalogDB:
    """SQLite-backed pipeline asset catalog."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def init(self) -> None:
        """Create tables and indexes if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.session() as conn:
            conn.executescript(_CREATE_SQL)

    @contextmanager
    def session(
        self,
    ) -> Generator[sqlite3.Connection, None, None]:
        """Yield a connection that auto-commits or rolls back."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Assets ────────────────────────────────────────────────────────────────

    def upsert_asset(
        self, conn: sqlite3.Connection, asset: Asset
    ) -> None:
        """Insert or replace an asset record."""
        now = datetime.utcnow().isoformat()
        conn.execute(
            """
            INSERT INTO assets
                (uid, name, asset_type, stage, file_path,
                 file_hash, file_size, tier, tags, notes,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                name       = excluded.name,
                stage      = excluded.stage,
                file_path  = excluded.file_path,
                file_hash  = excluded.file_hash,
                file_size  = excluded.file_size,
                tier       = excluded.tier,
                tags       = excluded.tags,
                notes      = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                asset.uid,
                asset.name,
                asset.asset_type.value,
                asset.stage.value,
                asset.file_path,
                asset.file_hash,
                asset.file_size,
                asset.tier.value,
                json.dumps(asset.tags),
                asset.notes,
                (
                    asset.created_at.isoformat()
                    if asset.created_at else now
                ),
                now,
            ),
        )

    def get_asset(
        self, conn: sqlite3.Connection, uid: str
    ) -> Optional[Asset]:
        """Retrieve an asset by UID."""
        row = conn.execute(
            "SELECT * FROM assets WHERE uid = ?", (uid,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_asset(row)

    def get_assets_by_stage(
        self,
        conn: sqlite3.Connection,
        stage: PipelineStage,
    ) -> list[Asset]:
        """Retrieve all assets currently at a given stage."""
        rows = conn.execute(
            """
            SELECT * FROM assets
            WHERE stage = ?
            ORDER BY updated_at DESC
            """,
            (stage.value,),
        ).fetchall()
        return [self._row_to_asset(r) for r in rows]

    def get_all_assets(
        self, conn: sqlite3.Connection
    ) -> list[Asset]:
        """Retrieve all assets ordered by last update."""
        rows = conn.execute(
            "SELECT * FROM assets ORDER BY updated_at DESC"
        ).fetchall()
        return [self._row_to_asset(r) for r in rows]

    def _row_to_asset(self, row: sqlite3.Row) -> Asset:
        return Asset(
            uid=row["uid"],
            name=row["name"],
            asset_type=AssetType(row["asset_type"]),
            stage=PipelineStage(row["stage"]),
            file_path=row["file_path"],
            file_hash=row["file_hash"],
            file_size=row["file_size"],
            tier=AssetTier(row["tier"]),
            tags=json.loads(row["tags"]),
            notes=row["notes"],
            created_at=(
                datetime.fromisoformat(row["created_at"])
                if row["created_at"] else None
            ),
            updated_at=(
                datetime.fromisoformat(row["updated_at"])
                if row["updated_at"] else None
            ),
        )

    # ── Stage runs ────────────────────────────────────────────────────────────

    def start_stage_run(
        self,
        conn: sqlite3.Connection,
        asset_uid: str,
        stage: PipelineStage,
        tool: str = "",
        input_path: str = "",
    ) -> str:
        """Record the start of a stage run. Returns run_id."""
        run_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO stage_runs
                (run_id, asset_uid, stage, started_at,
                 tool, input_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                asset_uid,
                stage.value,
                datetime.utcnow().isoformat(),
                tool,
                input_path,
            ),
        )
        return run_id

    def finish_stage_run(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        status: str,
        output_path: str = "",
        error_message: str = "",
        duration_s: float = 0.0,
    ) -> None:
        """Update a stage run with completion info."""
        conn.execute(
            """
            UPDATE stage_runs
            SET finished_at   = ?,
                status        = ?,
                output_path   = ?,
                error_message = ?,
                duration_s    = ?
            WHERE run_id = ?
            """,
            (
                datetime.utcnow().isoformat(),
                status,
                output_path,
                error_message,
                duration_s,
                run_id,
            ),
        )

    def get_stage_runs(
        self,
        conn: sqlite3.Connection,
        asset_uid: str,
    ) -> list[StageRun]:
        """Get all stage runs for an asset, newest first."""
        rows = conn.execute(
            """
            SELECT * FROM stage_runs
            WHERE asset_uid = ?
            ORDER BY started_at DESC
            """,
            (asset_uid,),
        ).fetchall()
        return [self._row_to_stage_run(r) for r in rows]

    def _row_to_stage_run(self, row: sqlite3.Row) -> StageRun:
        return StageRun(
            run_id=row["run_id"],
            asset_uid=row["asset_uid"],
            stage=PipelineStage(row["stage"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=(
                datetime.fromisoformat(row["finished_at"])
                if row["finished_at"] else None
            ),
            status=row["status"],
            tool=row["tool"],
            input_path=row["input_path"],
            output_path=row["output_path"],
            error_message=row["error_message"],
            duration_s=row["duration_s"],
        )

    # ── QA results ────────────────────────────────────────────────────────────

    def record_qa_result(
        self, conn: sqlite3.Connection, result: QAResult
    ) -> None:
        """Insert a QA check result."""
        conn.execute(
            """
            INSERT INTO qa_results
                (run_id, asset_uid, stage, check_name,
                 status, detail, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.run_id,
                result.asset_uid,
                result.stage.value,
                result.check_name,
                result.status.value,
                result.detail,
                (
                    result.checked_at.isoformat()
                    if result.checked_at
                    else datetime.utcnow().isoformat()
                ),
            ),
        )

    def get_qa_results(
        self,
        conn: sqlite3.Connection,
        asset_uid: str,
    ) -> list[QAResult]:
        """Get all QA results for an asset."""
        rows = conn.execute(
            """
            SELECT * FROM qa_results
            WHERE asset_uid = ?
            ORDER BY checked_at DESC
            """,
            (asset_uid,),
        ).fetchall()
        return [self._row_to_qa_result(r) for r in rows]

    def _row_to_qa_result(self, row: sqlite3.Row) -> QAResult:
        return QAResult(
            run_id=row["run_id"],
            asset_uid=row["asset_uid"],
            stage=PipelineStage(row["stage"]),
            check_name=row["check_name"],
            status=QAStatus(row["status"]),
            detail=row["detail"],
            checked_at=(
                datetime.fromisoformat(row["checked_at"])
                if row["checked_at"] else None
            ),
        )

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self, conn: sqlite3.Connection) -> dict:
        """Return high-level catalog statistics."""
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN asset_type = 'character'
                    THEN 1 ELSE 0 END) AS characters,
                SUM(CASE WHEN asset_type = 'environment'
                    THEN 1 ELSE 0 END) AS environments,
                SUM(CASE WHEN asset_type = 'motion'
                    THEN 1 ELSE 0 END) AS motions,
                SUM(CASE WHEN asset_type = 'prop'
                    THEN 1 ELSE 0 END) AS props
            FROM assets
            """
        ).fetchone()
        qa_row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'fail'
                    THEN 1 ELSE 0 END) AS fails,
                SUM(CASE WHEN status = 'warn'
                    THEN 1 ELSE 0 END) AS warns
            FROM qa_results
            """
        ).fetchone()
        runs_row = conn.execute(
            "SELECT COUNT(*) AS total FROM stage_runs"
        ).fetchone()
        return {
            "total_assets": row["total"] or 0,
            "characters": row["characters"] or 0,
            "environments": row["environments"] or 0,
            "motions": row["motions"] or 0,
            "props": row["props"] or 0,
            "stage_runs": runs_row["total"] or 0,
            "qa_fails": qa_row["fails"] or 0,
            "qa_warns": qa_row["warns"] or 0,
        }
