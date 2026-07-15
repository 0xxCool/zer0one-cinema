# zer0one-cinema — Roadmap

Version: v0-draft (2026-07-15). One release per phase, each independently useful.

## Sequencing principle

Every release ships a **working end-to-end path** for a narrower scope, not a partial layer for the full scope. v0.1 already lets a user run `zocinema model-prep foo.glb → foo_clean.blend` — no visual output yet, but a real, testable improvement over "hand-edit in Blender GUI". Each subsequent release adds one layer of value, not one layer of the stack.

## v0.1 — Model-Prep Core (Target: Week 2, ~5–7 dev-days)

**Ships:** `zocinema model-prep <glb> --output <clean.blend>` — takes any vehicle GLB, produces a canonically-rigged `.blend` file: wheels detected + centered + rigged, body grouped, ground-anchored, materials sanitized. Deterministic (same input → bit-identical output).

**Modules:** `io.glb_loader`, `model_prep/*` (all 9 files).

**Test fixtures:** 10 vehicle GLBs collected from Sketchfab CC0 + Khronos glTF-Sample-Assets:
- 3× RS6 variants (we already own one)
- BMW M3, Ford Mustang, Porsche 911 — sports segment
- Tesla Model S, Ford F-150 — sedan + truck
- generic-low-poly + vintage-classic — long-tail

**Success criteria:**
- Wheel detection: 4/4 wheels correctly identified on 9/10 fixtures (motorcycle counts as 2/2)
- Ground anchor: `min_z(scene) ∈ [-0.001, +0.001]` on 10/10
- No wheel flies off; caliper stays static; body is a single group
- Deterministic: run twice, `sha256(output.blend) == sha256(output.blend)`
- Runs on CPU in < 15 s per fixture

**Deliverables:** PyPI release, GitHub tag, CI matrix green, README with "getting started" that works from a fresh venv.

**Explicit NOT in v0.1:** rendering, lighting, cameras, HDRIs. Just the rigging.

## v0.2 — Preflight & Verify (Target: Week 3, ~4–5 dev-days)

**Ships:** `zocinema preflight <clean.blend> --camera <path>` — renders a fast preview frame, analyzes it, returns PASS/WARN/FAIL with structured JSON. `zocinema verify <frames-dir>` runs the 6-gate CGVF check on any finished render.

**Modules:** `preflight/*` (3 files), `verify/*` (4 files, migrated + extended from existing `.claude/skills/cinema-grade-verification/scripts/verify_frame.py`).

**Auto-fix loop:** MAX_ITERS=3. If preflight fails after 3 attempts, emit `preflight_report.json` and exit non-zero (no GPU spend on unfixable configs).

**Success criteria:**
- Frustum check catches "car cut off" in 3/3 test cases
- Ground-edge detection catches visible-plane-edge in 3/3 test cases
- Composition check flags center-locked in 3/3 test cases
- Auto-fix resolves 2/3 of these without human intervention (unfixable third → clean error)
- CGVF verify runs at ≤ 250 ms per frame

**Explicit NOT in v0.2:** looks or camera presets — preflight uses hand-authored test cameras. Presets come in v0.3.

## v0.3 — Preset Library (Target: Week 4, ~5–7 dev-days)

**Ships:** `zocinema render <clean.blend> --look <preset> --camera <preset> --duration <s> --output <out.mp4>` — full E2E with preset library.

