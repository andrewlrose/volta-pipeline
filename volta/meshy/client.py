"""VOLTA — Meshy API client (Stage 2: Image/Text → 3D Mesh).

Meshy (https://www.meshy.ai) provides Image→3D and Text→3D generation.
API docs: https://docs.meshy.ai/api-image-to-3d

Phase 1: Client skeleton — task creation, polling, URL retrieval.
Phase 2: Auto-download GLB/FBX, LOD tier routing, batch processing.

Environment:
    MESHY_API_KEY — required; obtain from https://app.meshy.ai/settings
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from volta.models import AssetTier, MeshyError

BASE_URL = "https://api.meshy.ai/openapi"
POLL_INTERVAL_S = 5.0
MAX_WAIT_S = 900.0  # 15 minutes

# Map asset tier to Meshy topology quality setting
_TIER_TOPOLOGY: dict[AssetTier, str] = {
    AssetTier.HERO: "high",
    AssetTier.MID: "medium",
    AssetTier.PROP: "low",
    AssetTier.ENVIRONMENT: "medium",
}

_MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class MeshyClient:
    """REST client for the Meshy 3D generation API."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        key = api_key or os.environ.get("MESHY_API_KEY")
        if not key:
            raise MeshyError(
                "MESHY_API_KEY not set. Export it or pass api_key= explicitly."
            )
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {key}"},
            timeout=60.0,
        )

    def image_to_3d(
        self,
        image_path: Path,
        tier: AssetTier = AssetTier.MID,
        enable_pbr: bool = True,
    ) -> str:
        """Submit an Image→3D task. Returns task_id."""
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        suffix = image_path.suffix.lower()
        mime = _MIME_MAP.get(suffix, "image/jpeg")
        encoded = base64.b64encode(image_path.read_bytes()).decode()
        payload: dict[str, Any] = {
            "image_url": f"data:{mime};base64,{encoded}",
            "topology": "triangle",
            "enable_pbr": enable_pbr,
        }
        try:
            resp = self._client.post("/v1/image-to-3d", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MeshyError(f"image-to-3d request failed: {exc}") from exc
        return resp.json()["result"]

    def text_to_3d(
        self,
        prompt: str,
        negative_prompt: str = "",
        tier: AssetTier = AssetTier.MID,
        art_style: str = "realistic",
        enable_pbr: bool = True,
    ) -> str:
        """Submit a Text→3D task. Returns task_id."""
        payload: dict[str, Any] = {
            "mode": "preview",
            "prompt": prompt,
            "art_style": art_style,
            "topology": "triangle",
            "target_polycount": {
                AssetTier.HERO: 80000,
                AssetTier.MID: 10000,
                AssetTier.PROP: 2000,
                AssetTier.ENVIRONMENT: 10000,
            }[tier],
            "should_remesh": True,
        }
        try:
            resp = self._client.post("/v2/text-to-3d", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MeshyError(f"text-to-3d request failed: {exc}") from exc
        return resp.json()["result"]

    def wait_for_task(
        self,
        task_id: str,
        max_wait_s: float = MAX_WAIT_S,
        mode: str = "image",
    ) -> dict[str, Any]:
        """Poll until the task succeeds. Returns full task dict."""
        deadline = time.monotonic() + max_wait_s
        while time.monotonic() < deadline:
            task = self.get_task(task_id, mode=mode)
            status = task.get("status", "")
            if status == "SUCCEEDED":
                return task
            if status in ("FAILED", "EXPIRED", "CANCELED"):
                raise MeshyError(f"Task {task_id} ended with status: {status}")
            time.sleep(POLL_INTERVAL_S)

        raise MeshyError(f"Task {task_id} timed out after {max_wait_s}s")

    def get_task(self, task_id: str, mode: str = "image") -> dict[str, Any]:
        """Fetch current task status."""
        if mode not in ("image", "text"):
            raise ValueError("mode must be image or text")
        endpoint = "v2/text-to-3d" if mode == "text" else "v1/image-to-3d"
        try:
            resp = self._client.get(f"/{endpoint}/{task_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise MeshyError(f"Failed to fetch task {task_id}: {exc}") from exc

    def refine_text_task(
        self, preview_task_id: str, enable_pbr: bool = True
    ) -> str:
        """Create refinement only after confirming preview succeeded."""
        task = self.get_task(preview_task_id, mode="text")
        if (
            task.get("status") != "SUCCEEDED"
            or task.get("mode", "preview") != "preview"
        ):
            raise MeshyError("Refinement requires a successful preview task")
        response = self._client.post(
            "/v2/text-to-3d",
            json={
                "mode": "refine",
                "preview_task_id": preview_task_id,
                "enable_pbr": enable_pbr,
            },
        )
        response.raise_for_status()
        return response.json()["result"]

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "MeshyClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
