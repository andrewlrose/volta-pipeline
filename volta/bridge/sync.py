"""VOLTA — Bridge sync: computes live state and writes
.atlas-bridge/memory.json for ATLAS to consume.

ATLAS reads .atlas-bridge/memory.json on every ``bridge-sync`` run.
This module is the VOLTA side — it computes the current pipeline
health from the catalog and git history and writes a memory snapshot
that satisfies the BridgeSummary schema in core.bridge_sync.

Schema (memory.json top-level keys):
    status_summary  str    One-line human summary
    health          dict   {status, days_since_push, open_pr_count}
    last_updated    str    ISO timestamp of last sync
    last_atlas_sync str|null  Filled in by ATLAS on its side
    session_count   int    Incremented each time sync() is called
    alerts          list   [{id, message, severity, resolved}]
    open_tasks      list   [{id, description, priority, owner,
                             created_at}]
    metrics         dict   Arbitrary pipeline metrics

ATLAS BridgeSummary maps:
    health.status          → health_status
    health.days_since_push → days_since_push
    health.open_pr_count   → open_pr_count
    alerts[]               → BridgeAlert
    open_tasks[]           → BridgeOpenTask
    metrics                → metrics dict
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from volta.catalog import CatalogDB

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BRIDGE_DIR = _REPO_ROOT / ".atlas-bridge"
_MEMORY_FILE = _BRIDGE_DIR / "memory.json"
_TASKS_FILE = _BRIDGE_DIR / "tasks.jsonl"
_DEFAULT_DB = Path.home() / ".volta" / "catalog.db"

# Health thresholds
_ACTIVE_DAYS = 7    # pushed within this many days → "active"
_STALE_DAYS = 30    # pushed within this many days → "stale", else "inactive"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _git_days_since_push(
    project_root: Path = _REPO_ROOT,
) -> int:
    """Days since last git commit. Returns -1 if git not available."""
    try:
        result = subprocess.run(
            [
                "git", "-C", str(project_root),
                "log", "-1", "--format=%ci",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        raw = result.stdout.strip()
        if not raw:
            return -1
        last_commit = datetime.fromisoformat(raw)
        if last_commit.tzinfo is None:
            last_commit = last_commit.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        return max(0, (now - last_commit).days)
    except Exception as exc:
        logger.debug("git log failed: %s", exc)
        return -1


def _catalog_metrics(db_path: Path) -> dict:
    """Load stats from the VOLTA catalog. Returns {} on failure."""
    try:
        catalog = CatalogDB(db_path)
        catalog.init()
        with catalog.session() as conn:
            return catalog.stats(conn)
    except Exception as exc:
        logger.debug("catalog stats failed: %s", exc)
        return {}


def _load_current_memory(
    bridge_dir: Path = _BRIDGE_DIR,
) -> dict:
    """Load existing memory.json to preserve session_count etc."""
    path = bridge_dir / "memory.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _pending_task_count(
    bridge_dir: Path = _BRIDGE_DIR,
) -> int:
    """Count unresolved TaskRequest lines in tasks.jsonl."""
    path = bridge_dir / "tasks.jsonl"
    if not path.exists():
        return 0
    count = 0
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    count += 1
    except OSError:
        pass
    return count


# ── Core API ──────────────────────────────────────────────────────────────────

def compute_memory(
    db_path: Optional[Path] = None,
    bridge_dir: Optional[Path] = None,
) -> dict:
    """Compute a fresh memory snapshot without writing it.

    Merges live catalog metrics, git state, and any ATLAS-written
    fields (like last_atlas_sync, open_tasks) we want to preserve.
    """
    db = db_path or _DEFAULT_DB
    bdir = bridge_dir or _BRIDGE_DIR

    metrics = _catalog_metrics(db)
    days_since_push = _git_days_since_push()
    previous = _load_current_memory(bdir)

    # Health
    if days_since_push < 0:
        health_status = "unknown"
    elif days_since_push <= _ACTIVE_DAYS:
        health_status = "active"
    elif days_since_push <= _STALE_DAYS:
        health_status = "stale"
    else:
        health_status = "inactive"

    total = metrics.get("total_assets", 0)
    stage_runs = metrics.get("stage_runs", 0)
    qa_fails = int(metrics.get("qa_fails", 0))

    status_summary = (
        f"VOLTA Phase 1 — "
        f"{total} asset(s), {stage_runs} stage run(s)"
    )

    # Build alerts from live data, preserve any manually added ones
    alerts: list[dict] = []
    if qa_fails > 0:
        alerts.append({
            "id": "qa-fails",
            "message": (
                f"{qa_fails} QA failure(s) in catalog"
            ),
            "severity": "warning",
            "resolved": False,
        })
    pending_tasks = _pending_task_count(bdir)
    if pending_tasks > 0:
        alerts.append({
            "id": "atlas-tasks-pending",
            "message": (
                f"{pending_tasks} pending TaskRequest(s) "
                f"from ATLAS awaiting plan"
            ),
            "severity": "info",
            "resolved": False,
        })

    # Preserve ATLAS-written fields and open_tasks list
    last_atlas_sync = previous.get("last_atlas_sync")
    open_tasks = previous.get("open_tasks", [])
    prev_session = int(previous.get("session_count", 0))

    return {
        "status_summary": status_summary,
        "health": {
            "status": health_status,
            "days_since_push": days_since_push,
            "open_pr_count": 0,
        },
        "last_updated": datetime.now().isoformat(
            timespec="seconds"
        ),
        "last_atlas_sync": last_atlas_sync,
        "session_count": prev_session + 1,
        "alerts": alerts,
        "open_tasks": open_tasks,
        "metrics": {
            "total_assets": total,
            "stage_runs": stage_runs,
            "qa_fails": qa_fails,
            "qa_warns": int(metrics.get("qa_warns", 0)),
            "phases_complete": 1,
            "pipeline_stages": 12,
        },
    }


def write_memory(
    memory: dict,
    bridge_dir: Optional[Path] = None,
) -> Path:
    """Atomically write memory.json to the bridge directory."""
    bdir = bridge_dir or _BRIDGE_DIR
    bdir.mkdir(parents=True, exist_ok=True)
    out_path = bdir / "memory.json"

    # Atomic write via tempfile + rename
    fd, tmp = tempfile.mkstemp(
        dir=str(bdir), suffix=".tmp", prefix=".volta_bridge_"
    )
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2)
        Path(tmp).replace(out_path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return out_path


def sync(
    db_path: Optional[Path] = None,
    bridge_dir: Optional[Path] = None,
) -> dict:
    """Compute and write bridge memory. Returns the memory dict."""
    memory = compute_memory(db_path, bridge_dir)
    write_memory(memory, bridge_dir)
    return memory


def read_tasks(
    bridge_dir: Optional[Path] = None,
) -> list[dict]:
    """Read TaskRequest lines from tasks.jsonl (written by ATLAS)."""
    bdir = bridge_dir or _BRIDGE_DIR
    path = bdir / "tasks.jsonl"
    if not path.exists():
        return []
    tasks: list[dict] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                tasks.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning(
                    "tasks.jsonl line %d invalid JSON: %s", i, exc
                )
    return tasks


def update_task_status(
    task_id: str,
    new_status: str,
    bridge_dir: Optional[Path] = None,
) -> bool:
    """Update the ``status`` field of one task in tasks.jsonl.

    Rewrites the file atomically via a temp-file swap so a partial
    write never corrupts the queue.  Returns True if the task was found
    and updated, False otherwise.

    Both key names used across ATLAS formats are checked:
    ``id`` (dashboard / simplified) and ``task_request_id``
    (full Bridge Protocol).
    """
    bdir = bridge_dir or _BRIDGE_DIR
    path = bdir / "tasks.jsonl"
    if not path.exists():
        return False

    lines: list[str] = []
    found = False
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw_stripped = raw.strip()
            if not raw_stripped:
                lines.append(raw)
                continue
            try:
                task = json.loads(raw_stripped)
                tid = task.get("id") or task.get(
                    "task_request_id", ""
                )
                if tid == task_id:
                    task["status"] = new_status
                    lines.append(json.dumps(task) + "\n")
                    found = True
                    continue
            except json.JSONDecodeError:
                pass
            lines.append(raw)

    if not found:
        return False

    # Atomic write via tempfile in same directory
    try:
        fd, tmp = tempfile.mkstemp(
            dir=str(bdir), suffix=".tmp"
        )
        with open(fd, "w", encoding="utf-8") as fh:
            fh.writelines(lines)
        Path(tmp).replace(path)
    except (OSError, IOError) as exc:
        logger.error(
            "Failed to rewrite tasks.jsonl: %s", exc
        )
        return False
    return True
