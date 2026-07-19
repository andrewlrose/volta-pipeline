# Volta — Operating Guide

*Fable creative/business portfolio audit — deep pass, 2026-07-07. CLI/script-driven tool.*

## Setup (once per machine)

```powershell
cd E:\dev\projects\Volta
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env    # then fill in MESHY_API_KEY
```

*Plain language: Volta installs like any Python tool. The only account/key it needs today is Meshy (the cloud 3D-model service); everything else runs on this machine. The key lives in `.env`, which is never committed.*

External tools by stage: **ComfyUI** running locally at `http://localhost:8188` for concept art (start it before `volta generate`); **FFmpeg** on PATH for social export; AccuRig/Cascadeur/MotionBuilder/UE5 remain manual (Phase 2 will script them — until then the CLI tells you the manual steps).

## Commands

| Command | Stage | What it does |
|---------|-------|--------------|
| `volta status` | — | Catalog statistics: asset counts by type, stage runs, QA fails/warns. Your dashboard. |
| `volta generate <workflow.json>` | 0–1 Concept | Queues a ComfyUI workflow (e.g. `workflows/bsm_concept_v0.json`), polls to completion, reports output images. |
| `volta mesh <image>` | 2 Mesh | Submits image→3D to Meshy at the tier you choose (`--tier hero/mid/prop/env` sets topology quality), waits, reports result URLs. |
| `volta rig <fbx>` | 5 Rig | Phase 2 stub — prints the manual AccuRig→MotionBuilder HIK workflow. |
| `volta mocap <file>` | 7 Mocap | Validates and parses BVH/FBX/C3D; extracts frame count, fps, duration. |
| `volta mocap-scan <dir>` | 7 Mocap | Batch-ingests a directory of mocap files into the catalog. |
| `volta qa <asset_uid>` | 10 QA | Runs the validator suite (file exists, size sanity, poly budget by tier, stage record) and stores results. |
| `volta export <video> --preset youtube_1080` | 11 Export | FFmpeg transcode with presets: `youtube_4k`, `youtube_1080`, `instagram_reel`, `tiktok`. |
| `volta run <asset_uid>` | — | Advances an asset through its next stage. |
| `volta bridge sync` | — | Recomputes pipeline health and writes `.atlas-bridge/memory.json` for ATLAS (atomic write). |
| `volta bridge status` / `volta bridge tasks` | — | Shows bridge state / lists TaskRequests filed by ATLAS. |

## What "working correctly" looks like

- `python -m pytest` → **25 passed** (~1–2s).
- `volta status` prints a table without errors (an empty catalog shows zeros — that's fine).
- `volta generate` requires ComfyUI to answer at `:8188`; `volta mesh` requires `MESHY_API_KEY`; `volta export` requires `ffmpeg` on PATH. Each fails with a clear message naming exactly what's missing.
- `volta bridge sync` bumps `session_count` and refreshes `last_updated` in `.atlas-bridge/memory.json`.

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `ComfyUI not running` / ping fails | Start ComfyUI locally first; confirm `COMFYUI_HOST` in `.env` if not on `:8188`. |
| `MESHY_API_KEY not set` | Fill it in `.env` (from app.meshy.ai → Settings). |
| Text→3D job "times out" or 404s while polling | Known bug V-2 (client polls the image endpoint for text tasks) — check the job in the Meshy web app; it likely succeeded. |
| "N pending TaskRequest(s)" alert won't clear | Known bug V-3 — the counter ignores task status. Verify with `volta bridge tasks`; trust the task list, not the alert count. |
| `NotImplementedError: ... is Phase 2` | Working as designed — the message includes the manual workflow to use instead. |
| Catalog seems empty on another machine | The catalog currently defaults to `~/.volta/catalog.db` (finding V-1). Set `VOLTA_DB` explicitly per project until the per-project default lands. |

## Manual vs. automated

- **Automated today:** concept generation, mesh submission, mocap parsing, QA checks, social transcode, bridge reporting.
- **Manual today (Phase 2 scope):** rigging (AccuRig), mocap physics cleanup (Cascadeur), facial capture, UE5 assembly/PCG, film/game packaging — the CLI prints step-by-step manual instructions for each.
- **Human-only by rule:** HERO-tier asset promotions (Andy approves), external generation spend (Meshy costs money per job — check the queue before batch runs).
