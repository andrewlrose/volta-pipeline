"""VOLTA — Click CLI entry point."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from volta.catalog import CatalogDB
from volta.models import AssetType, PipelineStage
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


# ── mocap-scan ────────────────────────────────────────────────────────────────

@cli.command("mocap-scan")
@click.argument(
    "library_dir",
    type=click.Path(
        exists=True, file_okay=False, path_type=Path
    ),
)
@click.option(
    "--db",
    type=click.Path(),
    default=str(DEFAULT_DB),
    show_default=True,
    help="Catalog database path.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print results without writing to catalog.",
)
def mocap_scan(
    library_dir: Path, db: str, dry_run: bool
) -> None:
    """Bulk-register BVH/FBX motions from a library directory."""
    from volta.mocap.ingest import (
        SUPPORTED_FORMATS,
        ingest_bvh,
    )
    from volta.models import Asset, AssetTier

    files = sorted(
        f
        for f in library_dir.rglob("*")
        if f.is_file()
        and f.suffix.lower() in SUPPORTED_FORMATS
    )

    if not files:
        console.print(
            f"[yellow]No motion files found in:[/yellow] "
            f"{library_dir}"
        )
        return

    t = Table(
        title=f"Mocap Library — {library_dir}",
        show_header=True,
    )
    t.add_column("Name", style="cyan")
    t.add_column("Fmt", no_wrap=True)
    t.add_column("Frames", justify="right")
    t.add_column("FPS", justify="right")
    t.add_column("Duration", justify="right")
    t.add_column("Status")

    catalog = CatalogDB(Path(db))
    if not dry_run:
        catalog.init()

    registered = 0
    errors = 0

    for motion_file in files:
        suffix = motion_file.suffix.lower()
        frames_str = fps_str = dur_str = "—"
        try:
            notes = ""
            if suffix == ".bvh":
                meta = ingest_bvh(motion_file)
                frames_str = str(meta["frame_count"])
                fps_str = f"{meta['fps']:.0f}"
                dur_str = f"{meta['duration_s']:.1f}s"
                notes = (
                    f"{meta['frame_count']} frames "
                    f"@ {meta['fps']:.0f} fps "
                    f"({meta['duration_s']:.1f}s)"
                )

            if not dry_run:
                h = hashlib.sha256()
                with motion_file.open("rb") as fh:
                    h.update(fh.read(65_536))
                file_hash = h.hexdigest()

                asset = Asset(
                    uid=Asset.uid_from_path(motion_file),
                    name=motion_file.stem,
                    asset_type=AssetType.MOTION,
                    stage=PipelineStage.MOCAP,
                    file_path=str(motion_file.resolve()),
                    file_hash=file_hash,
                    file_size=motion_file.stat().st_size,
                    tier=AssetTier.MID,
                    notes=notes,
                )
                with catalog.session() as conn:
                    catalog.upsert_asset(conn, asset)
                registered += 1
                status_str = "[green]registered[/green]"
            else:
                status_str = "[dim]dry-run[/dim]"

        except Exception as exc:  # noqa: BLE001
            errors += 1
            status_str = f"[red]ERROR: {exc}[/red]"

        t.add_row(
            motion_file.stem,
            suffix.lstrip(".").upper(),
            frames_str,
            fps_str,
            dur_str,
            status_str,
        )

    console.print(t)
    if not dry_run:
        console.print(
            f"\n[green]Done.[/green] "
            f"{registered} registered, {errors} errors."
        )
    else:
        console.print(
            f"\n[dim]Dry run — {len(files)} files found, "
            f"none written to catalog.[/dim]"
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


# ── bridge (ATLAS integration) ────────────────────────────────────────────────

@cli.group()
def bridge() -> None:
    """ATLAS ↔ VOLTA bridge — status reporting and task dispatch."""


@bridge.command(name="sync")
@click.option(
    "--db",
    type=click.Path(),
    default=str(DEFAULT_DB),
    show_default=True,
    help="Catalog database path.",
)
def bridge_sync(db: str) -> None:
    """Update .atlas-bridge/memory.json with current state.

    ATLAS reads this file on every ``python main.py bridge-sync``
    run. Call this after any significant pipeline work to keep
    ATLAS informed.
    """
    from volta.bridge.sync import sync

    memory = sync(db_path=Path(db))
    health = memory.get("health", {})
    console.print(
        f"[green]Bridge synced.[/green]  "
        f"Health: {health.get('status', '?')}  |  "
        f"Assets: {memory['metrics']['total_assets']}  |  "
        f"Stage runs: {memory['metrics']['stage_runs']}"
    )
    alerts = memory.get("alerts", [])
    for a in alerts:
        icon = (
            "[red]●[/red]"
            if a["severity"] == "critical"
            else "[yellow]●[/yellow]"
            if a["severity"] == "warning"
            else "[cyan]●[/cyan]"
        )
        console.print(f"  {icon} {a['message']}")


@bridge.command(name="status")
def bridge_status() -> None:
    """Print the current .atlas-bridge/memory.json (what ATLAS sees)."""
    from volta.bridge.sync import _BRIDGE_DIR
    import json as _json

    mem_path = _BRIDGE_DIR / "memory.json"
    man_path = _BRIDGE_DIR / "manifest.json"
    if not mem_path.exists():
        console.print(
            "[red]ERROR[/red] memory.json not found. "
            "Run: volta bridge sync"
        )
        sys.exit(1)

    with mem_path.open("r", encoding="utf-8") as f:
        memory = _json.load(f)
    with man_path.open("r", encoding="utf-8") as f:
        manifest = _json.load(f)

    health = memory.get("health", {})
    t = Table(
        title="VOLTA Bridge Status", show_header=True
    )
    t.add_column("Field", style="cyan")
    t.add_column("Value")
    t.add_row("Project", manifest.get("project_name", "?"))
    t.add_row("Status", memory.get("status_summary", "?"))
    t.add_row(
        "Health", health.get("status", "unknown")
    )
    t.add_row(
        "Days since push",
        str(health.get("days_since_push", -1)),
    )
    t.add_row(
        "Last updated",
        memory.get("last_updated", "never"),
    )
    t.add_row(
        "Last ATLAS sync",
        memory.get("last_atlas_sync") or "not yet",
    )
    t.add_row(
        "Sessions",
        str(memory.get("session_count", 0)),
    )
    t.add_row(
        "Open tasks",
        str(len(memory.get("open_tasks", []))),
    )
    console.print(t)

    alerts = memory.get("alerts", [])
    if alerts:
        console.print("\n[bold]Alerts:[/bold]")
        for a in alerts:
            icon = (
                "[red]CRIT[/red]"
                if a["severity"] == "critical"
                else "[yellow]WARN[/yellow]"
                if a["severity"] == "warning"
                else "[cyan]INFO[/cyan]"
            )
            state = (
                "[dim](resolved)[/dim]"
                if a.get("resolved")
                else ""
            )
            console.print(
                f"  {icon} {a['message']} {state}"
            )

    caps = manifest.get("capabilities", [])
    if caps:
        console.print(
            f"\n[dim]Capabilities: "
            f"{', '.join(caps)}[/dim]"
        )


@bridge.command(name="tasks")
def bridge_tasks() -> None:
    """List pending TaskRequests dispatched from ATLAS."""
    from volta.bridge.sync import read_tasks

    tasks = read_tasks()
    if not tasks:
        console.print(
            "[dim]No pending tasks from ATLAS.[/dim]"
        )
        return
    t = Table(
        title=f"ATLAS Tasks ({len(tasks)})",
        show_header=True,
    )
    t.add_column("ID", style="dim")
    t.add_column("Priority")
    t.add_column("Title")
    t.add_column("Created")
    for task in tasks:
        t.add_row(
            task.get("task_id", "?")[:12],
            task.get("priority", "normal"),
            task.get("title", ""),
            task.get("created_at", "")[:10],
        )
    console.print(t)


# ── bridge exec ───────────────────────────────────────────────────────────────


def _task_id(task: dict) -> str:
    """Return the task identifier regardless of which key ATLAS used."""
    return task.get("id") or task.get("task_request_id", "")


def _task_text(task: dict) -> str:
    """Return the human-readable task description."""
    return task.get("task") or task.get("title") or "(no description)"


@bridge.command(name="exec")
@click.option(
    "--done",
    default=None,
    metavar="TASK_ID",
    help="Mark a task as done by its ID prefix.",
)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    help="Poll every 10s and print new tasks as they arrive.",
)
def bridge_exec(done: Optional[str], watch: bool) -> None:
    """Process pending ATLAS tasks — print briefs and mark in-progress.

    On each run this command:

    1. Reads all tasks in .atlas-bridge/tasks.jsonl
    2. Prints every ``pending`` task with its full brief
    3. Marks each found pending task as ``in_progress``

    Open this project in VS Code (``code .``) and start a Copilot
    session to execute the brief shown.  When the work is done,
    run::

        volta bridge exec --done <TASK_ID>

    to mark the task ``done`` so the ATLAS receipt strip updates.

    Use ``--watch`` to keep polling for new tasks every 10s
    (useful when ATLAS is actively dispatching).
    """
    import time as _time
    from volta.bridge.sync import read_tasks, update_task_status

    if done:
        # Mark a specific task done
        tasks = read_tasks()
        match = next(
            (t for t in tasks if _task_id(t).startswith(done)),
            None,
        )
        if match is None:
            console.print(
                f"[red]No task found matching ID prefix:[/red] {done}"
            )
            sys.exit(1)
        tid = _task_id(match)
        if update_task_status(tid, "done"):
            console.print(
                f"[green]Marked done:[/green] {tid[:16]}…"
            )
            console.print(
                f"  Task: {_task_text(match)[:80]}"
            )
        else:
            console.print(
                f"[red]Could not update status for[/red] {tid}"
            )
        return

    seen_ids: set[str] = set()

    def _process_once() -> int:
        tasks = read_tasks()
        pending = [
            t for t in tasks
            if t.get("status") == "pending"
            and _task_id(t) not in seen_ids
        ]
        for task in pending:
            tid = _task_id(task)
            seen_ids.add(tid)
            update_task_status(tid, "in_progress")
            console.rule(
                f"[bold cyan]ATLAS Task[/bold cyan] "
                f"[dim]{tid[:16]}[/dim]"
            )
            console.print(
                f"[bold]Project:[/bold] "
                f"{task.get('project', 'VOLTA')}"
            )
            console.print(
                f"[bold]Dispatched:[/bold] "
                f"{task.get('created_at', '')[:16]} UTC"
            )
            console.print(
                f"[bold]Priority:[/bold] "
                f"{task.get('priority', 'normal')}"
            )
            console.print()
            console.print(
                "[bold]Brief:[/bold]"
            )
            console.print(_task_text(task))
            console.print()
            console.print(
                "[dim]Status set to in_progress. "
                "Run `volta bridge exec --done "
                f"{tid[:8]}` when complete.[/dim]"
            )
        return len(pending)

    found = _process_once()
    if found == 0 and not watch:
        console.print(
            "[dim]No pending ATLAS tasks.[/dim]"
        )
        return

    if watch:
        console.print(
            "[dim]Watching for new tasks "
            "(Ctrl-C to stop)...[/dim]"
        )
        try:
            while True:
                _time.sleep(10)
                _process_once()
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/dim]")
