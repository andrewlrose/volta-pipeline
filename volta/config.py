"""Project-local catalog resolution (evaluated at call time)."""

import os
from pathlib import Path

VOLTA_ROOT = Path(__file__).resolve().parents[1]


def resolve_catalog_db_path(project_dir: Path | None = None) -> Path:
    """Honor explicit override, then nearest project, with legacy no-project fallback."""
    override = os.environ.get("VOLTA_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()
    if project_dir is None:
        return VOLTA_ROOT / "catalog.db"
    start = Path(project_dir).expanduser().resolve()
    for parent in (start, *start.parents):
        if (
            (parent / ".volta").is_dir()
            or (parent / "volta-project.yaml").is_file()
            or (parent / ".git").exists()
        ):
            return parent / ".volta" / "catalog.db"
    return start / ".volta" / "catalog.db"