**Presets shipped:**
- **Looks** (5): `night_neon_wet_v1` (Škomi's must-ship — NFS Heat DNA), `studio_hero_v1` (80% use-case default), `documentary_race_v1` (Ford v Ferrari), `golden_hour_track_v1` (premium), `showroom_daylight_v1` (product-vis)
- **Cameras** (5): `push_in`, `orbit_360`, `hero_reveal`, `chase_cam`, `flyby_low`

**Modules:** `presets/*` including all YAML files + `applier.py`.

**Success criteria:**
- Each of 25 preset combinations renders successfully on the RS6 fixture
- Golden frames committed to `tests/golden/` for each look × 3-key-cameras (15 goldens)
- Škomi-verdict on 3 must-ship looks (green light or specific delta feedback)
- Render time on A4000 serverless: ≤ 4 s per frame at 1920×1080, 128 samples

## v0.4 — CLI + Docker (Target: Week 5, ~5 dev-days)

**Ships:** Docker image `ghcr.io/0xxCool/zer0one-cinema-worker` runnable on RunPod serverless. `cinema-orch` integration: preflight step before every job dispatch. `zocinema` CLI properly packaged with `click`, full `--help`, subcommands documented.

**Modules:** `cli/main.py`, `docker/Dockerfile`, `docker/entrypoint.sh`. Integration file: `~/cinema-orch/cinema_orch/preflight.py`.

**Success criteria:**
- Docker image < 5 GB (Blender is ~2.5 GB, rest is deps)
- `docker run ghcr.io/0xxCool/zer0one-cinema-worker render <presigned-url> --preset X` completes E2E
- cinema-orch dispatches to serverless-worker successfully
- Cold-start on RunPod serverless: ≤ 90 s
- Failed preflight blocks job in cinema-orch (verified via test job with intentional bug)

## v0.5 — Public Launch (Target: Week 6, ~5 dev-days)

**Ships:** Landing page `zer0onelab.com/cinema`, GitHub README production-grade, HN Show-HN post, r/blender post, Blender-Artists thread. First 3 case-study videos public.

**Non-code deliverables:**
- Landing page (new route in `zer0one-web/`)
- 3 case-study videos (each < 30 s, downloadable `.blend` for reproducibility)
- Getting-started blog post (5-min read, one-command hello-world)
- YouTube 5-min demo video (screen-record + narration)
- LinkedIn post via existing `linkedin-automation` pipeline

**Success criteria:**
- Landing has JSON-LD SoftwareApplication + hreflang for 6 locales
- Show-HN post gets ≥ 20 upvotes in first 6 hours (kill-metric: if flat after 6 h, iterate)
- GitHub stars trend positive (target: ≥ 50 in first week)
- One inbound "how do I use this" question from a real 3D artist within 72 h

## v0.6 — Blender Extension (Target: Week 7 spillover, ~3–4 days)

**Ships:** Blender-4.2 Extension submission to `extensions.blender.org`. GUI panel with buttons for common operations (auto-rig, preflight, render with preset).

**Bundling requirement (Blender rule):** all Python wheels included in the ZIP; no runtime `pip install`; `bpy.app.online_access` respected.

**Success criteria:** Extension approved by Blender review, users can install it via the built-in Extensions panel.

## v1.0 — RS6 Case Study Live (Target: End of Sprint 19)

**Ships:** The one CLI command that produces the RS6 trailer:

```bash
zocinema render rs6_showpiece.glb \
  --look night_neon_wet_v1 \
  --camera hero_reveal:5s,orbit_360:8s,push_in:4s,chase_cam:10s \
  --duration 27 \
  --resolution 1920x1080 \
  --output rs6_showcase_v4.mp4
```

**Deploy:** Coming-Soon-Card on `zer0onelab.com/showcase` replaced by the actual video + a "Rendered with ZER0ONE Cinema (open source) — see how it was made [GitHub]" caption. Blog post explaining the backstory (RS6-8-iterations-of-Ad-Hoc-bugs → structural solution). Škomi's PO-verdict required.

**This is the "we shipped what we promised" milestone.** Everything after is v1.x incremental improvement (more looks, non-vehicle models, anamorphic, ML-suggest, multi-vehicle scenes).

## Beyond v1.0 (v1.x candidates, not committed)

- **v1.1 — Anamorphic Look Pack** (paid Premium tier trigger)
- **v1.2 — Non-Vehicle Models** (characters, ArchViz, products) — expands audience
- **v1.3 — ML Preset Suggestion** (opt-in): analyze GLB, suggest which of the 5 looks fits best based on model complexity + material palette
- **v1.4 — Multi-Vehicle Scenes** (racing grid, chase scene)
- **v1.5 — Storyboard-from-Text** ("Show me a 30 s trailer of this RS6 doing a hero reveal, then chasing, then hero pose") — the true "director" ambition

## Timeline compression risks

- **Wheel detection edge-cases** (v0.1) — if 3/10 fixtures fail, we need per-model YAML override support. Adds 2 days.
- **EEVEE preview** (v0.2) — if EEVEE-in-container proves broken as researched, we fall back to Cycles low-samples for preflight (still ~3 s, acceptable). No blocker.
- **Docker cold-start** (v0.4) — if > 90 s, we prewarm on the serverless endpoint. RunPod supports this natively via `min_workers`. Adds cost, not delivery time.
- **First Show-HN flop** (v0.5) — if it doesn't gain traction, we iterate title + first-hour-comment strategy + re-launch a week later. No hard failure mode.

## Definition of Done — per release

Every version release must have:
1. All new modules covered by unit + integration tests (≥ 80 % line coverage)
2. Documentation updated (`docs/user-guide/`, in-code docstrings)
3. `CHANGELOG.md` entry with breaking changes flagged
4. GitHub Release tagged, PyPI published, Docker image pushed
5. Cowork-agent verdict on the release (independent review, especially for design decisions)
6. Škomi's PO sign-off for v0.3, v0.5, v1.0 (customer-facing milestones)
