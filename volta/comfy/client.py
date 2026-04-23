"""VOLTA — ComfyUI API client.

ComfyUI exposes a REST API at http://localhost:8188 (default).
Workflows are JSON files that define a node graph. This client
queues prompts and polls for completion.

Phase 1: Connection test, workflow loading, queue + poll.
Phase 2: Async batch generation, output download, LoRA management.

Usage:
    with ComfyClient() as client:
        if not client.ping():
            raise RuntimeError("ComfyUI not running")
        wf = client.load_workflow(Path("workflows/character_ref.json"))
        prompt_id = client.queue_prompt(wf)
        history = client.wait_for_prompt(prompt_id)
        paths = client.get_output_paths(history)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from volta.models import ComfyError


DEFAULT_HOST = "http://localhost:8188"
POLL_INTERVAL_S = 2.0
MAX_WAIT_S = 600.0    # 10 minutes


class ComfyClient:
    """HTTP client for a running ComfyUI instance."""

    def __init__(self, host: str = DEFAULT_HOST) -> None:
        self.host = host.rstrip("/")
        self._client = httpx.Client(
            base_url=self.host, timeout=30.0
        )

    def ping(self) -> bool:
        """Return True if ComfyUI is reachable."""
        try:
            resp = self._client.get("/system_stats")
            return resp.status_code == 200
        except httpx.TransportError:
            return False

    def load_workflow(self, path: Path) -> dict[str, Any]:
        """Load a workflow JSON file from disk."""
        if not path.exists():
            raise FileNotFoundError(
                f"Workflow not found: {path}"
            )
        with path.open() as f:
            return json.load(f)

    def queue_prompt(
        self,
        workflow: dict[str, Any],
        client_id: str = "volta",
    ) -> str:
        """Queue a workflow prompt. Returns prompt_id."""
        payload = {
            "prompt": workflow,
            "client_id": client_id,
        }
        try:
            resp = self._client.post("/prompt", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ComfyError(
                f"Failed to queue prompt: {exc}"
            ) from exc
        return resp.json()["prompt_id"]

    def wait_for_prompt(
        self,
        prompt_id: str,
        max_wait_s: float = MAX_WAIT_S,
    ) -> dict[str, Any]:
        """Poll until the prompt completes. Returns history entry."""
        elapsed = 0.0
        while elapsed < max_wait_s:
            history = self._get_history(prompt_id)
            if prompt_id in history:
                return history[prompt_id]
            time.sleep(POLL_INTERVAL_S)
            elapsed += POLL_INTERVAL_S
        raise ComfyError(
            f"Prompt {prompt_id} timed out after {max_wait_s}s"
        )

    def get_output_paths(
        self, history_entry: dict[str, Any]
    ) -> list[str]:
        """Extract output file names from a history entry."""
        paths: list[str] = []
        outputs = history_entry.get("outputs", {})
        for node_output in outputs.values():
            for key in ("images", "videos", "gifs"):
                for item in node_output.get(key, []):
                    if "filename" in item:
                        paths.append(item["filename"])
        return paths

    def _get_history(
        self, prompt_id: str
    ) -> dict[str, Any]:
        try:
            resp = self._client.get(
                f"/history/{prompt_id}"
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise ComfyError(
                f"Failed to get history: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "ComfyClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
