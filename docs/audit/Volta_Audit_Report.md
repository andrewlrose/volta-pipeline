# Volta — Audit Report

*Fable creative/business portfolio audit — deep pass, 2026-07-07. Supersedes the 2026-07-07 19:36 shallow draft.*

## Executive Summary

Volta is SOFTWARE — confirmed: a real, installable Python package (~3,270 lines, 9 git commits, GitHub remote) implementing an AI-assisted virtual-production pipeline CLI. Phase 1 is honestly built and honestly scoped: working ComfyUI and Meshy clients, BVH mocap ingest, SQLite asset catalog, composable QA gates, FFmpeg social export, and an ATLAS bridge with proper atomic writes — while every Phase 2 feature is an explicit `NotImplementedError` stub with manual-workflow instructions instead of pretend code. All 25 tests pass (verified live in the audit sandbox). Repo hygiene is good: caches gitignored, secrets in `.env` only, remote configured. The real findings are three correctness/drift issues: the catalog default still points at `~/.volta/` despite the project's own load-bearing "per-project `.volta/`" decision; the Meshy client polls the wrong endpoint for text-to-3D tasks; and the bridge counts *every* task in `tasks.jsonl` as pending forever, ignoring the status field its own updater writes.

## Findings

| # | Issue | Location | Category | Severity | Recommended action | Status |
|---|-------|----------|----------|----------|--------------------|--------|
| V-1 | **Catalog path contradicts the project's own load-bearing decision.** CLAUDE.md: per-project catalogs in each consumer's `.volta/`, "NOT `~/.volta/`". Code defaults: `cli.py:20 DEFAULT_DB = Path.home()/".volta"/catalog.db`, `bridge/sync.py _DEFAULT_DB`, `.env.example VOLTA_DB=~/.volta/catalog.db`. Same class of drift as ATLAS's OBSIDIAN_VAULT_DIR lesson (one env var, one meaning). | `volta/cli.py:20`, `volta/bridge/sync.py`, `.env.example` | architecture / data-ownership | **Medium** | Introduce one shared resolver (project-root `.volta/` default, `VOLTA_DB` override) and import it everywhere — mirror ATLAS's `vault_env.py` pattern. | Flagged — config/behavior change |
| V-2 | **Meshy client polls the wrong endpoint for text tasks.** `text_to_3d()` posts to `/v2/text-to-3d`, but `get_task()` (used by `wait_for_task`) always GETs `/v1/image-to-3d/{id}` — waiting on a text-to-3D task will 404/fail. | `volta/meshy/client.py` `get_task()` | deps-tests / external API | **Medium** | Track task type per submission (or accept an endpoint arg) and poll the matching endpoint. | Flagged — external API call |
| V-3 | **Bridge "pending tasks" alert never clears.** `_pending_task_count()` counts every non-empty line of `tasks.jsonl` as pending; it never reads the `status` field that `update_task_status()` writes into the very same file. Completed tasks raise the "pending TaskRequest(s) from ATLAS" alert forever. | `volta/bridge/sync.py` `_pending_task_count()` | dead code / correctness | **Medium** | Parse each line and count only non-terminal statuses (e.g. not `done`/`dismissed`). | Flagged — behavior change |
| V-4 | **Deprecated/inconsistent timestamps.** `datetime.utcnow()` (deprecated in 3.12+) in `catalog.py` and `qa/validators.py`; `compute_memory()` stamps `last_updated` with naive local `datetime.now()` while `_git_days_since_push` uses tz-aware UTC. | `volta/catalog.py`, `volta/qa/validators.py`, `volta/bridge/sync.py` | deps-tests | Low | Standardize on `datetime.now(timezone.utc)`. | Flagged — touches stored data formats |
| V-5 | **Local-first: one hard cloud dependency (Meshy), correctly isolated.** ComfyUI is local-GPU; Meshy image/text→3D is cloud-only, confined to its own module but with no provider-neutral interface. Phase-2 keys (OpenAI/Anthropic/DeepMotion…) are placeholders only — no LLM calls exist yet. | `volta/meshy/client.py`, `.env.example` | local-first | Low | Cheap now: define a `MeshProvider` protocol so Meshy is one implementation; note local alternatives (e.g. TripoSR-class models) for the hardware-upgrade era. Any future LLM call goes through a gateway, never inline. | Flagged — roadmap `[Local-First]` |
| V-6 | **Catalog stores raw `file_path` strings; portability rule not yet enforced in schema.** CLAUDE.md requires `{sha256, relative_path, source_root}` references (named mounts, no absolute Windows paths) — the `assets` table has `file_path TEXT` and callers pass whatever they have. Absolute `E:\...` paths won't survive the M6 migration. | `volta/catalog.py` schema, `volta/models.py` | data-ownership | **Medium** | Add `source_root` + relative-path columns (or normalize on write) before the catalog accumulates real assets — cheap now, painful later. | Flagged — schema change |
| V-7 | **Positive: atomic writes done right.** `write_memory()` and `update_task_status()` both use tempfile + `Path.replace()` — the household writer discipline, already implemented here. Honest Phase-2 stubs (`NotImplementedError` + manual steps) instead of silent no-ops. | `volta/bridge/sync.py` | architecture | Info | Use this module as the reference pattern for Writers_Room's WR-2 fix. | No action needed |
| V-8 | **Sandbox git status shows every tracked file as modified** — consistent with the documented CRLF/Linux↔NTFS mount artifact (ATLAS S269 saw 585 phantom modifications). | repo root | deps-tests | Info | Verify with native `git status` before any commit; expect a short real list. | Flagged for native verification |

