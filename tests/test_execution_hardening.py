import json
import threading
from unittest.mock import patch

import httpx
import pytest
from click.testing import CliRunner

from volta.bridge.sync import _pending_task_count
from volta.catalog import CatalogDB
from volta.cli import cli
from volta.config import VOLTA_ROOT, resolve_catalog_db_path
from volta.meshy.client import MeshyClient
from volta.models import (
    Asset,
    AssetType,
    CharacterAsset,
    EnvironmentAsset,
    MotionAsset,
    PipelineStage,
    PropAsset,
    ShotAsset,
    SkeletonStandard,
)
from volta.pipeline import catalogued_stage, keyframe_to_video


def test_project_resolution(tmp_path, monkeypatch):
    monkeypatch.delenv("VOLTA_DB_PATH", raising=False)
    assert resolve_catalog_db_path() == VOLTA_ROOT / "catalog.db"
    assert resolve_catalog_db_path(tmp_path) == tmp_path / ".volta/catalog.db"
    (tmp_path / ".volta").mkdir()
    assert (
        resolve_catalog_db_path(tmp_path / "deep")
        == tmp_path / ".volta/catalog.db"
    )
    monkeypatch.setenv("VOLTA_DB_PATH", str(tmp_path / "override.db"))
    assert resolve_catalog_db_path(tmp_path) == tmp_path / "override.db"


@pytest.mark.parametrize(
    "cls,kind,extra",
    [
        (
            CharacterAsset,
            AssetType.CHARACTER,
            {
                "poly_count": 90001,
                "skeleton_standard": SkeletonStandard.METAHUMAN,
            },
        ),
        (PropAsset, AssetType.PROP, {"poly_count": 123}),
        (
            EnvironmentAsset,
            AssetType.ENVIRONMENT,
            {"biome": "forest", "uses_nanite": False},
        ),
        (MotionAsset, AssetType.MOTION, {"fps": 24, "frame_count": 42}),
        (
            ShotAsset,
            AssetType.SHOT,
            {"keyframe_path": "frame.png", "video_path": "clip.mp4"},
        ),
    ],
)
def test_subtype_roundtrip(tmp_path, cls, kind, extra):
    db = CatalogDB(tmp_path / "catalog.db")
    db.init()
    asset = cls(
        "one", "one", kind, PipelineStage.MESH, "mesh.glb", "hash", 42, **extra
    )
    with db.session() as conn:
        db.upsert_asset(conn, asset)
        restored = db.get_asset(conn, asset.uid)
    assert type(restored) is cls
    for key, value in extra.items():
        assert getattr(restored, key) == value
    if cls is CharacterAsset:
        from volta.qa.validators import PolyCountValidator

        assert (
            PolyCountValidator().validate(restored, "run")[0].status.value
            == "fail"
        )


def test_migrate_legacy_catalog(tmp_path):
    db = CatalogDB(tmp_path / "old.db")
    db.init()
    with db.session() as conn:
        for name in ("poly_count", "approval_status", "metadata_json"):
            conn.execute(f"ALTER TABLE assets DROP COLUMN {name}")
        conn.execute(
            "INSERT INTO assets VALUES ('old','old','character','mesh','a','h',10,'mid','[]','','','')"
        )
    db.init()
    db.init()
    with db.session() as conn:
        restored = db.get_asset(conn, "old")
    assert isinstance(restored, CharacterAsset)
    assert restored.approval_status == "pending"


def test_meshy_text_lifecycle():
    calls = []

    def handle(request):
        calls.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content) if request.content else {},
            )
        )
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "result": "preview"
                    if calls[-1][2]["mode"] == "preview"
                    else "refine"
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "SUCCEEDED",
                "mode": "preview"
                if request.url.path.endswith("preview")
                else "refine",
            },
        )

    client = MeshyClient("fake-test-key")
    client._client.close()
    client._client = httpx.Client(
        base_url="https://api.meshy.ai/openapi",
        transport=httpx.MockTransport(handle),
    )
    assert client.text_to_3d("robot") == "preview"
    client.wait_for_task("preview", mode="text")
    assert client.refine_text_task("preview") == "refine"
    client.wait_for_task("refine", mode="text")
    assert all(
        path.startswith("/openapi/v2/text-to-3d") for _, path, _ in calls
    )
    assert calls[0][2]["prompt"] == "robot"
    assert calls[3][2]["preview_task_id"] == "preview"
    client.get_task("image-task")
    assert calls[-1][1] == "/openapi/v1/image-to-3d/image-task"
    client.close()


def test_meshy_failure_and_timeout():
    client = MeshyClient("fake")
    with patch.object(client, "get_task", return_value={"status": "FAILED"}):
        with pytest.raises(Exception, match="FAILED"):
            client.wait_for_task("bad", mode="text")
    with pytest.raises(Exception, match="timed out"):
        client.wait_for_task("bad", max_wait_s=0)
    with patch.object(client, "get_task", return_value={"status": "PENDING"}):
        with pytest.raises(Exception, match="successful preview"):
            client.refine_text_task("bad")
    client.close()


