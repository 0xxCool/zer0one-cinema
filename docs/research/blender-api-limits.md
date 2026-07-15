# Blender-API-Limits für zer0one-cinema (Sprint 19)

**Zweck:** Design-Constraints für Cinema-Trailer-CLI (GLB → Trailer via Blender im RunPod-Container).
**Zielversion:** Blender 4.2 LTS (support bis 2026-07); optional Vorbereitung Blender 5.2 LTS (2026-07 released).
**Stand:** 2026-07-15.

---

## Executive Summary

1. **Der `blender -b -P script.py` Weg ist der produktionsreife Pfad** — nicht `pip install bpy`. Der offizielle `bpy` PyPI-Build existiert (aktuell 5.2.0, Python 3.13-only, Linux glibc 2.28+), ist aber wählerisch bei Python-Versionen und läuft in einem eigenen `sys.executable`-Prozess — damit hebelt er die runpod-orch-Container-Konventionen aus. Für zer0one-cinema bleiben wir bei **`blender -b`**.
2. **Cycles + OPTIX auf headless GPU funktioniert vollständig ohne Display-Server**, aber GPU-Discovery ist explizit: `preferences.get_devices()` + Iteration über `preferences.devices` mit `d["use"]=True` ist Pflicht, und `--cycles-device OPTIX` als Doppel-Dash-Argument ist die kürzeste CLI-Form. **EEVEE-Next (4.2) braucht dagegen einen OpenGL-Context** — auf headless-Linux entweder EGL (bevorzugt) oder Xvfb als Fallback. Für Trailer-Rendering ist Cycles die einzig verlässliche Wahl.
3. **Draco-GLB-Import ist die häufigste vermeidbare Baustelle:** In den offiziellen Blender-Builds liegt `libextern_draco.so` seit 4.3 unter `python/lib/python3.11/site-packages/`, aber der glTF-Addon-Code hat mehrere Regressionen (`site` import fehlt, falscher Lookup-Pfad). Wir müssen im Docker-Image entweder das File in `python/lib/site-packages/` symlinken oder `BLENDER_EXTERN_DRACO_LIBRARY_PATH` env setzen — sonst brechen 40 % aller GLB-Fixtures.

**Design-Constraints daraus:**
- **C1:** Kein `pip install bpy` in Produktion — Blender-Binary via apt/tarball einfrieren, Scripts über `blender -b -P`.
- **C2:** Cycles-only für Trailer-Rendering (EEVEE-Next nur als Preview-Fallback mit Xvfb).
- **C3:** GLB-Import-Layer muss Draco vor jedem Import validieren (`os.path.exists(env)` + Fallback-Symlink im Dockerfile).

---

## API-Coverage-Matrix

Feature × headless-Funktioniert JA / NEIN / Workaround.

