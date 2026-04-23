"""VOLTA — Click CLI entry point."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from volta.catalog import CatalogDB
from volta.models import PipelineStage
from volta.qa.validators import qa_passed, run_qa_suite


console = Console()
DEFAULT_DB = Path.home() / ".volta" / "catalog.db"


@click.group()
@click.version_option(package_name="volta")
def cli() -> None:
    """VOLTA — AI animation pipeline orchestrator."""


# ── status ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--db",
    type=click.Path(),
    default=str(DEFAULT_DB),
    show_default=True,
    help="Catalog database path.",
)
def status(db: str) -> None:
    """Show pipeline catalog statistics."""
    catalog = CatalogDB(Path(db))
    catalog.init()
    with catalog.session() as conn:
        s = catalog.stats(conn)
    t = Table(title="VOLTA Catalog", show_header=True)
    t.add_column("Metric", style="cyan")
    t.add_column("Count", justify="right")
    t.add_row("Total assets", str(s["total_assets"]))
    t.add_row("  Characters", str(s["characters"]))
    t.add_row("  Environments", str(s["environments"]))
    t.add_row("  Motions", str(s["motions"]))
    t.add_row("  Props", str(s["props"]))
    t.add_row("Stage runs", str(s["stage_runs"]))
    t.add_row(
        "QA fails",
        f"[red]{s['qa_fails']}[/red]"
        if s["qa_fails"]
        else "0",
    )
    t.add_row(
        "QA warns",
        f"[yellow]{s['qa_warns']}[/yellow]"
        if s["qa_warns"]
        else "0",
    )
    console.print(t)


# ── generate ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument(
    "workflow", type=click.Path(exists=True, path_type=Path)
)
@click.option(
    "--host",
    default="http://localhost:8188",
    show_default=True,
    help="ComfyUI instance URL.",
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("."),
    show_default=True,
    help="Output directory for generated images.",
)
@click.option(
    "--db", type=click.Path(), default=str(DEFAULT_DB)
)
def generate(
    workflow: Path,
    host: str,
    out_dir: Path,
    db: str,
) -> None:
    """Run a ComfyUI generation workflow (Stage 0 — Concept)."""
    from volta.comfy.client import ComfyClient

    with ComfyClient(host=host) as client:
        if not client.ping():
            console.print(
                f"[red]ERROR[/red] ComfyUI not reachable "
                f"at {host}"
            )
            console.print(
                "  Start ComfyUI: python main.py --port 8188"
            )
            sys.exit(1)
        console.print(
            f"[cyan]Loading workflow:[/cyan] {workflow}"
        )
        wf = client.load_workflow(workflow)
        console.print("[cyan]Queuing prompt...[/cyan]")
        prompt_id = client.queue_prompt(wf)
        console.print(
            f"[cyan]Waiting for[/cyan] {prompt_id[:8]}..."
        )
        history = client.wait_for_prompt(prompt_id)
        paths = client.get_output_paths(history)
    if paths:
        console.print(
            f"[green]Done.[/green] {len(paths)} output(s):"
        )
        for p in paths:
            console.print(f"  {p}")
    else:
        console.print(
            "[yellow]Workflow complete — no outputs found."
            "[/yellow]"
        )


# ── mesh ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument(
    "image", type=click.Path(exists=True, path_type=Path)
)
@click.option(
    "--tier",
    type=click.Choice(["hero", "mid", "prop", "env"]),
    default="mid",
    show_default=True,
    help="Asset quality tier.",
)
@click.option(
    "--mode",
    type=click.Choice(["image", "text"]),
    default="image",
    show_default=True,
)
@click.option(
    "--prompt",
    default="",
    help="Text prompt (required with --mode text).",
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("."),
)
@click.option(
    "--db", type=click.Path(), default=str(DEFAULT_DB)
)
def mesh(
    image: Path,
    tier: str,
    mode: str,
    prompt: str,
    out_dir: Path,
    db: str,
) -> None:
    """Convert an image or prompt to 3D mesh via Meshy (Stage 2)."""
    from volta.meshy.client import MeshyClient
    from volta.models import AssetTier

    tier_enum = AssetTier(tier)
    with MeshyClient() as client:
        if mode == "image":
            console.print(
                f"[cyan]Submitting image-to-3D:[/cyan] {image}"
            )
            task_id = client.image_to_3d(image, tier=tier_enum)
        else:
            if not prompt:
                console.print(
                    "[red]ERROR[/red] --prompt required for "
                    "text mode."
                )
                sys.exit(1)
            task_id = client.text_to_3d(
                prompt, tier=tier_enum
            )
        console.print(
            f"[cyan]Task submitted:[/cyan] {task_id}"
        )
        console.print(
            "[cyan]Polling for completion...[/cyan]"
        )
        task = client.wait_for_task(task_id)
    model_urls = task.get("model_urls", {})
    console.print("[green]Done.[/green] Model URLs:")
    for fmt, url in model_urls.items():
        console.print(f"  {fmt}: {url}")


# ── rig ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument(
    "fbx_path", type=click.Path(exists=True, path_type=Path)
)
@click.option(
    "--skeleton",
    type=click.Choice(
        ["hik", "ue_mannequin", "metahuman", "custom"]
    ),
    default="hik",
    show_default=True,
    help="Target skeleton standard.",
)
@click.option(
    "--db", type=click.Path(), default=str(DEFAULT_DB)
)
def rig(fbx_path: Path, skeleton: str, db: str) -> None:
    """Auto-rig an FBX mesh to HIK (Stage 5). [Phase 2]"""
    console.print(
        "[yellow]NOTE[/yellow] AccuRig CLI integration is "
        "Phase 2."
    )
    console.print(
        "  Rig manually in AccuRig, export HIK FBX, "
        "then import to MotionBuilder."
    )
    console.print(f"  Input: {fbx_path}")
    console.print(f"  Target skeleton: {skeleton}")


# ── mocap ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument(
    "motion_file",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--clean",
    is_flag=True,
    default=False,
    help="Run Cascadeur cleanup (Phase 2).",
)
@click.option(
    "--db", type=click.Path(), default=str(DEFAULT_DB)
)
def mocap(
    motion_file: Path, clean: bool, db: str
) -> None:
    """Ingest a BVH or FBX motion file (Stage 7)."""
    from volta.mocap.ingest import ingest_bvh, validate_mocap_file

    validate_mocap_file(motion_file)
    if motion_file.suffix.lower() == ".bvh":
        meta = ingest_bvh(motion_file)
        console.print(
            f"[green]BVH parsed:[/green] "
            f"{meta['frame_count']} frames @ "
            f"{meta['fps']} fps "
            f"({meta['duration_s']:.1f}s)"
        )
    else:
        console.print(
            f"[cyan]FBX ingest:[/cyan] {motion_file}"
        )
        console.print(
            "  FBX metadata extraction is Phase 2."
        )
    if clean:
        console.print(
            "[yellow]NOTE[/yellow] Cascadeur cleanup is Phase 2."
        )


# ── qa ────────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("asset_uid")
@click.option(
    "--db", type=click.Path(), default=str(DEFAULT_DB)
)
def qa(asset_uid: str, db: str) -> None:
    """Run QA validation suite on a catalog asset."""
    catalog = CatalogDB(Path(db))
    catalog.init()
    with catalog.session() as conn:
        asset = catalog.get_asset(conn, asset_uid)
        if asset is None:
            console.print(
                f"[red]ERROR[/red] Asset not found: {asset_uid}"
            )
            sys.exit(1)
        results = run_qa_suite(asset)
        for result in results:
            colour = {
                "pass": "green",
                "warn": "yellow",
                "fail": "red",
                "skip": "dim",
            }.get(result.status.value, "white")
            console.print(
                f"  [{colour}]"
                f"{result.status.value.upper():4}"
                f"[/{colour}]  "
                f"{result.check_name}: {result.detail}"
            )
            catalog.record_qa_result(conn, result)
        passed = qa_passed(results)
    if passed:
        console.print("[green]QA PASSED[/green]")
    else:
        console.print("[red]QA FAILED[/red]")
        sys.exit(1)


# ── export ────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument(
    "input_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--target",
    type=click.Choice(
        ["social", "film", "game", "web", "vr"]
    ),
    default="social",
    show_default=True,
    help="Delivery target.",
)
@click.option(
    "--preset",
    default="youtube_1080",
    show_default=True,
    help="Social preset (youtube_4k, instagram_reel, tiktok).",
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("."),
)
def export(
    input_path: Path,
    target: str,
    preset: str,
    out_dir: Path,
) -> None:
    """Route a render to a delivery target (Stage 11)."""
    from volta.export.router import export_social
    from volta.models import ExportTarget

    tgt = ExportTarget(target)
    if tgt == ExportTarget.SOCIAL:
        out_path = export_social(
            input_path, out_dir, preset=preset
        )
        console.print(
            f"[green]Exported:[/green] {out_path}"
        )
    else:
        console.print(
            f"[yellow]NOTE[/yellow] "
            f"'{target}' export is Phase 2."
        )


# ── run (full pipeline) ───────────────────────────────────────────────────────

@cli.command()
@click.argument("asset_uid")
@click.option(
    "--from-stage",
    type=click.Choice([s.value for s in PipelineStage]),
    default=None,
    help="Resume pipeline from a specific stage.",
)
@click.option(
    "--db", type=click.Path(), default=str(DEFAULT_DB)
)
def run(
    asset_uid: str,
    from_stage: Optional[str],
    db: str,
) -> None:
    """Run (or resume) the full pipeline for an asset."""
    catalog = CatalogDB(Path(db))
    catalog.init()
    with catalog.session() as conn:
        asset = catalog.get_asset(conn, asset_uid)
    if asset is None:
        console.print(
            f"[red]ERROR[/red] Asset not found: {asset_uid}"
        )
        sys.exit(1)
    console.print(
        f"[cyan]VOLTA pipeline:[/cyan] {asset.name} "
        f"({asset_uid[:8]})"
    )
    console.print(
        f"  Current stage: {asset.stage.value}"
    )
    if from_stage:
        console.print(f"  Resuming from: {from_stage}")
    console.print(
        "[yellow]Full pipeline orchestration is Phase 2.[/yellow]"
    )
    console.print(
        "  Use individual commands per stage: "
        "generate → mesh → rig → mocap → qa → export"
    )
