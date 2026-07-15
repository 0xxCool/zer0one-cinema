# zer0one-cinema — Architecture

Version: v0-draft (2026-07-15). Consolidates 7 research docs (see `docs/research/`).

## 1. Design Principles (non-negotiable)

1. **Deterministic.** Same GLB + same preset → bit-identical output. All stochastic steps use fixed seeds + sorted inputs. K-Means with `random_state=0, n_init=1`. No ML in the render path (only optional, opt-in, in future preset-suggestion helpers).
2. **Cycles-only rendering.** EEVEE-Next requires an OpenGL display context that headless Linux containers cannot cleanly provide; commercial risk of EGL/Xvfb breakage on GPU drivers is real. Cycles + OPTIX works headless with `nvidia-container-toolkit` and no display server. (See `research/blender-api-limits.md` §2.)
3. **Blender-tarball, not `pip install bpy`.** The PyPI `bpy` package (v5.2, Python-version-locked, glibc ≥ 2.28) has a SIGSEGV race on interpreter cleanup that surfaces as exit-code 139/245 *after* successful renders. We ship the official Blender 4.2 LTS tarball frozen at a known-good version and invoke it via `blender -b -P script.py`; health-checks look at output-file existence, never at exit-code.
4. **No proprietary dependencies.** All deps are OSI-licensed. FFmpeg for encoding, OpenColorIO+AgX for grading (Blender-native since 4.0), Blender-Compositor for post. DaVinci Resolve is excluded (its scripting API is Studio-only, breaks the zero-cost rule).
5. **Whitelist over blacklist.** For material sanitizing, wheel detection, PBR normalization: known classes are corrected, unknown inputs are passed through untouched. Rollback log per operation, so users can `zocinema undo`.
6. **Max-iters bounds on every auto-fix loop.** No infinite retry. `MAX_ITERS = 3` for preflight-fix, then hard-fail with a structured JSON report (no GPU spend on a bug we can't fix).

## 2. Data Flow (High-Level)

```
                          ┌────────────────────────────────────────────┐
                          │   1. glb_in         2. preset (yaml)       │
                          └───────────┬────────────────┬───────────────┘
                                      ▼                ▼
                          ┌────────────────────────────────────────────┐
                          │  MODEL_PREP      (deterministic)           │
                          │  - glb_loader                              │
                          │  - bbox_utils                              │
                          │  - wheel_detect     (K-Means k=4, sorted)  │
                          │  - origin_fix                              │
                          │  - rolling_axis                            │
                          │  - caliper_filter                          │
                          │  - ground_anchor    (all-mesh min_z)       │
                          │  - body_group                              │
                          │  - material_sanitize (3-pass whitelist)    │
                          └───────────┬────────────────────────────────┘
                                      ▼
                          ┌────────────────────────────────────────────┐
                          │  PRESET_APPLIER (data-driven)              │
                          │  - looks/*.yaml     → HDRI + lighting rig  │
                          │  - cameras/*.yaml   → path + focal + DoF   │
                          │  - post_chain       → compositor nodes     │
                          └───────────┬────────────────────────────────┘
                                      ▼
                          ┌────────────────────────────────────────────┐
                          │  PREFLIGHT (fast, EEVEE 1 frame, ~5 s)     │
                          │  ⚠ Cycles-low-samples if EEVEE broken      │
                          │  - test_frame                              │
                          │  - frame_analyzer:                         │
                          │      • frustum_check (world_to_camera_view)│
                          │      • ground_edge_detect (Hough)          │
                          │      • composition_check (saliency)        │
                          │  - auto_fix_loop  (MAX_ITERS=3)            │
                          └───────────┬────────────────────────────────┘
                                      │  PASS: continue          FAIL: exit + JSON report
                                      ▼
                          ┌────────────────────────────────────────────┐
                          │  RENDER (Cycles + OPTIX, N frames)         │
                          │  - engine        (samples, denoiser)       │
                          │  - gpu_init      (explicit device select)  │
                          │  - frame_writer  (16-bit PNG multi-pass)   │
                          └───────────┬────────────────────────────────┘
                                      ▼
                          ┌────────────────────────────────────────────┐
                          │  POST (Blender-Compositor + FFmpeg)        │
                          │  - compositor_chain  (grain/vignette/CA)   │
                          │  - encoder          (H.264 + AV1 + poster) │
                          └───────────┬────────────────────────────────┘
                                      ▼
                          ┌────────────────────────────────────────────┐
                          │  VERIFY (CGVF — Cinema-Grade Verification) │
                          │  - 6 gates: lighting/material/motion/      │
                          │             composition/atmosphere/grading │
                          │  - waveform + vectorscope (FFmpeg-parsed)  │
                          │  - HTML report per render                  │
                          └───────────┬────────────────────────────────┘
                                      │  ≥ 95 % frames PASS: ship        < 95 %: flag + report
                                      ▼
                          ┌────────────────────────────────────────────┐
                          │  DELIVERY (mp4, webm, poster.jpg, report)  │
                          └────────────────────────────────────────────┘
```

Each stage is independently invokable (`zocinema model-prep`, `zocinema preflight`, …) so power-users can compose custom pipelines.

## 3. Module Map

Package: `zer0one_cinema` (Python ≥ 3.11).

| Sub-package | Files | Purpose |
|---|---|---|
| `io/` | `glb_loader.py`, `output_writer.py` | Deterministic import (`bpy.ops.import_scene.gltf`) + PNG/MP4/WebM write |
| `model_prep/` | `bbox_utils`, `wheel_detect`, `origin_fix`, `rolling_axis`, `caliper_filter`, `ground_anchor`, `body_group`, `material_sanitize` | GLB → canonical rigged scene |
| `presets/` | `applier.py`, `looks/*.yaml`, `cameras/*.yaml`, `post_chains/*.yaml` | Data-driven preset system |
| `preflight/` | `test_frame`, `frame_analyzer`, `auto_fix_loop` | Cheap pre-render sanity checks |
| `render/` | `engine`, `gpu_init`, `frame_writer` | Cycles+OPTIX orchestration |
| `post/` | `compositor_chain`, `encoder` | Blender-Compositor + FFmpeg |
| `verify/` | `gates`, `frame`, `reporter`, `waveform_probe` | CGVF 6-gate check + report |
| `cli/` | `main.py` | Click-based CLI (`zocinema`) |
| `blender_addon/` | `__init__.py`, `blender_manifest.toml`, `ops.py`, `panels.py` | Blender 4.2 Extension wrapper (Phase 2) |
| `docker/` | `Dockerfile`, `entrypoint.sh` | Serverless-worker image `ghcr.io/0xxCool/zer0one-cinema-worker` |

## 4. Interfaces

**Module contract:** every module accepts a `Context` dataclass (Blender scene reference + JSON-serializable config-dict) and returns a `Result` dataclass (mutated scene + operation log + provenance hash).

```python
@dataclass
class Context:
    scene: bpy.types.Scene         # active Blender scene
    config: dict                    # JSON-serializable; snapshot at boundary
    trace: list[TraceEntry]         # append-only operation log
    seed: int = 0                   # global RNG seed
```

**Provenance-hash:** SHA-256 of (input-GLB-hash + preset-yaml-hash + package-version + seed). Same hash → same output. Recorded in every delivered `report.json` for reproducibility audits.

## 5. Key Constraints From Research

Compressed from the 7 research docs; full detail there.

**From `state-of-art.md`:** the market has renderers (V-Ray, KeyShot, C4D+Redshift) and DCCs (Blender, Maya) but no "director-in-a-box" — nothing goes from GLB to trailer in one command. Add-ons cover slices (Rigacar for wheels, iCars for curves, AutoCam for cameras) but never the whole chain. **Positioning:** deterministic + headless + MIT + GLB-first is a defensible white-space.

**From `blender-api-limits.md`:** three hard constraints — no `pip install bpy` (use Blender-tarball), Cycles-only headless (EEVEE-Next needs display), Draco-lib symlink required in Docker image. GPU-init requires explicit `preferences.get_devices()` + per-device `d.use = True`.

**From `wheel-detection-methods.md`:** K-Means (k=4) with `random_state=0, n_init=1` + lexicographically-sorted candidate points before `.fit()` is bit-identical across runs. Six-stage pipeline (candidates → axis-align → cluster → radius-fit → symmetry-test → caliper-filter). Edge-cases: motorcycle (k=2), truck (k=6), spare-wheel (5th candidate), caliper-inside-cluster.

**From `pbr-auto-fix-heuristics.md`:** five most-impactful auto-fixes — emission-kill, alpha-clamp to 1.0, 3-pass classification (regex → texture → default_plastic), car-paint formula with `Coat Weight = 1.0` (without it, paint looks like wall-paint), and awareness of Blender-4.x rename traps (`Clearcoat` → `Coat Weight`, etc). Whitelist-only, per-op rollback log.

**From `cinema-look-analysis.md`:** three must-ship presets — `night_neon_wet_v1` (NFS Heat DNA, non-negotiable), `studio_hero_v1` (80 % use-case), `documentary_race_v1` (Ford v Ferrari + Gran Turismo racing feel, differentiator). Bonus: FFmpeg-vectorscope-parser makes Gate 6 (Grading) machine-measurable.

**From `preflight-frame-qa.md`:** three preflight checks under 200 ms each — `world_to_camera_view()` frustum test, OpenCV Canny+Hough for ground-edge visibility, saliency + rule-of-thirds for composition. Auto-fix formula: `camera_shift = ndc_offset × 2 · distance · tan(fov/2)`. `MAX_ITERS = 3` bounded.

**From `opensource-ecosystem.md`:** dependency set is FFmpeg + OpenColorIO/AgX + Blender-Compositor + `opencv-contrib-python` + `scikit-image` + `numpy` + `pillow` + `pyyaml` + `click`. Test-assets from Sketchfab CC0 tag + Khronos glTF-Sample-Assets + PolyHaven HDRIs. Launch strategy: Blender-Artists + r/blender + Show HN on the same day; `extensions.blender.org` submission comes in Phase 2 (needs wheels bundled, no runtime pip).

## 6. Deployment Targets

| Target | Format | Audience | Release |
|---|---|---|---|
| PyPI | `pip install zer0one-cinema` | Python devs, cinema-orch backend | v0.1 |
| GitHub Release | source tarball + `.blend` fixtures | Contributors | v0.1 |
| Docker (GHCR) | `ghcr.io/0xxCool/zer0one-cinema-worker` | Serverless-render backends | v0.4 |
| Blender Extensions Platform | `.zip` with `blender_manifest.toml`, wheels bundled | End-users (GUI) | v0.5 |

`cinema-orch` integrates it as `preflight` hook (validates before dispatching to the RunPod serverless endpoint `cx6ws3mc43880a`). Preflight failure → job never leaves the orchestrator, user sees fix suggestions in the dashboard.

## 7. Test Strategy

- **Unit tests** (`tests/unit/`) — pure-Python module contracts, no Blender needed. Uses recorded `bpy.Scene` fixtures.
- **Integration tests** (`tests/integration/`) — run in a Docker container with Blender 4.2, use 10 real GLB fixtures from Sketchfab CC0.
- **Golden-frame tests** (`tests/golden/`) — each preset renders a canonical scene, output compared to committed golden PNG via SSIM (threshold 0.98). New presets require golden regeneration + human sign-off.
- **CI matrix** — Python 3.11/3.12, Ubuntu 22.04, GitHub Actions with CPU-only Blender (unit + integration). GPU tests only on the RunPod endpoint (nightly).

## 8. Out-of-Scope for v0.x (explicitly deferred)

- Non-vehicle models (character, architecture, product) — later.
- Anamorphic 2.39:1 letterbox (nice-to-have, v0.6+).
- Real-time (interactive) rendering — Cinema is the target, not games.
- ML-based preset suggestion — v1.x, opt-in only.
- Multi-vehicle scenes — v0.6+.
- Cloud UI (web-frontend) — that's what `zer0onelab.com/render` already does.
