# zer0one-cinema

**Deterministic cinema-grade rendering automation for Blender.**
GLB in, movie out — no manual scene setup, no per-model tweaking, no subscription tools required.

> **Status:** v0.1 model-prep layer implemented, real-Blender verified on 2 vehicle GLBs.
> Follow [releases](https://github.com/0xxCool/zer0one-cinema/releases) or
> [zer0onelab.com/cinema](https://zer0onelab.com/cinema) for progress.

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

**v0.1 ships the first stage of that pipeline** — deterministic model preparation:

```bash
zocinema model-prep my_car.glb --output my_car_prepped.blend --report report.json
```

The full render pipeline lands in v0.3.

---

## Quickstart (v0.1)

Model-prep is a Blender-Python operation — it needs Blender 4.2+ installed. Full render
pipeline (v0.3+) will also work as a standalone pip install.

### 1. Install Blender 4.2 LTS

```bash
# Download the official tarball (avoid distro packages — many miss the Draco decoder)
wget https://download.blender.org/release/Blender4.2/blender-4.2.11-linux-x64.tar.xz
tar -xf blender-4.2.11-linux-x64.tar.xz -C ~/opt/
```

### 2. Install zer0one-cinema

```bash
# Into Blender's bundled Python:
~/opt/blender-4.2.11-linux-x64/4.2/python/bin/python3.11 -m pip install --user \
    click numpy pillow pyyaml scikit-learn

# Clone the repo (PyPI upload will come with v0.1.0 release tag):
git clone https://github.com/0xxCool/zer0one-cinema ~/zer0one-cinema
```

### 3. Prepare a GLB

```bash
BLENDER=~/opt/blender-4.2.11-linux-x64/blender
cd ~/zer0one-cinema

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

The output `.blend` file is fully-rigged: wheels have their origins at the axle
centers (so `wheel.rotation_euler.x -= radians(360)` spins them in place instead of
throwing them off the car), the body is grounded to z=0, materials are normalized
to sane PBR values (car-paint clearcoat, chrome metallic, etc.). Deterministic —
same GLB + same seed → byte-identical output.

**Read the report:**

```bash
python3 -m json.tool report.json
```

---

## What v0.1 supports

- **Wheel detection** for typical 4-wheeled cars, SUVs, trucks, monster-trucks (wheelbase-to-wheel-diameter ratio 0.03 – 0.50)
- **Ground anchor** — vehicle's lowest point placed at world z=0
- **Origin fix** — wheel object-origins moved to axle centers (so rotation animations work)
- **Body group** — non-wheel meshes grouped with a centroid for later body-roll/pitch animation
- **Material sanitize** — 12-class PBR classifier (car-paint, chrome, glass, tire, brake, carbon-fiber, headlight, taillight, rim-alloy, interior-plastic, leather-seat, unknown → default-plastic). Whitelist-based: unknowns pass through untouched. Hard fixes for the two most common Sketchfab bugs (emission accidentally set on body, alpha=0.99 instead of 1.0).

## What v0.1 does NOT support (yet)

- **Merged-mesh GLBs** — models exported as one giant mesh with no separate wheel objects. Common on old CAD-export or single-artist Sketchfab uploads (e.g. `khronos_toy_car.glb`). Sub-mesh splitting via connected-components arrives in v0.2.
- **Rendering** — v0.1 is model-prep only. Cinema-grade renders (Cycles + preset library) come in v0.3.
- **Preflight / verify** — automatic frame-QA is v0.2.
- **Non-vehicle models** — characters, architecture, product-vis need their own detection heuristics (v1.2+).

---

## Design principles

1. **Deterministic.** Same GLB + same preset → byte-identical output. K-Means uses `random_state=0, n_init=1` with lexicographically-sorted inputs.
2. **Open source.** MIT license. Core is free forever. Premium look library (v0.3+) is a separate paid add-on.
3. **No proprietary dependencies.** Blender / Python / numpy / scikit-learn / FFmpeg — no Adobe / Substance / KeyShot / Marmoset subscription required.
4. **Every frame verified.** The 6-gate cinema-grade verification framework (v0.2) runs on every render — bad frames are flagged, not shipped.
5. **Testable without Blender.** All model-prep modules work against pure-Python protocols (`MeshLike`, `MaterialLike`, `MutableObject`). Unit tests use numpy-only mocks — no `bpy` required. 140 tests in the current suite.

---

## Architecture

```
GLB → Model-Prep → Preflight → Preset-Apply → Render → Post → Verify → Delivery
      [v0.1 ✓]    (v0.2)      (v0.3)         (v0.3)   (v0.3) (v0.2)   (v0.3)
```

Each stage is an independent Python package with a stable interface. Compose your own pipelines.
Full architecture: [docs/architecture.md](docs/architecture.md).

---

## Roadmap

- **v0.1** ✓ — Model-Prep Core (wheel detection, origin fix, ground anchor, body group, material sanitize)
- **v0.2** — Preflight & Verify (test frame + 6-gate verification + auto-fix loop)
- **v0.3** — Preset Library (5 looks × 5 cameras) + Cycles rendering
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
pip install -e ".[dev]"
pytest tests/               # 140 tests, ~5s
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

Not accepting external contributions yet — waiting for v0.3 (public launch) to stabilize the interface. **Bug reports welcome** as GitHub Issues, especially for new GLB structures that the wheel-detection Stage 2 filter rejects (paste the output of `scripts/debug_candidates.py`).

## License

MIT — see [LICENSE](LICENSE).

## Who's behind this

Built by [ZER0ONELAB](https://zer0onelab.com) as part of our cloud-render platform for DACH studios doing brand work. If you need cinema-grade renders at scale without doing the engineering yourself, we're the delivery layer.
