"""Tests for volta.comfy.client — ComfyUI HTTP client."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import httpx

from volta.comfy.client import ComfyClient
from volta.models import ComfyError


# ── fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_WORKFLOW: dict = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "flux1-dev.safetensors"},
    },
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "test prompt", "clip": ["1", 1]},
    },
}


@pytest.fixture()
def workflow_file(tmp_path: Path) -> Path:
    """Write a sample workflow JSON to a temp file."""
    p = tmp_path / "test_workflow.json"
    p.write_text(json.dumps(SAMPLE_WORKFLOW))
    return p


# ── ping ──────────────────────────────────────────────────────────────────────

class TestPing:
    def test_ping_returns_true_on_200(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch.object(
            ComfyClient,
            "__init__",
            lambda self, host="http://localhost:8188": None,
        ):
            client = ComfyClient.__new__(ComfyClient)
            client.host = "http://localhost:8188"
            mock_http = MagicMock()
            mock_http.get.return_value = mock_resp
            client._client = mock_http
            assert client.ping() is True

    def test_ping_returns_false_on_transport_error(
        self,
    ) -> None:
        with patch.object(
            ComfyClient,
            "__init__",
            lambda self, host="http://localhost:8188": None,
        ):
            client = ComfyClient.__new__(ComfyClient)
            client.host = "http://localhost:8188"
            mock_http = MagicMock()
            mock_http.get.side_effect = (
                httpx.TransportError("no route")
            )
            client._client = mock_http
            assert client.ping() is False


# ── load_workflow ─────────────────────────────────────────────────────────────

class TestLoadWorkflow:
    def test_loads_valid_json(
        self, workflow_file: Path
    ) -> None:
        client = ComfyClient.__new__(ComfyClient)
        client.host = "http://localhost:8188"
        client._client = MagicMock()
        wf = client.load_workflow(workflow_file)
        assert "1" in wf
        assert wf["1"]["class_type"] == (
            "CheckpointLoaderSimple"
        )

    def test_missing_file_raises(
        self, tmp_path: Path
    ) -> None:
        client = ComfyClient.__new__(ComfyClient)
        client.host = "http://localhost:8188"
        client._client = MagicMock()
        with pytest.raises(FileNotFoundError):
            client.load_workflow(tmp_path / "ghost.json")


# ── queue_prompt ──────────────────────────────────────────────────────────────

class TestQueuePrompt:
    def test_returns_prompt_id(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "prompt_id": "abc123"
        }

        client = ComfyClient.__new__(ComfyClient)
        client.host = "http://localhost:8188"
        mock_http = MagicMock()
        mock_http.post.return_value = mock_resp
        client._client = mock_http

        prompt_id = client.queue_prompt(SAMPLE_WORKFLOW)
        assert prompt_id == "abc123"

    def test_raises_on_http_error(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = (
            httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            )
        )

        client = ComfyClient.__new__(ComfyClient)
        client.host = "http://localhost:8188"
        mock_http = MagicMock()
        mock_http.post.return_value = mock_resp
        client._client = mock_http

        with pytest.raises(ComfyError):
            client.queue_prompt(SAMPLE_WORKFLOW)
