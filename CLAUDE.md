# VOLTA — Claude Code Context

## What this is
VOLTA is an AI-assisted virtual production pipeline (concept art → game/film delivery) for the boutique studio pitch: ComfyUI/SDXL/Flux concepting, Meshy image-to-3D, AccuRig → MotionBuilder rigging, UE5 assembly, QA gates, and export routing — orchestrated through a single CLI. Built by Andy Rose (mocap post supervisor; Avatar/Lion King/Mufasa lineage).

**Current production:** Bear Suit Man Episode 1 ("Cereal Aisle") — the live proving ground (`BREAKDOWN.md`). **CuddlePirates** is the second demo IP and declares its Volta dependency from its side.

## Read first
1. `README.md` — pipeline stages 0–11, phase status, quick start
2. `BREAKDOWN.md` — BSM Ep1 production breakdown (placeholder sections fill as the 6-week sprint progresses)
3. `PORTFOLIO.md` — pitch-facing summary
4. `.atlas-bridge/` — ATLAS orchestration contract (ProjectsPM)

## Package layout
```
volta/
├── cli.py            ← single CLI entry point
├── catalog.py        ← asset catalog (per-project, see below)
├── models.py         ← dataclass DTOs
├── comfy/            ← Stage 0–1: ComfyUI concept + style consistency
├── meshy/            ← Stage 2: image-to-mesh (MESHY_API_KEY)
├── rigging/          ← Stage 5: AccuRig → MotionBuilder HIK
├── mocap/            ← Stage 7: Vicon/Cascadeur ingest
├── unreal/           ← Stage 9: UE5 PCG + State Trees
├── qa/               ← Stage 10: validators / QA gates
├── export/           ← Stage 11: FFmpeg / Movie Render Queue routing
└── bridge/           ← ATLAS bridge support
```

## Load-bearing decisions
- **Per-project catalogs**: each consuming project owns `.volta/` in its own tree (CuddlePirates Round 2 M3). NOT `~/.volta/`. The catalog is the system of record for assets; the Obsidian vault is for knowledge — don't confuse the two.
- **REFERENCE-tier imports**: concept material lives in OneDrive (`E:/OneDrive/Backup_2023oct22/...`) and is referenced, not copied. **Portability rule:** store references as `{sha256, relative_path, source_root}` with `source_root` a named mount resolved per-machine — absolute Windows paths will not survive the M6 migration.
- **Host split (planned)**: GPU generation workloads (ComfyUI/SDXL/Flux) stay on the Windows GPU box; M6 (always-on Linux server) hosts catalogs, QA reports, and future vault publishing. Choose catalog paths for the right host.
- **Only Andy approves HERO-tier promotions** (mirrors CuddlePirates rule).

## Vault integration (future, by design — not started)
- **Feed:** a `volta vault-export` command publishing per-project catalog summaries as vault notes (`projects/<project>/assets.md`) — one-way published view, like ATLAS_State.md. Reuse ATLAS's `ProjectPageBuilder` pattern; do not invent a new writer.
- **Query:** creative research via Rosie's knowledge_base embeddings once vault sync covers it. Brain-first protocol: check the vault before external references.

## Security
- `MESHY_API_KEY` and service credentials in `.env` only — never committed.
- No PII in scope. Creative IP is pre-pitch confidential: catalog/vault exports default `sensitivity: yellow` (local-LLM-only under the embedding split).

## What NOT to do
- Don't write to the Obsidian vault directly — vault publishing goes through the ATLAS writer patterns when it ships.
- Don't store absolute OneDrive/drive-letter paths in catalogs — hash-addressed references only.
- Don't duplicate concept media into project trees.

<!-- BEGIN UNIFIED SESSION CONTEXT PROTOCOL -->
## Unified Session Context Protocol (Claude, Codex, Antigravity, VS Code Copilot)

### Session Start Protocol (Targeted Read)
1. **Dynamic Session Counter**: Evaluate `global.total_sessions` from `.atlas/memory.json` or `HANDOFF.md §Pick Up Here`. Do not assume session numbers.
2. **Targeted State Read**:
   - Read `HANDOFF.md` §`Pick Up Here` (stop at historical archive).
   - Read `HANDOFF.md` §`Persistent Backlogs` (if present).
   - Read machine state (`.atlas/memory.json` or `.atlas-bridge/` state).
3. **Git State Verification**: Run `git status --short` and `git log -n 5 --oneline` to note recent commits and uncommitted files.
4. **Surface Brief**: Print compact summary (Last Commit, Active Task, Open Backlog Count) and confirm next steps with user.

### Session Close Protocol (State Persistence)
1. **Update Memory State**: Write updated domain/task state to `.atlas/memory.json` (including `last_session_platform` = `claude` | `codex` | `antigravity` | `copilot`).
2. **Update Session Handoff**: Write a clean `(DONE)` summary block (≤ 30 lines) to `HANDOFF.md §Pick Up Here`.
3. **Update Backlogs**: Reconcile open items in tracking backlog files.
4. **Snapshot Audit**: Log immutable session log snapshot via `SessionLogger` (if supported).
<!-- END UNIFIED SESSION CONTEXT PROTOCOL -->
