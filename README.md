# zer0one-cinema

**Deterministic cinema-grade rendering automation for Blender.**
GLB in, movie out — no manual scene setup, no per-model tweaking, no subscription tools required.

> **Status:** Active development. First public release: **v0.1.0** (Model-Prep Core), ETA August 2026.
> Follow [releases](https://github.com/0xxCool/zer0one-cinema/releases) or [zer0onelab.com/cinema](https://zer0onelab.com/cinema) for progress.

---

## The problem this solves

Take any 3D vehicle model from Sketchfab, throw it into Blender, run Cycles — you get a bland turntable. To get an *automotive-trailer look* (Ford v Ferrari, NfS Heat, Gran Turismo) you need:

- Wheels detected and rigged at their real rotation center (not the GLB's random origin)
- Body on the ground, not floating or sunk
- Lighting that flatters the paint (rim light for silhouette, key/fill balance)
- Camera framing that respects Rule-of-Thirds and doesn't clip parts of the car
- Post-processing (grading, DoF, motion blur, chromatic aberration, film grain)
- Verification that every rendered frame actually meets those standards

Today this takes a 3D artist several days of manual work per model. `zer0one-cinema` does it in one CLI command:

```bash
zocinema render my_car.glb --look studio_night_neon --camera push_in --output trailer.mp4
```

---

## Design principles

1. **Deterministic.** Same GLB + same preset → same output. No randomness. No manual tweaking that fails on the next model.
2. **Open source.** MIT license. Core is free forever. Premium look library is a separate paid add-on.
3. **No proprietary dependencies.** Blender/Python/numpy — nothing that requires an Adobe/Substance/Marmoset/KeyShot subscription.
4. **Every frame verified.** 6-gate cinema-grade verification runs on every render. Bad frames are flagged, not shipped.
5. **Sold by the software's owner as a real product.** This isn't a script we open-sourced — it's a ZER0ONELAB commercial offering with a free tier.

---

## Architecture (planned)

```
GLB → Model-Prep → Preflight → Preset-Apply → Render → Post → Verify → Delivery
      (auto rig)   (test fr.)  (look+camera)   (Cycles) (grade) (6 gates)  (mp4/webm)
```

Each stage is an independent Python module with a stable interface. Skip stages you don't need. Compose your own pipelines.

---

## Roadmap

- **v0.1** — Model-Prep Core (wheel detection, origin fix, ground anchor, body group)
- **v0.2** — Preflight & Verify (test frame + 6-gate verification + auto-fix loop)
- **v0.3** — Preset Library (5 looks × 5 cameras)
- **v0.4** — CLI + Blender Addon + Docker Serverless
- **v0.5** — Public Launch (landing page + 3–5 case studies)
- **v1.0** — First customer case study live on zer0onelab.com

Full plan: [docs/roadmap.md](docs/roadmap.md) (in progress).

---

## Contributing

Not accepting contributions yet — waiting for the architecture to stabilize. Star the repo to follow progress. Issues welcome for bug reports and feature requests once v0.1 ships.

## License

MIT — see [LICENSE](LICENSE).

## Who's behind this

Built by [ZER0ONELAB](https://zer0onelab.com) as part of our cloud-render platform for DACH studios doing brand work. If you need cinema-grade renders at scale without doing the engineering yourself, we're the delivery layer.
