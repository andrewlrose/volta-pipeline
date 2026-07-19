# Volta — Project Overview & Recommendations Summary

*Fable creative/business portfolio audit — deep pass, 2026-07-07.*

## What this project is (plain language)

Volta is Andy's **AI-assisted movie/game production pipeline in a box**. It takes the workflow he's run at industrial scale for 25 years — concept art → 3D model → rig → motion capture → assembly in Unreal → quality check → final delivery — and rebuilds it as a one-person command-line tool where AI services do the heavy lifting at several stages: ComfyUI generates concept art on the local GPU, Meshy turns images into 3D meshes, and quality gates check every asset against film/game budgets before it moves on.

Every asset, every processing step, and every QA result is recorded in a small local database, so the pipeline always knows what state everything is in. The live proving ground is Bear Suit Man Episode 1; CuddlePirates is the second demo production.

## What it's trying to achieve

A credible boutique-studio pipeline that one experienced supervisor plus AI tools can operate — proving that the concept-to-delivery path that used to take a department can run on a desk. Phase 1 (working now): concept generation, image-to-mesh, mocap ingest, QA gates, social-media export, ATLAS status reporting. Phase 2 (deliberately stubbed, not faked): auto-rigging, facial animation, Unreal automation, film/game packaging.

## How well it's achieving that

The engineering is disciplined and honest. What's claimed as working, works — 25/25 tests pass, verified live in this audit. What isn't built yet says so explicitly and tells you the manual workaround instead of pretending. Repo hygiene is solid (git history, GitHub remote, secrets kept to `.env`, atomic file writes in the ATLAS bridge — the best writer discipline in the creative portfolio).

Three real issues need attention, all cheap now and expensive later: the asset catalog still defaults to a shared home-directory location despite the project's own decision that each production owns its catalog (V-1); the Meshy client checks text-to-3D jobs at the wrong endpoint, so those jobs appear to fail (V-2); and asset file paths are stored as absolute Windows paths, which will all break in the planned move to the M6 server (V-6).

## Recommendations summary (plain language)

1. **Move the catalog default to per-project `.volta/`** with one shared path resolver — the household has already paid the price for "one variable, two meanings" drift once. (V-1 — Medium.)
2. **Store portable asset references** (named mount + relative path + hash) before the catalog fills up with real assets. (V-6 — Medium.)
3. **Fix the two small correctness bugs** — text-to-3D polling and the never-clearing "pending tasks" alert. (V-2/V-3 — Medium.)
4. **Wrap Meshy in a provider interface** so a future local 3D generator is a drop-in, keeping the pipeline on the local-first road. (V-5 — [Local-First].)

Full detail: `Volta_Audit_Report.md` in this folder.