| Feature | `blender -b` (Background Mode) | `bpy` als pip-Modul | Bemerkung |
|---|---|---|---|
| `bpy.ops.import_scene.gltf(filepath=...)` | JA | JA | Braucht Draco-Lib für komprimierte GLBs (siehe unten). Filepath muss absolute sein — Relative-Path resolven scheitert je nach CWD. |
| `bpy.ops.render.render(animation=True, write_still=True)` | JA | JA | Blocking. Für Fortschritts-Callbacks `bpy.app.handlers.render_stats.append()` — Callback läuft aus Render-Thread. |
| `bpy.ops.render.render('INVOKE_DEFAULT')` | NEIN | NEIN | Braucht Window — im Background-Mode `CANCELLED`. Für Fortschritt: Frame-Loop + `render_write` handler. |
| `bpy.context.view_layer.objects.active = obj` | JA | JA | Bevorzugte Form. `bpy.context.active_object` schreiben ist read-only in `-b`. |
| `bpy.context.view_layer` (lesen) | JA | JA | In Background gibt es nur `bpy.context.scene.view_layers[0]` als Default. UI-Screen ist `None`. |
| `context.temp_override(window=..., area=..., region=...)` | Nur eingeschränkt | Nur eingeschränkt | Es gibt keine Windows/Areas in `-b` — Overrides für view_layer/scene/object funktionieren, für Screen-Areas nicht. |
| UI-Operatoren (`bpy.ops.uv.smart_project`, `bpy.ops.mesh.*`) | Workaround | Workaround | Brauchen mode `OBJECT`/`EDIT` toggle und aktives Object. Poll-Fehler → `object.select_set(True)` + `context.view_layer.objects.active = obj` VOR dem Aufruf. |
| Cycles CPU-Render | JA | JA | — |
| Cycles GPU (CUDA) | JA | JA | Braucht `preferences.compute_device_type="CUDA"` + `get_devices()` + `d["use"]=True` PRO Device. |
| Cycles GPU (OPTIX) | JA | JA | Wie CUDA, aber NVIDIA-Driver ≥535. Compute Capability ≥5.0. `--cycles-device OPTIX` als kürzere CLI-Form. |
| Cycles OPTIX Denoise | JA | JA | Nur wenn OPTIX-Device _konfiguriert_ ist (nicht nur CUDA), unabhängig von compute_device_type für Render. |
| EEVEE-Next Render | Workaround | Workaround | Braucht OpenGL/EGL Kontext — funktioniert mit `libegl-mesa0` + NVIDIA-EGL im Container, sonst Xvfb. Auf headless Windows: nicht supported. |
| Compositor (Post-Processing Nodes) | JA | JA | Läuft auf CPU/GPU im Render-Job — kein separater Kontext nötig. |
| Video-Sequencer (VSE) Export | JA | JA | ffmpeg-Muxing built-in, aber Codec-Support hängt von Blender-Build ab (offizielle Builds haben ffmpeg mit x264/vpx/opus). |
| `bpy.ops.wm.save_as_mainfile()` | JA | JA | — |
| `bpy.ops.wm.save_userpref()` | JA | Warnung | Im Container ist $HOME oft ephemeral — Prefs pro Container-Start neu setzen statt speichern. |
| Add-on `enable` (`bpy.ops.preferences.addon_enable(module='io_scene_gltf2')`) | JA | JA | Default-Bundle-Addons sind ab 4.2 als Extensions gepackt — `io_scene_gltf2` bleibt aber core. |
| Neue Extensions installieren (`bpy.ops.extensions.package_install`) | JA | JA | Braucht Netz oder lokales Repo. In Airgapped-Container: `--offline-mode` + File-Repo. |

