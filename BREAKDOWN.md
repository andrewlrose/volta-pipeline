# VOLTA — Production Breakdown
## Bear Suit Man Episode 1: Cereal Aisle

**Pipeline:** VOLTA v0.1
**Production:** Bear Suit Man Episode 1 — ~60-second deadpan comedy short
**Sprint duration:** 6 weeks
**Producer / pipeline author:** Andrew Rose

---

## Executive Summary

<!-- PLACEHOLDER — fill in Week 6 after production wrap. -->
<!-- Should cover: what VOLTA is, what was produced, honest assessment of -->
<!-- where it accelerated work, where it didn't, and what the next -->
<!-- pipeline iteration would address. Target: 5-minute read for a -->
<!-- Netflix PT&O hiring manager with no VOLTA context. -->

---

## Section 1 — Concept Art (Stages 0–1)

**VOLTA stages covered:** Stage 0 (ComfyUI + Flux.1 concept generation),
Stage 1 (IP-Adapter style consistency)

<!-- PLACEHOLDER — populate Week 2. -->
<!-- Content to include: -->
<!-- - Character LoRA training run: base model, dataset size, training -->
<!--   steps, learning rate, sample outputs -->
<!-- - Before/after: vanilla Flux output vs. Bear Suit Man character LoRA -->
<!-- - Style LoRA training run and results -->
<!-- - Actual prompts used for hero shots -->
<!-- - Candidate-to-selected ratio per shot -->
<!-- - ComfyUI workflow screenshots with node-cluster annotations -->
<!-- - Bear LoRA source / training notes -->
<!-- - Honest assessment: where did LoRA consistency hold? Where did it -->
<!--   break down, and how was it mitigated? -->

---

## Section 2 — From 2D to Rigged 3D (Stages 2–5)

**VOLTA stages covered:** Stage 2 (Meshy image-to-mesh), Stage 3
(retopology + UV), Stage 4 (PBR materials), Stage 5 (AccuRig → HIK)

<!-- PLACEHOLDER — populate Week 3. -->
<!-- Content to include: -->
<!-- - Raw Meshy output → retopologized mesh → rigged character: -->
<!--   three-frame comparison (most visually persuasive section) -->
<!-- - Bear Suit Man mesh: chain-mail/tires/duct-tape detail challenges; -->
<!--   what survived Meshy, what required manual cleanup -->
<!-- - UV unwrap approach and choices -->
<!-- - PBR material workflow (Meshy base + Substance touch-ups) -->
<!-- - AccuRig pass notes; HIK retarget setup -->
<!-- - Bear character pipeline (same stages, abbreviated) -->
<!-- - Environment asset sourcing decision and rationale -->
<!-- - Time comparison table: VOLTA actual vs. traditional pipeline -->
<!--   estimate (concept artist → modeler → texture → rigger) -->

---

## Section 3 — Mocap-Driven Performance + UE5 Assembly (Stages 7–8)

**VOLTA stages covered:** Stage 7 (mocap ingest + cleanup), Stage 8
(DCC assembly: MotionBuilder → UE5 Sequencer)

<!-- PLACEHOLDER — populate Week 4. -->
<!-- Content to include: -->
<!-- - Mocap source decision and rationale (real capture / Cascadeur / -->
<!--   DeepMotion / keyframe — whichever was used) -->
<!-- - Bear Suit Man performance notes: the encumbered, heavy, awkward -->
<!--   quality is the defining character note; how was it achieved? -->
<!-- - Mocap cleanup: solve, gap-fill, smooth approach -->
<!-- - HIK retarget from MotionBuilder to UE5 characters -->
<!-- - UE5 Sequencer setup: shot blocking, camera placement, lens choices -->
<!-- - Comedic timing iteration: what changed between first playblast -->
<!--   and locked cut? -->
<!-- - For the writer: frame this section through Andrew's career lens — -->
<!--   15+ years of mocap supervision on Avatar, Lion King, Mufasa, and -->
<!--   the Sony PS5 catalog. This is the section where his actual -->
<!--   expertise is most directly applied. -->

---

## Section 4 — Lighting, Rendering, and Delivery (Stages 9–11)

**VOLTA stages covered:** Stage 9 (UE5 lighting + PCG), Stage 10
(QA gates), Stage 11 (Movie Render Queue + FFmpeg export)

<!-- PLACEHOLDER — populate Week 5. -->
<!-- Content to include: -->
<!-- - Lighting approach: fluorescent supermarket aesthetic — slightly -->
<!--   green, slightly oppressive, mundane horror -->
<!-- - Before/after: flat UE5 preview lighting vs. final cinematic -->
<!-- - FX pass: atmosphere, dust motes, overhead flicker -->
<!-- - Movie Render Queue configuration (output format, color management) -->
<!-- - Editorial: Resolve assembly, sound design approach, color grade -->
<!-- - Render time actual vs. estimate -->
<!-- - Sound design breakdown: Wilhelm scream, bear suit foley, -->
<!--   supermarket ambient, bear vocalizations, tackle impact, score -->
<!-- - Export: 4K master settings, 1080p Vimeo transcode -->

---

## Conclusions

<!-- PLACEHOLDER — fill in Week 6. -->
<!-- Content to include: -->
<!-- - What VOLTA measurably accelerated (be specific — hours saved, -->
<!--   tasks eliminated, quality threshold reached faster) -->
<!-- - What VOLTA did not accelerate (honest) -->
<!-- - Where manual craft was still required and why -->
<!-- - What the next pipeline iteration would address (Phase 2 items) -->
<!-- - The honest production accounting: total hours by Andrew vs. -->
<!--   estimated traditional pipeline headcount × days -->

---

*Case study video: [Bear Suit Man Episode 1 on Vimeo](#) — link live after Week 6 ship.*
*Full VOLTA repository: [github.com/andrewlrose/volta-pipeline](https://github.com/andrewlrose/volta-pipeline)*
