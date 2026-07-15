# Preflight Frame QA — Automated Test-Frame Analysis & Auto-Fix

> **Kontext.** zer0one-cinema Sprint 19. Vor jedem teuren Full-Render (312+
> Frames @ Cycles auf RunPod) rendern wir 1–3 EEVEE-Preflight-Frames,
> analysieren sie per Computer-Vision, erkennen bekannte Klassen von Bugs
> (Auto abgeschnitten, Rad im Boden, Ground-Edge sichtbar, Central-Lock in
> Composition, unterbelichtet, matschig) und versuchen bis zu 3-mal
> automatisch zu korrigieren. Erst wenn der Preflight grün ist, geht der
> Job an die Farm.

---

## 1. Executive Summary (5 Sätze)

Das Preflight-Gate kombiniert **drei Datenquellen**: (a) Blender-native
Projektion der 3D-Bounding-Box in Screen-Space per
`bpy_extras.object_utils.world_to_camera_view()` — deterministisch,
kostenlos, sagt uns wo das Auto _sein müsste_; (b) einen schnellen
EEVEE-Preview-Render (typ. 3–5 s statt 40 s Cycles) als tatsächliches
Bild; (c) klassische OpenCV-Metriken auf diesem Bild (Laplacian-Variance
für Sharpness, Hough-Lines für Ground-Edge, StaticSaliencyFineGrained
für Composition). Auto-Fix-Regeln übersetzen jede Bug-Klasse in eine
konkrete Kamera- oder Ground-Änderung mit geschlossener Formel
(z. B. Pixel-Offset × 2·distance·tan(fov/2) / image_width → Meter
seitlicher Kamera-Shift). Ein **strikter Iterations-Cap von 3** verhindert
divergierende Loops (empirisch stützt sich das auf Self-Review-Studien,
die zeigen dass Runde 4+ häufig Regression bringt). Wenn nach 3 Runden
kein grüner Frame vorliegt, bricht der Job mit strukturiertem Fehler
und Zwischenergebnissen ab — kein Full-Render, kein GPU-$-Verbrauch.

---

## 2. Analyse-Techniken-Tabelle

| Bug-Klasse | Messung | Bibliothek / API | Threshold (v0.2) | Kosten |
|---|---|---|---|---|
| Auto abgeschnitten | Alle 8 Bbox-Ecken durch `world_to_camera_view()` → alle x,y ∈ [ε, 1−ε] und z > 0? | `bpy_extras.object_utils` (Blender-native) | ε = 0.04 (4 % Rand) | < 1 ms |
| Auto nicht im Frame / hinter Kamera | Mindestens eine Bbox-Ecke mit z ≤ 0 | dito | z > 0 für ALLE Ecken | < 1 ms |
| Composition central-locked | Saliency-Schwerpunkt via Image-Moments; Distanz zu den 4 Rule-of-Thirds-Power-Punkten | `cv2.saliency.StaticSaliencyFineGrained_create()`, `cv2.moments()` | Distanz zum nächsten Power-Punkt < 15 % der min(w,h) | 50–100 ms @ 1080p |
| Ground-Edge sichtbar (Ground zu klein) | Canny + `cv2.HoughLinesP()` sucht dominante horizontale Kante *unterhalb* der Auto-Bbox | OpenCV | Keine Linie mit \|θ − 90°\| < 5° und y > bbox.y_max | 30–50 ms |
| Horizon-Line falsch (Auto steht in Luft) | Bbox-Unterkante vs. detektierte Horizon-Linie | Hough + geometrischer Vergleich | Unterkante höchstens 20 px oberhalb Horizon | 30–50 ms |
| Unscharf / falsch fokussiert | Laplacian-Variance auf ROI = Auto-Bbox | `cv2.Laplacian(roi, cv2.CV_64F).var()` | > 120 (empirisch für 1080p Cycles-Renders; Kalibration je Szene) | < 10 ms |
| Unter-/Überbelichtet | Luminance-Histogramm (Y-Kanal in YCrCb): % Pixel bei 0 und 255 | `cv2.calcHist()` auf Y-Kanal | Clipping-Anteil < 2 % je Ende; Median-Y ∈ [40, 200] | < 10 ms |
| Farbstich | RGB-Histogramm Mean pro Channel; Delta max−min | `cv2.calcHist()` × 3 | \|R̄−Ḡ\|, \|Ḡ−B̄\|, \|R̄−B̄\| < 25 (bei neutraler Szene) | < 10 ms |
| Noise / Grain zu stark | σ-Estimate via `estimate_sigma` (skimage) oder Laplacian auf Flatfield-ROI | scikit-image `restoration.estimate_sigma` | σ < 6 (0–255-Skala) | 50 ms |
| Regression vs. Golden Frame | SSIM und PSNR gegen `evals/golden/*.png` | `skimage.metrics.structural_similarity`, `peak_signal_noise_ratio` | 1 − SSIM < 0.10 (moderate Changes ok), < 0.02 (Perfekt-Match); PSNR > 28 dB | 100 ms |
| Black / broken frame | FFmpeg `blackdetect` bzw. `blackframe` als Fallback | `ffmpeg -vf blackframe=amount=98:threshold=32` | Keine Detection | ~200 ms |
| Perceptual quality (optional) | BRISQUE / NIQE — no-reference | `pyiqa` (PyTorch) | BRISQUE < 40, NIQE < 5 | 300–800 ms GPU / 1–3 s CPU |