### Plain-language layer, finding by finding

- **V-1:** The project wrote down a rule for itself — "each production keeps its own asset catalog inside its own folder" — but the code still drops the catalog into a single shared folder in the user's home directory. The household has been burned by exactly this kind of "one path, two meanings" drift before (the Obsidian vault variable). Fix it while the catalog is nearly empty.
- **V-2:** Ask Volta to generate a 3D model from *text* and it submits the job fine — then checks on it at the *image* jobs counter. The job succeeds on Meshy's side, but Volta would wait, get "no such job," and report failure.
- **V-3:** The to-do inbox from ATLAS never empties: even after a task is marked done, the alert still says it's waiting. Annoying rather than dangerous, but it trains you to ignore alerts — which *is* dangerous.
- **V-4:** Two slightly different clocks are used for record-keeping. Harmless today; confusing when comparing timestamps across machines later.
- **V-5:** Of everything Volta talks to, only Meshy (the 3D-model generator) lives in the cloud. It's neatly boxed into one file, which is 90% of the battle — the last 10% is a formal "any mesh generator can plug in here" interface so a future local model is a drop-in.
- **V-6:** The asset catalog remembers files by their full Windows address (like `E:\OneDrive\...`). Move to the Linux server and every address breaks. The project's own docs already say to store portable references — the database just doesn't enforce it yet.
- **V-7:** Good news: the file-writing safety habit ATLAS uses everywhere is already implemented correctly here. Other projects in this portfolio should copy this file.
- **V-8:** The sandbox's view of git claims everything changed; that's a known illusion caused by Windows/Linux line-ending translation. Trust the native check.

## Evolution Roadmap

| Priority | Recommendation | Tags | Why this matters (plain language) |
|----------|----------------|------|-----------------------------------|
| 1 | Single catalog-path resolver: per-project `.volta/` default, one env override (V-1) | [Data-Ownership] | Prevents the exact "same variable, different meaning" drift that cost ATLAS multiple sessions to unwind. |
| 2 | Portable asset references: `source_root` + relative paths in the schema (V-6) | [Data-Ownership] | Do it before real assets pile up; makes the planned M6 host-split possible at all. |
| 3 | Fix Meshy text-task polling + pending-task counting (V-2, V-3) | — | Two small correctness bugs that will each burn a confused hour the first time they're hit in production. |
| 4 | `MeshProvider` protocol around Meshy (V-5) | [Local-First] | One cheap interface now means a local 3D generator later is a plug-in, not a rewrite. |
| 5 | UTC-normalize timestamps (V-4) | — | Boring consistency that pays off the first time logs from two machines are compared. |
| 6 | When Phase-2 LLM features arrive, route through a gateway with local-first task routing (mirror ATLAS `llm_gateway.py`) | [Local-First] | Keeps the pipeline able to run fully offline on future M6-class hardware. |

## Change List

- No source code changes were made. No dead code, unused imports, or commented-out blocks found (the Phase-2 stubs are deliberate, documented scaffolding, not dead code). All concrete issues touch config defaults, schema, external API calls, or behavior — flag-only categories.
- Rewrote `docs/audit/` deliverables (this report, Overview, Operating Guide + HTML twins), replacing the shallow drafts.

## Verification Notes

- Tests: `python -m pytest` → **25/25 pass, 1.29s** (audit sandbox).
- Repo: 9 commits, remote `github.com/andrewlrose/volta-pipeline.git`; caches/egg-info confirmed untracked (`git ls-files` count 0).
- Secrets: `.env.example` placeholders only; `MESHY_API_KEY` via environment — no secret values found anywhere in the tree.
- V-2/V-3 confirmed by direct code read of `meshy/client.py` and `bridge/sync.py`.
