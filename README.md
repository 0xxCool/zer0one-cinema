# zer0one-cinema

**Deterministic cinema-grade rendering automation for Blender.**
GLB in, movie out — no manual scene setup, no per-model tweaking, no subscription tools required.

> **Status:** v0.2.1 shipped — model-prep + preflight + verify (with profile-based thresholds).
> Rendering pipeline lands in v0.3.
> Live case-study: [zer0onelab.com/cinema](https://zer0onelab.com/cinema).

[![PyPI](https://img.shields.io/pypi/v/zer0one-cinema.svg)](https://pypi.org/project/zer0one-cinema/)
[![CI](https://github.com/0xxCool/zer0one-cinema/actions/workflows/ci.yml/badge.svg)](https://github.com/0xxCool/zer0one-cinema/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## The problem this solves

Take any 3D vehicle model from Sketchfab, throw it into Blender, run Cycles — you get a bland turntable. To get an *automotive-trailer look* (Ford v Ferrari, NfS Heat, Gran Turismo) you need:

- Wheels detected and rigged at their real rotation center (not the GLB's random origin)
- Body on the ground, not floating or sunk
- Lighting that flatters the paint (rim light for silhouette, key/fill balance)
- Camera framing that respects Rule-of-Thirds and doesn't clip parts of the car
- Post-processing (grading, DoF, motion blur, chromatic aberration, film grain)
- Verification that every rendered frame actually meets those standards

Today this takes a 3D artist several days of manual work per model. `zer0one-cinema` will do it in one CLI command:

```bash
zocinema render my_car.glb --look studio_night_neon --camera push_in --output trailer.mp4
```

**v0.2.1 ships the first two stages** — model-prep + preflight-and-verify:

```bash
# Stage 1 — deterministic model preparation (needs Blender's bpy)
blender -b -P scripts/run_zocinema.py -- model-prep my_car.glb --output my_car.blend

# Stage 2 — preflight the scene (renders a preview frame, auto-fixes known bug classes)
zocinema preflight my_car.blend --camera Cam --report preflight.json

# Stage 3 — verify a folder of rendered frames against 6 cinema-grade gates
zocinema verify frames/ --profile night_neon --report verify.json
```

The full render pipeline lands in v0.3.

---

## Quickstart (v0.2.1)

### Install from PyPI

```bash
# CLI + verify (no Blender needed — verify + gates run on rendered PNGs)
pip install "zer0one-cinema[preflight]==0.2.1"

zocinema --version   # zocinema, version 0.2.1
zocinema --help
```

The `[preflight]` extra pulls in `opencv-contrib-python`, `scikit-image`, `scikit-learn`, `pillow`, and `pyyaml` so both `preflight` and `verify` work out of the box. If you only need `model-prep`, `pip install zer0one-cinema` is enough — but you also need Blender to actually run it (see below).

### Verify rendered frames (no Blender required)

```bash
# Daylight-studio thresholds (default, matches v0.2.0)
zocinema verify path/to/frames/ --report verify.json

# NfS-style night hero-reveal (cyan+magenta neon, dark metallic body, orbit camera)
zocinema verify path/to/frames/ --profile night_neon --report verify.json
```

The 6-gate CGVF check runs at ~1.6 s per 1080p frame. Report has both machine-readable JSON and a side-by-side Markdown (`.md` suffix next to the JSON path).

Exit codes drive CI: `0` = all PASS, `1` = at least one WARN, `2` = at least one FAIL.

### Preflight a Blender scene

Preflight renders a small preview at scene-boundary corners, analyzes the frame against a fix-rules registry, applies known fixes (e.g. camera clips car body → back the camera up), and re-renders. Loops up to `--max-iters` times.

```bash
# Needs Blender 4.2+ on PATH (or invoke via blender -b -P scripts/run_zocinema.py)
zocinema preflight my_car.blend \
    --camera Cam \
    --car car \
    --output-dir preflight-frames \
    --report preflight.json \
    --max-iters 3
```

### Model-prep a GLB (needs Blender)

Model-prep is the only stage that hard-depends on `bpy`. Run through Blender:

```bash
BLENDER=~/opt/blender-4.2.11-linux-x64/blender

"$BLENDER" -b -P scripts/run_zocinema.py -- model-prep \
    /path/to/car.glb \
    --output out.blend \
    --report report.json \
    --seed 0
```

**Real example on `kenney_sedan.glb`** (part of our test-suite):

```
[1/7] Loading kenney_sedan.glb...
      → 5 meshes, 3184 vertices, 0.13s
[2/7] Ground-anchoring...
      → z_shift = 0.0000 m, moved 0 objects
[3/7] Detecting wheels...
      → 4 wheels: FL, FR, RL, RR (confidence 0.90)
[4/7] Re-origining wheels...
      → moved 0 origins, skipped 0 already-centered
[5/7] Building body group...
      → 1 body meshes (excluded 4 wheel + 0 env)
[6/7] Sanitizing materials...
      → 1 materials analyzed, 1 changed
[7/7] Saving out.blend...
✓ Done in 2.5s
```

The output `.blend` file is fully rigged: wheels have their origins at the axle centers (so `wheel.rotation_euler.x -= radians(360)` spins them in place instead of throwing them off the car), the body is grounded to z=0, materials are normalized to sane PBR values.

Deterministic — same GLB + same seed → byte-identical output.

---

## Verify profiles

`v0.2.0` had a single hard-coded threshold set tuned for daylight studio renders. Cinema-grade night-neon looks (cyan/magenta rims, dark metallic body, orbit camera) tripped false FAILs on every gate. `v0.2.1` introduces named threshold profiles:

| Profile | When to use | What it widens vs standard |
|---|---|---|
| `standard` (default) | Daylight studio, product-shot, well-lit hero | — (v0.2.0 behaviour, unchanged) |
| `night_neon` | NfS-style cyan+magenta night hero-reveal, orbit camera, dark metallic body | A_lighting key/fill max 6→25 · B_material body-bright-frac min 0.08→0 · C_motion consistency min 0.85→0.05 · F_grading shadow-hue 160-220°→190-290°, highlight-hue 20-60°→180-330°, corner/center 0.75→5 · D_composition center-offset min 0.15→0, negative-space 0.20→0.60 · aspect_ratio 2.39 (cinemascope) → 1.7778 (web 16:9) |

On the RS6 night hero-reveal case-study that ships as our v3 live demo: **standard** produces 0-8% pass across all gates; **night_neon** produces 91-100% pass across all 6.

Add your own profile in [`zer0one_cinema/verify/thresholds.py`](zer0one_cinema/verify/thresholds.py) — the merge is base-thresholds + override-dict, so a profile only lists what it changes.

---

## What v0.2.1 supports

**Model-prep**
- **Wheel detection** for typical 4-wheeled cars, SUVs, trucks, monster-trucks (wheelbase-to-wheel-diameter ratio 0.03–0.50)
- **Ground anchor** — vehicle's lowest point placed at world z=0
- **Origin fix** — wheel object-origins moved to axle centers (so rotation animations work)
- **Body group** — non-wheel meshes grouped with a centroid for later body-roll/pitch animation
- **Material sanitize** — 12-class PBR classifier (car-paint, chrome, glass, tire, brake, carbon-fiber, headlight, taillight, rim-alloy, interior-plastic, leather-seat, unknown → default-plastic)

**Preflight**
- Deterministic preview-render at scene boundaries
- Analyzer + fix-rules registry: camera clipping, hero-side lighting-flatness, HDRI-overexposure, etc.
- Loop up to `--max-iters` iterations with auto-fixes, reports per-iteration diagnostics

**Verify (6-gate CGVF framework)**
- `A_lighting` — key/fill ratio, shadow density, highlight clip
- `B_material` — bright-body-pixel fraction, wet-asphalt peaks (below vehicle)
- `C_motion` — Farnebäck optical-flow direction consistency between consecutive frames
- `D_composition` — subject center-offset, negative space, auto-fill fraction
- `E_atmosphere` — background detail
- `F_grading` — aspect-ratio, vignette, shadow/highlight hue targets
- Per-frame status + roll-up + per-gate PASS-rate
- Named threshold profiles (`--profile standard | night_neon`, more coming in v0.3)
- Machine-readable JSON + side-by-side Markdown reports
- `--strict` mode: treat WARN as FAIL (for CI regression gating)

**Reference case-study**
The v0.2.1 stack is dogfooded on our own live demo — see [`zer0one-web/scripts/render_rs6_hero_reveal_v3.py`](https://github.com/0xxCool/zer0one-cinema/blob/main/scripts/render_rs6_hero_reveal_v3.py) and the [live 192-frame render](https://zer0onelab.com/de/showcase).

## What v0.2.1 does NOT support (yet)

- **Rendering** — v0.2.1 is model-prep + preflight + verify. Cinema-grade renders (Cycles + preset library) come in v0.3.
- **Merged-mesh GLBs** — models exported as one giant mesh with no separate wheel objects. Sub-mesh splitting via connected-components arrives in v0.3.
- **Non-vehicle models** — characters, architecture, product-vis need their own detection heuristics (v1.2+).
- **Golden-frame regression** — `zocinema verify --ref path/` is stubbed in v0.2.1, full implementation lands in v0.3.

---

## Design principles

1. **Deterministic.** Same GLB + same preset → byte-identical output. K-Means uses `random_state=0, n_init=1` with lexicographically-sorted inputs.
2. **Open source.** MIT license. Core is free forever. Premium look library (v0.3+) is a separate paid add-on.
3. **No proprietary dependencies.** Blender / Python / numpy / scikit-learn / OpenCV / FFmpeg — no Adobe / Substance / KeyShot / Marmoset subscription required.
4. **Every frame verified.** The 6-gate CGVF framework runs on every render — bad frames are flagged, not shipped.
5. **Testable without Blender.** Model-prep + verify work against pure-Python protocols (`MeshLike`, `MaterialLike`, `MutableObject`). Unit tests use numpy-only mocks — no `bpy` required.
6. **Configurable thresholds.** Verify gates read all cutoffs from a single dict; named profiles keep look-specific overrides out of gate code.

---

## Architecture

```
GLB → Model-Prep → Preflight → Preset-Apply → Render → Post → Verify → Delivery
      [v0.1 ✓]    [v0.2 ✓]    (v0.3)         (v0.3)   (v0.3) [v0.2 ✓] (v0.3)
```

Each stage is an independent Python package with a stable interface. Compose your own pipelines.
Full architecture: [docs/architecture.md](docs/architecture.md).

---

## Roadmap

- **v0.1** ✓ — Model-Prep Core (wheel detection, origin fix, ground anchor, body group, material sanitize)
- **v0.2** ✓ — Preflight & Verify (test frame + 6-gate verification + auto-fix loop)
- **v0.2.1** ✓ — Verify threshold profiles (`--profile night_neon`)
- **v0.3** — Preset Library (5 looks × 5 cameras) + Cycles rendering + Golden-frame regression
- **v0.4** — CLI + Blender Addon + Docker Serverless
- **v0.5** — Public Launch (landing page + 3–5 case studies)
- **v1.0** — First customer case study live on zer0onelab.com

Full roadmap: [docs/roadmap.md](docs/roadmap.md).

---

## Development

```bash
git clone https://github.com/0xxCool/zer0one-cinema
cd zer0one-cinema
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,preflight]"
pytest tests/               # ~200 tests, ~10s
ruff check zer0one_cinema tests
mypy zer0one_cinema
```

Real-Blender integration testing needs the runner script:

```bash
~/opt/blender-4.2/blender -b -P scripts/run_zocinema.py -- \
    model-prep tests/glb_fixtures/kenney_sedan.glb --output /tmp/out.blend
```

Test-fixture GLBs (not in the repo — see [tests/glb_fixtures/README.md](tests/glb_fixtures/README.md) for reproduction).

---

## Contributing

Not accepting external code contributions yet — waiting for v0.3 (public launch) to stabilize the interface. **Bug reports welcome** as GitHub Issues, especially:

- New GLB structures the wheel-detection Stage 2 filter rejects (paste the output of `scripts/debug_candidates.py`).
- False-positive FAILs in `zocinema verify` for legitimate cinema looks — add the profile name you used (or `standard` if none) and 3-5 sample frames if you can share them.

## License

MIT — see [LICENSE](LICENSE).

## Who's behind this

Built by [ZER0ONELAB](https://zer0onelab.com) as part of our cloud-render platform for DACH studios doing brand work. If you need cinema-grade renders at scale without doing the engineering yourself, we're the delivery layer.