**Screen-Space-Konvention (`world_to_camera_view`)**: (0, 0) = Bild-Unten-Links,
(1, 1) = Bild-Oben-Rechts, negativer z-Wert = Punkt hinter der Kamera.
Werte außerhalb [0, 1] sind erlaubt und bedeuten „außerhalb Kadrage" —
genau das messen wir für den Frame-Cut-Off-Check.
Quelle: [Blender API Docs](https://docs.blender.org/api/current/bpy_extras.object_utils.html),
[LearnOpenGL Coordinate Systems](https://learnopengl.com/Getting-started/Coordinate-Systems).

---

## 3. Auto-Fix-Loop — Pseudocode (State-Machine)

```python
# preflight_loop.py — v0.2 draft
MAX_ITERS = 3          # empirisch: >3 selten Verbesserung, oft Regression
                       # (Restore-Assess-Repeat, arXiv 2603.26385)
NDC_MARGIN = 0.04      # 4 % Sicherheitsrand am Frame
FOV_X = camera.data.angle_x         # rad
IMG_W, IMG_H = scene.render.resolution_x, scene.render.resolution_y

state = "PLAN"
report = []

for it in range(MAX_ITERS):
    # === 1) RENDER: EEVEE preflight (5 s statt Cycles 40 s) ===
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 16          # niedrig für Preflight
    scene.render.resolution_percentage = 50      # halbe Auflösung reicht
    bpy.ops.render.render(write_still=True)
    frame = cv2.imread(preflight_path)           # BGR uint8

    # === 2) ANALYZE ===
    checks = {}

    # 2a) Bbox in Screen-Space (Blender-native, ohne CV)
    ndc = [world_to_camera_view(scene, cam, cam @ v) for v in car.bound_box]
    xs, ys, zs = zip(*ndc)
    checks["car_fully_in_frame"] = (
        min(zs) > 0
        and min(xs) > NDC_MARGIN and max(xs) < 1 - NDC_MARGIN
        and min(ys) > NDC_MARGIN and max(ys) < 1 - NDC_MARGIN
    )
    off_x = max(0, max(xs) - (1 - NDC_MARGIN)) - max(0, NDC_MARGIN - min(xs))
    off_y = max(0, max(ys) - (1 - NDC_MARGIN)) - max(0, NDC_MARGIN - min(ys))

    # 2b) Composition — Saliency vs. Rule-of-Thirds
    sal = cv2.saliency.StaticSaliencyFineGrained_create()
    _, sal_map = sal.computeSaliency(frame)
    M = cv2.moments((sal_map * 255).astype("uint8"))
    cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
    thirds = [(IMG_W / 3, IMG_H / 3), (2 * IMG_W / 3, IMG_H / 3),
              (IMG_W / 3, 2 * IMG_H / 3), (2 * IMG_W / 3, 2 * IMG_H / 3)]
    d_thirds = min(math.hypot(cx - x, cy - y) for x, y in thirds)
    checks["composition_ok"] = d_thirds < 0.15 * min(IMG_W, IMG_H)

    # 2c) Ground-Edge unter Auto?
    bbox_px = ndc_bbox_to_pixels(ndc, IMG_W, IMG_H)
    below = frame[bbox_px.y_max:, :]
    edges = cv2.Canny(cv2.cvtColor(below, cv2.COLOR_BGR2GRAY), 60, 180)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                            minLineLength=IMG_W * 0.4, maxLineGap=20)
    checks["ground_infinite"] = not any_horizontal(lines, tol_deg=5)

    # 2d) Sharpness on car ROI
    roi = frame[bbox_px.y_min:bbox_px.y_max, bbox_px.x_min:bbox_px.x_max]
    checks["sharp_enough"] = cv2.Laplacian(roi, cv2.CV_64F).var() > 120

    # 2e) Exposure
    y_chan = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)[..., 0]
    clip_lo = (y_chan == 0).mean(); clip_hi = (y_chan == 255).mean()
    checks["exposure_ok"] = clip_lo < 0.02 and clip_hi < 0.02

    report.append({"iter": it, "checks": checks})
    if all(checks.values()):
        state = "PASS"
        break

    # === 3) FIX — deterministische Regeln, kleinste plausible Änderung ===
    fixed = False

    if not checks["car_fully_in_frame"]:
        # Formel: Meter seitlicher Kamera-Shift = ndc_offset * frame_width_at_distance
        dist = (car.location - cam.location).length
        frame_w_at_dist = 2 * dist * math.tan(FOV_X / 2)
        frame_h_at_dist = frame_w_at_dist * IMG_H / IMG_W
        cam.location += cam.matrix_world.to_3x3() @ Vector((
            -off_x * frame_w_at_dist, +off_y * frame_h_at_dist, 0))
        fixed = True

    elif not checks["ground_infinite"]:
        ground.scale *= 1.5                              # Ground vergrößern
        fixed = True

    elif not checks["composition_ok"]:
        # Kleiner Kamera-Yaw so, dass Saliency-Schwerpunkt näher an nächstem
        # Power-Punkt landet. Delta in Pixeln → in rad über FOV.
        target = min(thirds, key=lambda p: math.hypot(cx - p[0], cy - p[1]))
        d_px = target[0] - cx
        cam.rotation_euler.z += (d_px / IMG_W) * FOV_X
        fixed = True

    elif not checks["sharp_enough"]:
        # DoF-Fokus auf Auto ziehen, statt Blende zu ändern
        cam.data.dof.focus_object = car
        cam.data.dof.aperture_fstop = max(cam.data.dof.aperture_fstop, 4.0)
        fixed = True

    elif not checks["exposure_ok"]:
        # 1 Stop hoch oder runter, je nach Clipping-Seite
        step = -1.0 if clip_hi > clip_lo else +1.0
        scene.view_settings.exposure += step
        fixed = True

    if not fixed:
        state = "STUCK"
        break

else:
    state = "MAX_ITERS_EXCEEDED"

if state != "PASS":
    raise PreflightFailed(state, report)   # kein Full-Render!
```

**Warum `MAX_ITERS = 3`.**  Netflix VMAF- und Self-Review-Literatur zeigen
konsistent, dass iterative Loops nach Runde 3 in *diminishing returns*
oder *Regression* umkippen; das arXiv-Paper *Restore, Assess, Repeat*
begrenzt max. Inference-Iterationen auf 8 und den Restore-Loop selbst
auf T = 4; Self-Review-Studien fixieren empirisch auf 3.
Quellen: [arXiv 2603.26385](https://arxiv.org/pdf/2603.26385),
[arXiv 2507.05598](https://arxiv.org/pdf/2507.05598).

---

## 4. Empfohlene Python-Libraries & Deps

**Minimal-Set (v0.2, muss ins `pyproject.toml`):**

```toml
[project.optional-dependencies]
preflight = [
    "opencv-contrib-python >= 4.10",   # enthält cv2.saliency (nicht in base!)
    "numpy",
    "scikit-image >= 0.24",            # SSIM, PSNR, estimate_sigma
    "Pillow",                          # I/O-Fallback wenn kein cv2
]
```

**Optional (v0.3+, wenn perceptual Metriken gewünscht):**

```toml
preflight-ml = [
    "pyiqa >= 0.1.11",                 # BRISQUE, NIQE, LPIPS, MUSIQ, TOPIQ
    "torch >= 2.3",                    # PyTorch backend
]
```

**Nicht in `pip`, sondern System-Binary:**
- `ffmpeg` — Fallback-Analyse via `blackdetect`, `blackframe`,
  `signalstats`; für v0.2 reicht ein `shutil.which("ffmpeg")`-Check.
- `blender` selbst (headless, `-b -E BLENDER_EEVEE_NEXT`).

**Wichtig**: `opencv-python` alleine reicht **nicht** — das `saliency`-Modul
ist im `opencv-contrib`-Package. Konflikt vermeiden, nie beides
installieren. Quelle: [PyImageSearch Saliency Detection](https://pyimagesearch.com/2018/07/16/opencv-saliency-detection/).

---

## 5. Failure-Handling — wann geben wir auf?

Preflight ist **niemals „bester Effort"** — entweder alle Gates grün, oder
Job bricht sauber ab, bevor Farm-$-Kosten anfallen.

| Situation | Verhalten | Exit-Code / Exception |
|---|---|---|
| Alle Checks grün innerhalb ≤ 3 Iterationen | Weiter zum Full-Render | 0 |
| Nach 3 Iterationen noch ≥ 1 Check rot | Abbruch mit `PreflightFailed(state="MAX_ITERS_EXCEEDED", report=[...])` — Report enthält Iteration-Historie pro Check | 10 |
| Fix-Regel greift nicht mehr (kein Fix mehr anwendbar, aber Checks rot) | Abbruch mit `state="STUCK"` — meist Szene-Fehler (Kamera in Wand, Auto ohne Bbox, kein Ground-Objekt) | 11 |
| EEVEE-Render crasht / liefert schwarzes Bild | 1× Retry mit `-E BLENDER_EEVEE` (Legacy), dann Abbruch `state="RENDER_FAILED"` — historisch bekannt bei bpy.ops.render mit EEVEE ([issue #54](https://github.com/TylerGubala/blenderpy/issues/54)) | 12 |
| Golden-Frame existiert, SSIM < 0.90 zu Golden | *Warning* im Report, aber kein Blocker (Szenen dürfen sich ändern) | 0 mit Warn-Flag |
| Golden-Frame existiert, 1 − SSIM > 0.10 UND `--strict-regression` gesetzt | Abbruch `state="REGRESSION"` | 13 |
| Kein Auto-Objekt zum Analysieren gefunden (falscher Node-Name / Import fehlgeschlagen) | Sofort-Abbruch, keine Iteration | 20 |

Alle Abbrüche schreiben strukturiertes JSON nach
`renders/<job>/preflight-report.json` mit: `iterations[]`, `final_state`,
`failed_checks`, `applied_fixes`, `frame_paths[]` (Contact-Sheet aller
Preflight-Frames für Nutzer-Sichtung nach `render-qa`-Skill).

---

## 6. Alle Claims mit Quellen

**Blender screen-space & camera view**
- [Blender API Docs — bpy_extras.object_utils](https://docs.blender.org/api/current/bpy_extras.object_utils.html) — `world_to_camera_view` Signatur, NDC-Konvention (0,0)=bottom-left, (1,1)=top-right, negativer z = hinter Kamera
- [b3d.interplanety — On-screen bounding box](https://b3d.interplanety.org/en/getting-an-on-screen-bounding-box-for-an-object-in-blender/) — Vergleichsansatz mit `location_3d_to_region_2d`
- [BlenderProc camera API](https://dlr-rm.github.io/BlenderProc/blenderproc.api.camera.html) — `get_view_fac_in_px`, frustum-Test
- [CGWire — Blender Scripting for Camera Animation 2026](https://blog.cg-wire.com/blender-scripting-camera-paths/) — Kamera-Script-Grundlagen
- [Blender Manual — Command Line Rendering](https://docs.blender.org/manual/en/latest/advanced/command_line/render.html) — `-E BLENDER_EEVEE_NEXT` Flag
- [BlenderArtists — EEVEE viewport animation via CLI](https://blenderartists.org/t/eevee-viewport-animation-rendering-via-commandline/1208914) — Praxis-Beispiel
- [blenderpy Issue #54](https://github.com/TylerGubala/blenderpy/issues/54) — bekannter EEVEE-Crash bei bpy.ops.render, benötigt Fallback

**OpenCV Saliency & Rule-of-Thirds**
- [OpenCV Docs — StaticSaliencyFineGrained](https://docs.opencv.org/4.x/da/dd0/classcv_1_1saliency_1_1StaticSaliencyFineGrained.html) — Center-Surround-Diff, Integralbild, Realtime
- [PyImageSearch — OpenCV Saliency Detection](https://pyimagesearch.com/2018/07/16/opencv-saliency-detection/) — Python-Idiome, `opencv-contrib` benötigt
- [datahacker.rs — Layout Scoring: Rule of Thirds](https://datahacker.rs/llm_log-019-layout-scoring-does-furniture-placement-follow-the-rule-of-thirds/) — Power-Punkte + Gaussian-Reward-Zones + Saliency-Fraction-Score
- [LearnOpenCV — Centroid via Moments](https://learnopencv.com/find-center-of-blob-centroid-using-opencv-cpp-python/) — `cv2.moments()` für Schwerpunkt

**Ground / Horizon Detection**
- [LearnOpenCV — Hough Transform](https://learnopencv.com/hough-transform-with-opencv-c-python/) — Grundlagen, `HoughLinesP` probabilistic variant
- [GeeksForGeeks — Hough Line Method](https://www.geeksforgeeks.org/python/line-detection-python-opencv-houghline-method/) — Python-Beispiel, Canny-Preprocessing

**Sharpness / Blur**
- [OpenCV Blog — Autofocus & Focus Measures](https://opencv.org/blog/autofocus-using-opencv-a-comparative-study-of-focus-measures-for-sharpness-assessment/) — Comparative-Study inkl. Laplacian-Variance
- [Sagar — Laplacian & Blur Detection](https://medium.com/@sagardhungel/laplacian-and-its-use-in-blur-detection-fbac689f0f88) — Threshold-Kalibration, ROI-Anwendung
- [rbaron — How to identify blurry images](https://rbaron.net/blog/2020/02/16/How-to-identify-blurry-images) — Praxis-Benchmarks

**Luminance / Contrast**
- [GeeksForGeeks — Histogram Analysis](https://www.geeksforgeeks.org/python/opencv-python-program-analyze-image-using-histogram/) — `cv2.calcHist`, Y-Kanal in YCrCb
- [OpenCV Courses — Image Contrast Enhancement](https://opencv.courses/blog/image-contrast-enhancement-illuminating-perspectives-with-opencv/) — YCrCb / LAB Luminance-Isolation

**FFmpeg Frame-QA**
- [FFmpeg Filters Documentation](https://ffmpeg.org/ffmpeg-filters.html) — offiziell
- [blackdetect Reference](https://ayosec.github.io/ffmpeg-filters-docs/8.0/Filters/Video/blackdetect.html) — `d`, `pic_th`, `pix_th`
- [GDELT Blog — blackdetect for commercial blocks](https://blog.gdeltproject.org/using-ffmpegs-blackdetect-filter-to-identify-commercial-blocks/) — Real-world tuning

**Perceptual IQA (optional v0.3)**
- [IQA-PyTorch (PyIQA)](https://github.com/chaofengc/IQA-PyTorch) — BRISQUE, NIQE, LPIPS, PSNR, SSIM, MUSIQ, TOPIQ — PyPI: `pip install pyiqa`
- [dataworlds — No-Reference: BRISQUE/NIQE/CLIP-IQA](https://dataworlds.substack.com/p/the-no-reference-avenger-battling) — Score-Interpretation

**Regression vs. Golden Frame**
- [Probe.dev — PSNR vs SSIM](https://www.probe.dev/resources/psnr-ssim-quality-analysis) — Threshold-Empfehlungen für Rendering-Regression
- [Netflix TechBlog — VMAF v1](https://medium.com/netflix-techblog/vmaf-v1-good-is-not-good-enough-60d7e4244ea8) — Perceptual-Quality-Referenz
- [Streaming Learning Center — VMAF Best Practices](https://streaminglearningcenter.com/encoding/best-practices-for-netflixs-vmaf-metric.html) — JND ≈ 6 Punkte, „VMAF 95 = übersteigend, VMAF 84–92 = YouTube/FB-Niveau"
- [Fora Soft — VMAF Explained](https://www.forasoft.com/learn/video-quality/articles-vqm/vmaf-explained) — Score-Mapping bad/poor/fair/good/excellent

**Iterative Auto-Fix Loops (Terminierung / Konvergenz)**
- [arXiv 2603.26385 — Restore, Assess, Repeat](https://arxiv.org/pdf/2603.26385) — MAX_ITERS-Cap, Restore-Assess-Feedback-Loop
- [arXiv 2507.05598 — Self-Review Framework](https://arxiv.org/pdf/2507.05598) — Empirische Fixierung auf 3 Iterationen
- [Roboflow Blog — Automate Camera Control](https://blog.roboflow.com/automate-camera-control/) — CV-getriebene Kamera-Adjustments

**Coordinate-System-Background**
- [LearnOpenGL — Coordinate Systems](https://learnopengl.com/Getting-started/Coordinate-Systems) — NDC, Clip-Space, Kamera-Konventionen (Kamera schaut −z)
- [Scratchapixel — 2D Coords of a 3D Point](https://www.scratchapixel.com/lessons/3d-basic-rendering/computing-pixel-coordinates-of-3d-point/mathematics-computing-2d-coordinates-of-3d-points.html) — Projektions-Mathematik
- [Blender World-to-Pixel Gist](https://gist.github.com/hsab/1bc4562d4fd3b6d29be4e5baa589420d) — Kompakte Python-Referenz