def test_catalog_stage_success_and_failure(tmp_path):
    source = tmp_path / "workflow.json"
    source.write_text("{}")
    output = tmp_path / "frame.png"
    output.write_bytes(b"real-output")
    dbpath = tmp_path / "catalog.db"
    with catalogued_stage(
        dbpath, source, PipelineStage.KEYFRAME, "mock"
    ) as paths:
        paths.append(output)
    with pytest.raises(RuntimeError):
        with catalogued_stage(dbpath, source, PipelineStage.KEYFRAME, "mock"):
            raise RuntimeError("failure")
    db = CatalogDB(dbpath)
    with db.session() as conn:
        statuses = [
            r[0] for r in conn.execute("SELECT status FROM stage_runs")
        ]
        assert sorted(statuses) == ["failed", "success"]
        assert any(
            a.file_path == str(output.resolve())
            for a in db.get_all_assets(conn)
        )


def test_vision_does_not_block_video(tmp_path):
    release = threading.Event()
    events = []

    def checker(paths):
        release.wait(3)
        raise RuntimeError("offline")

    def video(paths):
        events.append("video")
        assert not release.is_set()
        return ["clip"]

    result, future = keyframe_to_video(
        lambda: [tmp_path / "frame"],
        video,
        vision_qc=True,
        report=tmp_path / "qc.json",
        checker=checker,
    )
    assert result == ["clip"] and events == ["video"]
    release.set()
    assert future.result(timeout=4)["status"] == "unavailable"


def test_pending_count(tmp_path):
    (tmp_path / "tasks.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"status": status})
                for status in ["pending", "in_progress", "done", "rejected"]
            ]
        )
        + "\ninvalid\n[]"
    )
    assert _pending_task_count(tmp_path) == 2


def test_cli_dynamic_db_and_approval(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VOLTA_DB_PATH", raising=False)
    result = CliRunner().invoke(cli, ["status"])
    assert result.exit_code == 0, result.output
    db = CatalogDB(tmp_path / ".volta/catalog.db")
    with db.session() as conn:
        db.upsert_asset(
            conn,
            Asset(
                "one", "one", AssetType.PROP, PipelineStage.MESH, "a", "h", 1
            ),
        )
    for command, expected in [("approve", "approved"), ("reject", "rejected")]:
        assert CliRunner().invoke(cli, [command, "one"]).exit_code == 0
        with db.session() as conn:
            assert db.get_asset(conn, "one").approval_status == expected


def test_cli_generate_registers_downloads(tmp_path):
    workflow = tmp_path / "workflow.json"
    workflow.write_text("{}")
    output = tmp_path / "frame.png"
    output.write_bytes(b"generated bytes")
    with patch("volta.comfy.client.ComfyClient") as client:
        instance = client.return_value.__enter__.return_value
        instance.ping.return_value = True
        instance.download_outputs.return_value = [output]
        result = CliRunner().invoke(
            cli,
            ["generate", str(workflow), "--db", str(tmp_path / "catalog.db")],
        )
    assert result.exit_code == 0, repr(result.exception)
    db = CatalogDB(tmp_path / "catalog.db")
    with db.session() as conn:
        assets = db.get_all_assets(conn)
        assert len(assets) == 1 and assets[0].file_path == str(
            output.resolve()
        )
        assert db.get_stage_runs(conn, assets[0].uid)[0].status == "success"


def test_cli_mesh_text_refines_and_catalogues(tmp_path):
    class Download:
        content = b"fake mesh fixture"

        def raise_for_status(self):
            pass

    with (
        patch("volta.meshy.client.MeshyClient") as client,
        patch("httpx.get", return_value=Download()),
    ):
        instance = client.return_value.__enter__.return_value
        instance.text_to_3d.return_value = "preview"
        instance.refine_text_task.return_value = "refine"
        instance.wait_for_task.return_value = {
            "model_urls": {"glb": "https://example.invalid/mesh"}
        }
        result = CliRunner().invoke(
            cli,
            [
                "mesh",
                "--mode",
                "text",
                "--prompt",
                "robot",
                "--out-dir",
                str(tmp_path / "out"),
                "--db",
                str(tmp_path / "catalog.db"),
            ],
        )
    assert result.exit_code == 0, repr(result.exception)
    instance.refine_text_task.assert_called_once_with("preview")
    assert (tmp_path / "out/refine.glb").read_bytes() == b"fake mesh fixture"
    db = CatalogDB(tmp_path / "catalog.db")
    with db.session() as conn:
        assert db.stats(conn)["stage_runs"] == 1
        assert db.get_all_assets(conn)[0].stage == PipelineStage.MESH


def test_project_resolution_uses_git_root_before_first_catalog(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("VOLTA_DB_PATH", raising=False)
    (tmp_path / ".git").mkdir()
    assert (
        resolve_catalog_db_path(tmp_path / "nested")
        == tmp_path / ".volta/catalog.db"
    )


def test_qc_report_failure_does_not_gate_video(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("fixture")
    result, future = keyframe_to_video(
        lambda: [tmp_path / "frame"],
        lambda paths: ["video"],
        vision_qc=True,
        report=blocker / "qc.json",
    )
    assert result == ["video"]
    assert future.result()["status"] == "unavailable"
