# VOLTA

**AI animation pipeline — concept art to game/film export.**

VOLTA orchestrates every stage of a character/environment
production pipeline, connecting AI generation tools, DCC
applications, and delivery targets through a single CLI.

---

## Pipeline Stages

| # | Stage | Tool | Status |
|---|-------|------|--------|
| 0 | Concept art | ComfyUI + SDXL/Flux.1 | Phase 1 |
| 1 | Style consistency | ComfyUI + IP-Adapter | Phase 1 |
| 2 | Image-to-Mesh | Meshy 4 | Phase 1 |
| 3 | Retopology + UV + LOD | ZRemesher / xAtlas | Phase 2 |
| 4 | PBR materials | Meshy + Substance Painter | Phase 2 |
| 5 | Character rigging | AccuRig → MotionBuilder HIK | Phase 1 |
| 6 | Facial animation | iPhone LiveLink + Audio2Face | Phase 2 |
| 7 | Mocap ingest + cleanup | Vicon / Cascadeur | Phase 1 |
| 8 | DCC assembly | MotionBuilder → Maya → UE5 | Phase 2 |
| 9 | AI Blueprints + PCG | UE5 PCG + State Trees | Phase 1 |
| 10 | QA gates | VOLTA validators | Phase 1 |
| 11 | Export routing | FFmpeg / Movie Render Queue | Phase 1 |

---

## Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS/Linux

# 2. Install VOLTA
pip install -e .

# 3. Configure credentials
cp .env.example .env
# Edit .env — add MESHY_API_KEY at minimum

# 4. Verify
python -m volta --help
volta status
```

---

## CLI Reference

```
volta --help           Show all commands
volta status           Catalog statistics
volta generate WF      Run a ComfyUI workflow
volta mesh IMAGE       Image-to-3D via Meshy
volta rig FBX          Auto-rig to HIK (Phase 2 — stub)
volta mocap BVH        Ingest a motion file
volta qa UID           Run QA validators on an asset
volta export FILE      Route a render to a delivery target
volta run UID          Run the full pipeline (Phase 2)
```

---

## Asset Tiers

| Tier | Poly budget | Use case |
|------|-------------|----------|
| HERO | 80k tris | Cinematic close-up characters |
| MID | 10k tris | Background characters, props |
| PROP | 2k tris | Small props, pickups |
| ENVIRONMENT | 200k (pre-Nanite) | Level geometry |

---

## Architecture

```
volta/
├── models.py          Enums, dataclasses, exceptions
├── catalog.py         SQLite catalog (assets, stage runs, QA)
├── cli.py             Click CLI
├── comfy/             ComfyUI HTTP client
├── meshy/             Meshy REST client
├── rigging/           HIK template management
├── mocap/             BVH ingest, Cascadeur stub
├── unreal/            UE5 PCG + Blueprint stubs
├── qa/                Validation gate suite
└── export/            FFmpeg social export + stubs
workflows/             ComfyUI workflow JSON files
templates/
├── hik/               HIK skeleton XML templates
└── mb_scripts/        MotionBuilder Python scripts
tests/                 pytest suite
```

---

## Requirements

- Python 3.11+
- `ffmpeg` on PATH for social export
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
  running locally for generation stages
- [Meshy](https://www.meshy.ai/) API key for mesh stages
- MotionBuilder with HIK for rigging/assembly
- Unreal Engine 5 for PCG + Blueprint + film export
- Cascadeur for mocap cleanup (Phase 2)
- AccuRig for auto-rigging (Phase 2)

---

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check volta/
mypy volta/
```

---

## License

Private — Andy Rose / LSLA. All rights reserved.