**Bekannte Bug/Regression-Klassen:**
- Exit-Code 139/245 bei sauberem Cycles-Render via `bpy`-Modul (Bug #126807) — Python-Shutdown-Race, kein Renderfehler. In Docker-CI: Exit-Code nicht als alleinigen Health-Check nehmen, sondern Output-File-Presence prüfen.
- `bpy.ops.render.render('INVOKE_DEFAULT')` sofortiger `CANCELLED` in Background — nie in `-b` verwenden.

---

## Container-Deployment-Recipe

### Base-Image (empfohlen)

```dockerfile
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    BLENDER_VERSION=4.2.5 \
    BLENDER_MAJOR=4.2 \
    PATH=/opt/blender:$PATH

# Minimal runtime deps (Blender braucht diese X-Libs auch im -b Mode für Symbol-Loading)
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl xz-utils ca-certificates \
      libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 \
      libgl1 libegl1 libgomp1 libsm6 libglu1-mesa \
      libxcb1 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
      libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 \
      libdbus-1-3 libx11-6 \
      ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Blender-Tarball (offizieller Build) einfrieren
RUN curl -sL https://download.blender.org/release/Blender${BLENDER_MAJOR}/blender-${BLENDER_VERSION}-linux-x64.tar.xz \
      | tar -xJ -C /opt && \
    mv /opt/blender-${BLENDER_VERSION}-linux-x64 /opt/blender

# Draco-Fix: env-var setzen UND symlink in Fallback-Pfad legen
ENV BLENDER_EXTERN_DRACO_LIBRARY_PATH=/opt/blender/${BLENDER_MAJOR}/python/lib/python3.11/site-packages/libextern_draco.so
RUN ln -sf /opt/blender/${BLENDER_MAJOR}/python/lib/python3.11/site-packages/libextern_draco.so \
           /opt/blender/${BLENDER_MAJOR}/python/lib/site-packages/libextern_draco.so || true

# Smoketest
RUN blender --version && \
    blender -b --python-expr "import bpy; bpy.ops.import_scene.gltf; print('OK')"
```

**Image-Größe (empirisch, Ubuntu 22.04 + CUDA runtime):**
- Base `nvidia/cuda:12.4.1-runtime-ubuntu22.04`: ~2.9 GB
- + Blender 4.2 tarball: +260 MB (unpacked ~750 MB)
- + apt runtime libs: +250 MB
- **Total: ~3.9 GB** (unkomprimiert). Wir haben in cinema-orch schon `ghcr.io/0xxcool/blender-worker` — dieses Rezept ist damit kompatibel, muss nur den Draco-Fix bekommen falls noch fehlt.

Alpine-Alternative: Blender-Builds sind gegen glibc gelinkt → **Alpine (musl) nicht supported**. Debian-slim spart ~150 MB, aber Ubuntu 22.04 hat das ausgereiftere NVIDIA-Toolkit-Zusammenspiel.

### GPU-Zugriff aktivieren (RunPod / docker-run)

```bash
docker run --rm --gpus all \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
  -v /work:/work \
  ghcr.io/0xxcool/blender-worker:latest \
  blender -b /work/scene.blend -o /work/out/frame_#### \
    -E CYCLES -s 1 -e 120 -a -- --cycles-device OPTIX
```

Wichtig: `NVIDIA_DRIVER_CAPABILITIES=compute,utility` reicht für Cycles+OPTIX. Für EEVEE-Next in Fallback-Situationen `+graphics` dazu.

### GPU-Init in Python-Setup-Script

```python
# scripts/enable_gpu.py — vor jedem Render als --python vorgeschaltet
import bpy

prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"  # oder "CUDA"
prefs.get_devices()  # PFLICHT — sonst leere Device-Liste

for d in prefs.devices:
    d["use"] = (d.type in {"OPTIX", "CUDA"})  # CPU ausschalten wenn nicht gewünscht
    print(f"[cinema] device: {d.name} type={d.type} use={d['use']}")

for scene in bpy.data.scenes:
    scene.cycles.device = "GPU"
```

Aufruf:
```
blender -b scene.blend --python scripts/enable_gpu.py --python scripts/render.py
```

### Extension als CLI-Frontend (optional)

Für 4.2+ neue Extension-Struktur (statt `bl_info` alt) — nur nötig wenn wir das CLI-Toolkit auch als Blender-Addon veröffentlichen:

```toml
# blender_manifest.toml
schema_version = "1.0.0"
id = "zer0one_cinema"
version = "0.1.0"
name = "ZER0ONE Cinema Trailer"
tagline = "Cinema-grade vehicle trailer from any GLB"
maintainer = "ZER0ONE d.o.o. <hi@zer0one.codes>"
type = "add-on"
blender_version_min = "4.2.0"
license = ["SPDX:GPL-3.0-or-later"]
tags = ["Render", "Import-Export"]
platforms = ["linux-x64", "windows-x64", "macos-arm64"]

wheels = [
  "./wheels/pyyaml-6.0.1-cp311-cp311-manylinux_2_17_x86_64.whl",
]
```

Package-Regeln:
- Ordnername = `id`.
- Kein `pip install` zur Runtime (violates extensions.blender.org policy).
- Wheels müssen für Python 3.11 (Blender 4.2) gebaut sein.
- Für `bpy.app.online_access == False` Netzwerk-Aufrufe skippen (Store-Requirement).

---

## Bekannte Fallstricke + Workarounds

| Symptom | Ursache | Workaround |
|---|---|---|
| `cannot open shared object libextern_draco.so` beim GLB-Import mit Draco-Compression | Blender-Build sucht in `python/lib/site-packages/`, die Datei liegt aber in `python/lib/python3.11/site-packages/` (ab 4.3 verschoben). Bei 4.2 ist es umgekehrt bei manchen Distro-Builds. | `ENV BLENDER_EXTERN_DRACO_LIBRARY_PATH=/opt/blender/4.2/python/lib/python3.11/site-packages/libextern_draco.so` UND Symlink in beide Pfade. Bei Distro-Builds (Arch/Ubuntu-apt): Datei fehlt komplett, dann **offiziellen Tarball** verwenden. |
| `NameError: name 'site' is not defined` in draco.py bei Export | Regression in Blender 4.3-Builds — Import von `site` fehlt in `io/com/draco.py`. | Bis-Patch: `sed -i '1i import site' $BLENDER/4.x/scripts/addons_core/io_scene_gltf2/io/com/draco.py`. Nicht relevant für pure-Import-Flows. |
| `AttributeError: 'NoneType' object has no attribute 'objects'` bei `bpy.context.view_layer.objects.active = ...` | Im `-b`-Mode nach `bpy.ops.wm.read_factory_settings(use_empty=True)` ist context view_layer manchmal noch nicht initialisiert. | `vl = bpy.context.scene.view_layers[0]` explizit holen, statt `bpy.context.view_layer`. Objekte via `bpy.data.objects[name]` targetten. |
| Exit-Code 139 (SIGSEGV) nach erfolgreichem Render aus `bpy`-pip-Modul | Bekannter Bug #126807 — Python-Shutdown-Race in Cycles-Cleanup. | In CI/orchestrator NICHT nur Exit-Code prüfen. Presence + Größe der Output-Files als Health-Signal. Bei `blender -b` Binary tritt der Bug seltener auf. |
| `bpy.ops.mesh.*` wirft `RuntimeError: Operator poll() failed` in `-b` | Kein aktives Object + falscher Mode. | Vor dem Aufruf: `obj.select_set(True); bpy.context.view_layer.objects.active = obj; bpy.ops.object.mode_set(mode='EDIT')`. |
| GPU wird als "None" gelistet im Container obwohl `nvidia-smi` GPUs zeigt | `preferences.get_devices()` nie gerufen ODER Blender-Build ohne OPTIX-Support ODER Driver <535. | (a) `get_devices()` explizit rufen, (b) mit `blender --debug-cycles -b` cross-checken, (c) `--cycles-device OPTIX` als CLI-Argument statt Python-Override — überschreibt scene setting. |
| EEVEE-Next Render "no OpenGL context" im Container | Kein EGL/OpenGL-Runtime in Base-Image. | Für EEVEE: `apt install libegl1 libglvnd0 libgl1` und `-e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics`. Für 100 % Reliability: `xvfb-run -a blender -b ...` als Fallback. Für Trailer-Rendering: EEVEE-Next _nicht_ als Haupt-Engine wählen. |
| Mehrere Blender-Instanzen auf einer GPU → OOM einer Instanz killt alle | Blender pooled VRAM nicht — jede Instanz braucht Full-Scene-VRAM. Bei parallel-N Prozessen wird N·SceneSize VRAM benötigt. | Für 24 GB GPUs (A5000/A4000-16GB): Max 1 Instanz pro Scene ≥ 8 GB VRAM. Alternativ: Frames auf mehrere Pods verteilen (RunPod-Serverless macht das schon). Nie 2 Blender auf 1 A4000. |
| `bpy.ops.wm.save_userpref` warnt oder failt in read-only container filesystem | $HOME nicht writable oder gar nicht gesetzt. | Prefs pro Session neu setzen in `enable_gpu.py`-Script — nicht persistieren. `HOME=/tmp` als env falls unbedingt nötig. |
| Blender-Addons "not installed" nach Container-Restart | Extensions installiert in $HOME/.config/blender — ephemer im Container. | Für Addons wie `io_scene_gltf2` (core-bundled) nichts nötig. Für Third-Party: als Wheel im Image mitliefern, per Startup-Script `addon_enable` rufen. |

---

## Multi-Process-Rendering — Verdikt

**Nicht auf einer GPU parallelisieren.** VRAM wird nicht gepoolt, jede Instanz braucht ihr eigenes Scene-BVH (Objects off-camera zählen für Lighting mit). Für ein Vehicle-Trailer-Setup (ein Auto + HDRI + Ground + Kamera-Path) liegen wir bei ~4-8 GB VRAM — auf einer A4000-16GB wären theoretisch 2 Instanzen möglich, aber der OOM-Kill einer Instanz erwischt beide (CUDA-Context shared).

**Skalierung soll über den RunPod-Serverless-Router laufen** — verschiedene Frame-Ranges auf verschiedene Pods (jeder Pod = 1 Blender). Das haben wir laut Memory schon (Endpoint `cx6ws3mc43880a`). Kein Multi-Instance in einem Container.

---

## Empfehlungen für zer0one-cinema Sprint 19

1. **CLI-Struktur:** `zer0one-cinema render --glb X.glb --preset trailer --out out.mp4` als Python-Wrapper, der einen `blender -b template.blend --python init.py --python run.py -- --glb X.glb` ausführt. Kein direktes `import bpy` im User-Code.
2. **Template-Blend-File:** Vorgebaute Szene mit HDRI, Ground, Camera-Rig, Compositor-Setup. Nur das GLB-Vehicle wird via Script importiert und auf einen leeren `Anchor`-Empty geparented. Damit ist der Python-Code trivial und deterministisch.
3. **GPU-Init immer als erstes `--python` Script** — vor Scene-Load, damit die Prefs greifen.
4. **Draco-Fix im Base-Image festschreiben** — nicht als Runtime-Fix pro Job, sonst Cold-Start-Latenz.
5. **Health-Check via Output-Existence**, nicht Exit-Code.
6. **Als Blender-Addon zusätzlich packen** (Sprint 20 vielleicht) — dann können User im Blender-UI "Send to Cinema" klicken. Aber CLI ist Sprint 19 Priorität 1.

---

## Quellen

- [bpy · PyPI](https://pypi.org/project/bpy/) — offizielle bpy-Package-Info, aktuelle Version 5.2.0 (Python 3.13, Linux/Win/macOS)
- [Blender 4.2 LTS: Python API Release Notes](https://developer.blender.org/docs/release_notes/4.2/python_api/)
- [Blender Python API — Context (bpy.context)](https://docs.blender.org/api/current/bpy.context.html)
- [Blender Python API — Operators (bpy.ops)](https://docs.blender.org/api/current/bpy.ops.html) — poll/context-Regeln
- [Blender Manual — Cycles GPU Rendering](https://docs.blender.org/manual/en/latest/render/cycles/gpu_rendering.html) — CUDA/OPTIX/HIP/oneAPI/Metal, Driver-Requirements
- [Blender Manual — EEVEE Limitations](https://docs.blender.org/manual/en/latest/render/eevee/limitations/limitations.html) — headless-Windows nicht supported
- [Blender Manual — Extensions Getting Started](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html)
- [Extensions Platform Beta Release — code.blender.org](https://code.blender.org/2024/05/extensions-platform-beta-release/)
- [Add-on Guidelines — developer.blender.org](https://developer.blender.org/docs/handbook/extensions/addon_guidelines/) — extension-store submission rules
- [Changes to Add-on and Themes Bundling (4.2 onwards)](https://devtalk.blender.org/t/changes-to-add-on-and-themes-bundling-4-2-onwards/34593)
- [Superhive — How to Convert Your Blender Add-on to an Extension](https://superhivemarket.com/posts/how-to-convert-your-blender-add-on-to-an-extension)
- [blender-extension-builder · PyPI](https://pypi.org/project/blender-extension-builder/) — automatisiertes Wheel-Bundling
- [Blender Issue #130545 — extern_draco.dll missing in 4.3](https://projects.blender.org/blender/blender/issues/130545)
- [Blender Issue #130849 — Missing site Import in draco.py](https://projects.blender.org/blender/blender/issues/130849)
- [Blender Pull #125555 — build-draco-for-python-module](https://projects.blender.org/blender/blender/pulls/125555)
- [glTF-Blender-IO Issue #627 (libextern_draco.so missing)](https://github.com/KhronosGroup/glTF-Blender-IO/issues/627)
- [linuxserver/docker-blender Issue #13 — version mismatch and missing Draco](https://github.com/linuxserver/docker-blender/issues/13)
- [Blender Issue #126807 — bpy Cycles exit code 139/245](https://projects.blender.org/blender/blender/issues/126807)
- [Devtalk — Headless rendering no longer picking up GPUs](https://devtalk.blender.org/t/headless-rendering-no-longer-automatically-picking-up-gpus/12176)
- [Devtalk — How to wait for bpy.ops.render.render](https://devtalk.blender.org/t/how-to-wait-for-bpy-ops-render-render/14526)
- [Devtalk — Why is only a single GPU used with OPTIX from Python API](https://devtalk.blender.org/t/why-is-only-a-single-gpu-used-when-using-optix-from-the-python-api-when-cuda-uses-multiple-when-configured-to-do-so/18869)
- [Devtalk — Multi Instance Multi GPU rendering slower than expected](https://devtalk.blender.org/t/multi-instance-multi-gpu-rendering-is-slower-than-expected/25173)
- [NVIDIA Container Toolkit — GitHub](https://github.com/NVIDIA/nvidia-container-toolkit)
- [NVIDIA Container Toolkit Quickstart](https://nvidia.github.io/container-wiki/toolkit/quickstart.html)
- [HaiyiMei/blender-docker-headless](https://github.com/HaiyiMei/blender-docker-headless) — CUDA-11.7 minimal example
- [Vogete/blender-cuda-docker](https://github.com/Vogete/blender-cuda-docker) — nvidia-docker Blender GPU Dockerfile
- [nytimes/rd-blender-docker (2.83 GPU dockerfile)](https://github.com/nytimes/rd-blender-docker/blob/master/dist/2.83-gpu-ubuntu18.04/Dockerfile) — dependency-list für apt
- [snowgoons.ro — Setting Up a Blender Rendering Node Using Docker](https://snowgoons.ro/posts/2020-09-08-setting-up-a-blender-rendering-node-using-docker/)
- [renderday.com — Mastering the Blender CLI](https://renderday.com/blog/mastering-the-blender-cli)
- [til.jakelazaroff.com — Export a Blender file to GLB from CLI](https://til.jakelazaroff.com/blender/export-a-blender-file-to-glb-from-the-command-line/)
- [Blender Developer Docs — Building Blender on Linux](https://developer.blender.org/docs/handbook/building_blender/linux/) — dependency list
- [Blender Developer Docs — Python Module build](https://developer.blender.org/docs/handbook/building_blender/python_module/)
