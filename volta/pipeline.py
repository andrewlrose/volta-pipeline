"""Catalogued stage execution and advisory keyframe QC before video generation."""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import uuid
from concurrent.futures import Future
from contextlib import contextmanager
from pathlib import Path

from volta.catalog import CatalogDB
from volta.models import Asset, AssetType, PipelineStage


@contextmanager
def catalogued_stage(
    db_path: Path, source: Path, stage: PipelineStage, tool: str
):
    catalog = CatalogDB(db_path)
    catalog.init()
    asset = Asset(
        uuid.uuid4().hex[:16],
        source.stem,
        AssetType.PROP,
        stage,
        str(source),
        hashlib.sha256(source.read_bytes()).hexdigest(),
        source.stat().st_size,
    )
    with catalog.session() as conn:
        catalog.upsert_asset(conn, asset)
        run_id = catalog.start_stage_run(
            conn, asset.uid, stage, tool, str(source)
        )
    outputs: list[Path] = []
    try:
        yield outputs
        if not outputs:
            raise RuntimeError("Stage produced no downloadable outputs")
        with catalog.session() as conn:
            for index, path in enumerate(outputs):
                if index:
                    asset.uid = uuid.uuid4().hex[:16]
                asset.file_path = str(path.resolve())
                asset.name = path.stem
                asset.file_size = path.stat().st_size
                asset.file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                catalog.upsert_asset(conn, asset)
            catalog.finish_stage_run(
                conn, run_id, "success", str(outputs[0].resolve())
            )
    except Exception as exc:
        with catalog.session() as conn:
            # Do not persist remote exceptions that may include signed URLs or credentials.
            catalog.finish_stage_run(
                conn, run_id, "failed", error_message=type(exc).__name__
            )
        raise


def local_vision_check(paths: list[Path]) -> dict:
    """Opt-in, local-only Ollama check; no models downloaded and no cloud fallback."""
    import httpx

    with httpx.Client(timeout=20, trust_env=False) as client:
        response = client.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "llava",
                "stream": False,
                "format": "json",
                "prompt": "Review keyframes for visual defects and continuity. Return JSON with observations; do not approve canon.",
                "images": [
                    base64.b64encode(p.read_bytes()).decode() for p in paths
                ],
            },
        )
        response.raise_for_status()
        return json.loads(response.json()["response"])


def submit_vision_qc(
    paths: list[Path], report: Path, checker=local_vision_check
) -> Future:
    """Start a daemon advisory check. Neither delay nor failure gates video generation.

    A durable pending report makes interruption visible; callers can retain the Future
    if they need to wait for QC explicitly. This hook never grants approval.
    """
    future: Future = Future()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps({"status": "pending", "advisory": True}), encoding="utf-8"
    )

    def work():
        try:
            result = {
                "status": "complete",
                "advisory": True,
                "result": checker(paths),
            }
        except Exception as exc:
            result = {
                "status": "unavailable",
                "advisory": True,
                "error": type(exc).__name__,
            }
        temporary = report.with_suffix(report.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(result), encoding="utf-8")
            temporary.replace(report)
            future.set_result(result)
        except Exception as exc:
            future.set_exception(exc)

    threading.Thread(target=work, daemon=True, name="volta-vision-qc").start()
    return future


def keyframe_to_video(
    keyframe_stage,
    video_stage,
    *,
    vision_qc=False,
    report=None,
    checker=local_vision_check,
):
    """Stage 2 keyframes -> advisory QC launch -> Stage 5 video, without a QC gate."""
    paths = keyframe_stage()
    if not paths:
        raise ValueError("No keyframes produced")
    qc = None
    if vision_qc:
        try:
            qc = submit_vision_qc(paths, report, checker)
        except Exception as exc:
            qc = Future()
            qc.set_result(
                {
                    "status": "unavailable",
                    "advisory": True,
                    "error": type(exc).__name__,
                }
            )
    return video_stage(paths), qc
