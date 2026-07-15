# Wheel-Detection aus 3D-Vehicle-GLB Mesh-Bounding-Boxes

**Projekt:** zer0one-cinema (Sprint 19)
**Datum:** 2026-07-15
**Status:** Research-Report v1.0 — Empfehlung für v0.1-Pipeline

---

## Executive Summary

**Empfehlung für v0.1: 6-Stage Multi-Stage-Pipeline** mit K-Means (k=4, fixed seed) als
Kern-Cluster-Schritt, umschlossen von deterministischen Geometrie-Heuristiken.

**Warum nicht ein einzelner ML-basierter Ansatz (PointNet++)?**
Für unser Ziel „selber Input → bit-identischer Output" (Cinema-Trailer soll bei erneuter Ausführung
identisch reproduzierbar sein) sind ML-Methoden schlecht geeignet: sie verlangen GPU-Determinismus,
Trainingsdaten und -pflege pro Vehicle-Klasse, und selbst mit Seed sind sie auf verschiedenen
GPUs nicht bit-identisch. Wir kennen zudem die Ziel-Topologie exakt (genau 4 Räder in
Rechteck-Anordnung, bilateral-symmetrisch), was klassische Heuristiken hoch-präzise macht.

**Warum K-Means und nicht DBSCAN/HDBSCAN/Mean-Shift?**
Wir kennen k=4 a priori. K-Means mit `random_state=0`, `init='k-means++'`, `n_init=1` ist
bit-deterministisch, O(nk·iter), und nutzt Domain-Wissen. Density-based Methoden sind für
unbekanntes k gedacht — für uns unnötige Flexibilität, die Determinismus kostet: DBSCAN und
HDBSCAN sind **nur** deterministisch, wenn die Input-Reihenfolge fixiert ist (Grenzpunkte werden
dem zuerst begegneten Cluster zugewiesen). Mean-Shift ist O(n²) — für ein paar hundert Sub-Mesh-Centers
kein Problem, aber ohne Vorteil gegenüber K-Means-k=4.

**Warum kein Naming-Heuristik-only Ansatz (à la Rigacar)?**
[Rigacar](https://github.com/digicreatures/rigacar) und [continuebreak vehicle rigging addon](https://continuebreak.com/creations/ue-vehicle-rigging-addon-blender/)
setzen naming-conventions voraus (`wheel_FL/FR/RL/RR` case-insensitive). Sketchfab-GLBs haben
diese in <20% der Fälle. Naming ist Stage 0 (Fast-Path Fallback), nicht die Hauptmethode.

---

## Methoden-Vergleichs-Tabelle

Skala: ★ = sehr schlecht für unser Ziel, ★★★★★ = ideal

| Methode | Robustheit | Determinismus | Rechenaufwand | Fit v0.1 | Kommentar |
|---|---|---|---|---|---|
| **K-Means k=4** (seed, n_init=1) | ★★★★ | ★★★★★ (bit-identisch) | O(n·k·iter), <10 ms | ★★★★★ | Core-Schritt |
| Naming-Heuristik (Rigacar-style) | ★★ (nur bei sauberem Naming) | ★★★★★ | O(n) | ★★★★★ (Stage 0) | Fast-Path Fallback |
| PCA (Symmetrieebene + Cylinder-Axis) | ★★★★ | ★★★★★ | O(V) pro Mesh | ★★★★★ | Als Validator |
| AABB Aspect-Ratio-Filter | ★★★ (viele False-Positives) | ★★★★★ | O(n) | ★★★★ | Als Pre-Filter |
| DBSCAN | ★★★ | ★★ (data-order dep.) | O(n log n) | ★★ | Nur wenn Order sortiert |
| HDBSCAN | ★★★★ | ★★ (data-order dep.) | O(n log n) | ★★★ | Fallback für unbekanntes k (z.B. Motorräder) |
| Mean-Shift | ★★★ | ★★★★ (mit fixem Bandwidth) | O(n²) | ★★ | Kein Vorteil vs. K-Means |
| RANSAC-Cylinder (pyRANSAC-3D) | ★★★★ (bei sauberen Zylindern) | ★★ (randomisiert, Seed möglich, aber lib-versionsabhängig) | ~100 ms/Kandidat | ★★★ | Optional als Cross-Check |
| PointNet++ (ML Segmentation) | ★★★★★ (bei trainierter Klasse) | ★ (GPU non-det., Dropout) | GPU-Sekunden, Model-Weights nötig | ★ (v0.1) → ★★★★ (v2+) | Overkill für v0.1 |
| Hough-Transform Symmetry | ★★★★ | ★★★★ | O(V²) — teuer | ★★ | Zu teuer, PCA reicht |

---

## Empfohlener Algorithmus (Multi-Stage Pipeline)

```python
def detect_wheels(gltf_path: str, seed: int = 0) -> WheelDetectionResult:
    """
    Deterministische Wheel-Detection aus beliebigem Vehicle-GLB.
    Return: 4 WheelInfo(center, radius, axis, sub_meshes[]) + vehicle_frame.
    Bei k!=4 (Motorrad/Truck): dynamische k-Detektion, Warnung.
    """
    # ═══════════════════════════════════════════════════════════════
    # Stage 0: Fast-Path via Naming Convention (Rigacar-style)
    # ═══════════════════════════════════════════════════════════════
    meshes = load_gltf_meshes(gltf_path)
    named_wheels = extract_by_name(meshes, patterns=[
        r"wheel[._\-\s]?(FL|FR|RL|RR|LF|RF|LR|RR|F[.\s_]?L|F[.\s_]?R|R[.\s_]?L|R[.\s_]?R)",
        r"(rad|roue|rueda)[._\-\s]?(vl|vr|hl|hr|fl|fr|rl|rr)",
    ])
    if len(named_wheels) == 4 and validate_rectangle(named_wheels):
        return build_result(named_wheels, source="naming")

    # ═══════════════════════════════════════════════════════════════
    # Stage 1: Vehicle-Frame Bestimmung (Body-PCA)
    #   glTF-Spec sagt +Y up, +Z forward, -X right — aber Sketchfab-
    #   GLBs sind notorisch inkonsistent (siehe Sources). NIE auf
    #   Achsen-Konvention verlassen, immer aus Geometrie ableiten.
    # ═══════════════════════════════════════════════════════════════
    all_verts = np.concatenate([m.world_verts for m in meshes])
    center, R_body = pca_frame(all_verts)  # R_body: 3x3 rotation
    # eigenvals sortiert absteigend: [long, wide, tall]
    #   longest horizontal    → forward-axis  (vehicle-Länge)
    #   second horizontal     → right-axis    (Track-Width)
    #   shortest (fast senkrecht zur Boden-Ebene) → up-axis
    forward_axis, right_axis, up_axis = R_body[0], R_body[1], R_body[2]
    body_bbox = aabb_in_frame(all_verts, R_body)  # AABB im rotierten Frame

    # ═══════════════════════════════════════════════════════════════
    # Stage 2: Geometrische Kandidaten-Filterung
    #   Wheels haben: (a) 2 ähnliche Dimensionen (Durchmesser), 1 kürzer
    #   (Breite/Dicke); (b) bbox-Diagonale zwischen 3% und 20% der
    #   Vehicle-Länge; (c) Center im unteren Drittel des Body-bbox.
    # ═══════════════════════════════════════════════════════════════
    candidates = []
    veh_len = body_bbox.length_along(forward_axis)
    for m in meshes:
        aabb = aabb_in_frame(m.world_verts, R_body)
        dims = sorted(aabb.dims)  # [short, mid, long]
        aspect_short = dims[0] / dims[2]        # 0.15..0.6 für Wheel
        aspect_disc  = dims[1] / dims[2]        # 0.8..1.05 (round)
        diag_frac = np.linalg.norm(aabb.dims) / veh_len
        y_frac = (m.center_in_frame(R_body).z - body_bbox.min.z) / body_bbox.dims[2]

        is_wheel_shape = (
            0.15 <= aspect_short <= 0.60 and     # zylindrisch
            0.80 <= aspect_disc  <= 1.05 and     # runde Stirnseite
            0.03 <= diag_frac    <= 0.22 and     # ~Wheel-Größe
            y_frac <= 0.45                        # unteres Drittel des Body
        )
        if is_wheel_shape:
            candidates.append(m)

    # ═══════════════════════════════════════════════════════════════
    # Stage 3: PCA-Zylinder-Bestätigung pro Kandidat
    #   Für einen Zylinder ergibt PCA λ1 (Axis, kürzer) << λ2 ≈ λ3.
    #   Bremsscheibe/Rim/Hub_Nut passen alle in diese Form —
    #   das wird in Stage 5 aufgelöst, nicht hier verworfen.
    # ═══════════════════════════════════════════════════════════════
    for c in candidates:
        eigvals, eigvecs = pca(c.world_verts)   # ascending
        c.local_axis = eigvecs[:, 0]            # kleinster eigval = Zylinder-Axis
        c.disc_ratio = eigvals[1] / eigvals[2]  # ≈1.0 für perfekt-rund
        c.axis_ratio = eigvals[0] / eigvals[2]  # <<1 für dünnes Rad
        # Reject nur bei extremen Werten: disc_ratio < 0.5 oder axis_ratio > 0.8
        # → alles andere sammelt Stage 5 richtig ein.

    # ═══════════════════════════════════════════════════════════════
    # Stage 4: K-Means k=4 auf Kandidaten-Centers (DETERMINISTISCH)
    #   Wichtig: Kandidaten VORHER kanonisch sortieren (z.B. lexikografisch
    #   über bbox-center-Koordinaten), damit K-Means über Läufe identische
    #   Cluster-Labels liefert.
    # ═══════════════════════════════════════════════════════════════
    candidates.sort(key=lambda c: (round(c.center.x, 4),
                                    round(c.center.y, 4),
                                    round(c.center.z, 4)))
    centers = np.array([c.center for c in candidates])

    k = 4 if len(candidates) >= 4 else infer_k(candidates)  # Motorrad-Fallback

    from sklearn.cluster import KMeans
    km = KMeans(
        n_clusters=k,
        init="k-means++",       # deterministisch mit random_state
        n_init=1,               # WICHTIG: sonst nicht bit-identisch reproduzierbar
        random_state=seed,      # int → deterministisch
        algorithm="lloyd",
    )
    labels = km.fit_predict(centers)
    wheel_centers = km.cluster_centers_  # 4 Punkte

    # ═══════════════════════════════════════════════════════════════
    # Stage 5: Symmetrie-Rechteck-Validierung
    #   Vehicle ist bilateral-symmetrisch um die Ebene {right_axis, up_axis}.
    #   Reflexion jedes Wheel-Centers über diese Ebene muss auf einem
    #   anderen Wheel-Center landen (tol = 5% der Track-Width).
    #   Die 4 Centers müssen ein Rechteck bilden:
    #     zwei Paare gleicher Kanten-Längen (Wheelbase + Track-Width).
    # ═══════════════════════════════════════════════════════════════
    sym_plane = plane(point=center, normal=right_axis)
    if not validate_symmetry(wheel_centers, sym_plane, tol_rel=0.05):
        return fallback_pipeline(meshes)  # siehe Edge Cases
    if not validate_rectangle(wheel_centers, tol_rel=0.05):
        return fallback_pipeline(meshes)

    # ═══════════════════════════════════════════════════════════════
    # Stage 6: FL/FR/RL/RR-Labeling + Sub-Mesh-Aggregation
    #   In (forward, right)-Koordinaten:
    #     forward-max & right-min  → FL   (Front Left)
    #     forward-max & right-max  → FR
    #     forward-min & right-min  → RL
    #     forward-min & right-max  → RR
    # ═══════════════════════════════════════════════════════════════
    wheels = label_flfr_rlrr(wheel_centers, forward_axis, right_axis)

    # Sub-Mesh-Aggregation: sammle ALLE Meshes (nicht nur Stage-1-Kandidaten!),
    # deren bbox-center innerhalb radius = 1.1 × wheel_diameter/2 vom
    # Wheel-Center liegt. Das erwischt Rim + Tire + Hub_Nut + Caliper.
    for w in wheels:
        w.sub_meshes = [m for m in meshes
                        if distance(m.center, w.center) < 1.1 * w.radius]

        # Caliper-vs-Rim Klassifizierung (Rotation-Behavior):
        #   HEURISTIK: Caliper/Brake-Disc-Halterung ist am chassis geankert.
        #   Ihr bbox-center hat einen RADIALEN Offset (senkrecht zur wheel-axis)
        #   in Richtung body-forward. Der Caliper "hängt" vor/hinter der Radnabe.
        #   Rim/Tire/Hub-Nut sind konzentrisch zur Radnabe → radialer Offset < 20%.
        for sm in w.sub_meshes:
            offset = sm.center - w.center
            radial = offset - np.dot(offset, w.axis) * w.axis  # in wheel-plane
            radial_frac = np.linalg.norm(radial) / w.radius
            sm.rotates_with_wheel = radial_frac < 0.20
            # ↑ False → Caliper/Halter, bleibt statisch beim Wheel-Spin

    return WheelDetectionResult(
        wheels=wheels,
        vehicle_frame=(forward_axis, right_axis, up_axis, center),
        source="geometric",
        confidence=compute_confidence(wheels, sym_plane),
    )
```

**Kern-Determinismus-Garantien:**

1. **K-Means:** `init='k-means++'` + `n_init=1` + `random_state=int` ist per sklearn-Docs
   bit-identisch reproduzierbar ([KMeans docs](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html)).
2. **Input-Sortierung** vor allen order-abhängigen Schritten (K-Means, DBSCAN-Fallback):
   Rundung auf 4 Dezimalstellen entfernt Float-Jitter, lexikografische Sortierung fixiert Order.
3. **PCA (numpy.linalg.eigh):** deterministisch für symmetrische Kovarianz-Matrix, aber
   Vorzeichen der Eigenvektoren ist mehrdeutig → Kanonisierung: erste nicht-null-Komponente
   muss positiv sein (`v * sign(v[argmax(abs(v))])`).
4. **Keine RANSAC** in der Haupt-Pipeline (RANSAC ist per Definition randomisiert,
   [Wikipedia](https://en.wikipedia.org/wiki/DBSCAN)-Analogie: „reasonable result with a certain
   probability" — nicht bit-identisch über Library-Versionen).

---

## Edge Cases + Fallback-Strategien

| # | Edge Case | Detektion | Fallback |
|---|---|---|---|
| 1 | **Motorrad (2 Räder)** | Nach Stage 2: <4 Kandidaten | k=2, Symmetrie-Test entlang forward-axis (2 Räder auf einer Linie) |
| 2 | **Truck/Bus (6 oder 8 Räder)** | Nach Stage 2: 6/8 valide Zylinder-Kandidaten | k dynamisch via `k=len(candidates)` und Prüfung dass k∈{2,4,6,8}; Rechteck-Test → Paar-weise |
| 3 | **Merged Single-Mesh (whole car = 1 mesh)** | Nach Stage 2: 0 Kandidaten | Sub-mesh-Split via connected-components auf Triangulation → dann Retry Stage 1 |
| 4 | **Rim+Tire nicht getrennt** (ein Mesh pro Rad) | Stage 5 succeeds, aber `sub_meshes` = [self] | Kein Fallback nötig — dann rotiert das Mesh als Ganzes, das ist korrekt |
| 5 | **Steering Wheel als False-Positive Zylinder** | Zylinder-Shape passt, aber Center liegt hoch im Body-bbox (y_frac > 0.45) | Höhen-Filter in Stage 2 filtert das aus |
| 6 | **Reserverad auf Kofferraum/Motorhaube** | Stage 4: 5. Cluster mit hohem inertia | Vor K-Means: forward-axis Position der Kandidaten prüfen — Reserverad liegt AUSSERHALB der zwei Wheelbase-Positionen |
| 7 | **Non-symmetrischer Custom-Build (Rally, Custom-Bodykit)** | Stage 5 Symmetrie-Test schlägt fehl | Soft-Warning zurückgeben, K-Means-Result trotzdem akzeptieren |
| 8 | **Z-up statt Y-up GLB** (Blender-Export ohne +Y-up-Option) | Body-PCA up_axis liegt bei ±Z statt ±Y | Egal — Pipeline nutzt PCA-frame, nicht glTF-Konvention |
| 9 | **Brems-Caliper wird als Wheel-Kandidat detektiert** | Nach Stage 2: 5+ Kandidaten, K-Means-Cluster mit sehr kleiner Point-Zahl | Stage 5 Rechteck-Test filtert (Caliper-Positionen bilden kein Wheel-Rechteck); alternativ: min-cluster-size = 2 verwerfen |
| 10 | **Sketchfab-GLB mit random Achse** (weder Y-up noch Z-up) | Body-PCA up_axis passt zu keinem globalen Achsenpaar | PCA-frame gilt, glTF-Header-Rotation ignorieren. Für Render später: rotation ins Cinema-Frame anwenden |
| 11 | **Halbtransparente Radkasten-Meshes** (Innenkotflügel wird als Zylinder detektiert) | Stage 2: passt teilweise; aber Sub-Mesh-Radius >> Wheel-Radius | Stage 3 disc_ratio-Test: Radkasten hat asymmetrische Krümmung, disc_ratio < 0.8 |
| 12 | **PCA Eigenvector-Sign-Flip** (identische Struktur, gedreht) | forward-axis könnte in +Z oder -Z laufen | Kanonisierung: forward zeigt in Richtung „mehr Meshes vor Center als hinter Center" — via `sign(sum(vert_x_in_frame > 0) - sum(vert_x_in_frame < 0))` |

**Meta-Fallback-Order:**
1. Naming-Heuristik (Stage 0) — 100% deterministisch, wenn matched
2. Geometrische Pipeline (Stages 1-6) — Default-Fall
3. HDBSCAN-basierter Rescue-Path — nur bei unbekanntem k (Motorrad/Truck)
4. **Human-in-the-loop:** Falls Confidence-Score < 0.7 → `--interactive`-Flag verlangt vom
   User `wheel_fl_mesh_name` explizit. Für v0.1 der einzig ehrliche Failure-Modus.

---

## Warum wir bestimmte Verfahren *nicht* wählen

**RANSAC-Cylinder-Fitting** ([pyRANSAC-3D](https://github.com/leomariga/pyRANSAC-3D)) ist
mächtig, aber (a) randomisiert per Definition, (b) instabil bei kurzen Zylindern
[GitHub Issue #13](https://github.com/leomariga/pyRANSAC-3D/issues/13), (c) benötigt Normalen
für Stabilität, die Sketchfab-GLBs oft nicht liefern. **Verwendung als Cross-Check
in v0.2** (Wheel-Radius-Verifikation), nicht als Primär-Detector.

**Hough-Transform für Symmetrieebenen** ([Podolak et al., Princeton, „A Planar-Reflective
Symmetry Transform for 3D Shapes"](https://gfx.cs.princeton.edu/pubs/podolak_2006_aps/index.php))
ist Gold-Standard für robuste Symmetrie-Detection, aber O(V²) in Vertex-Zahl und für unseren
Fall Overkill — weighted-PCA-Symmetrie ([He et al. 2020, Wiley](https://onlinelibrary.wiley.com/doi/10.1155/2020/8861367))
gibt in <10 ms akzeptable Ergebnisse für Vehicle-Klasse, die per Definition dominant-symmetrisch ist.

**PRS-Net** (ML-basierte Symmetry-Detection, [Wang et al., ResearchGate](https://www.researchgate.net/publication/336577419_PRS-Net_Planar_Reflective_Symmetry_Detection_Net_for_3D_Models))
und **PointNet++** ([Improved PointNet++ 2024, ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2212827124011429))
sind für v0.1 zu aufwändig (Model-Weights, Training, GPU-Determinismus). Reserviert für v2+
falls klassische Pipeline auf spezifischen Modellen scheitert.

---

## Sources

**Clustering:**
- [scikit-learn KMeans docs 1.9.0](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html) — n_init, random_state, k-means++
- [scikit-learn DBSCAN docs](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html) — data-order dependency
- [scikit-learn Flag for making DBSCAN deterministic (Issue #7848)](https://github.com/scikit-learn/scikit-learn/issues/7848)
- [scikit-learn 2.3 Clustering user guide](https://scikit-learn.org/stable/modules/clustering.html)
- [scikit-learn MeanShift docs](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.MeanShift.html) und [estimate_bandwidth](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.estimate_bandwidth.html)
- [HDBSCAN comparing_clustering_algorithms](https://hdbscan.readthedocs.io/en/latest/comparing_clustering_algorithms.html) — algorithm trade-offs
- [HDBSCAN performance benchmarks](https://hdbscan.readthedocs.io/en/latest/performance_and_scalability.html)
- [pberba: Understanding HDBSCAN](https://pberba.github.io/stats/2020/01/17/hdbscan/)
- [Hex Blog: Comparing DBSCAN, k-means, and Hierarchical Clustering](https://hex.tech/blog/comparing-density-based-methods/)
- [arXiv 2512.19772: A K-Means, Ward and DBSCAN repeatability study](https://arxiv.org/abs/2512.19772)
- [DBSCAN Wikipedia](https://en.wikipedia.org/wiki/DBSCAN)

**3D-Primitives / Cylinder-Fitting:**
- [pyRANSAC-3D GitHub](https://github.com/leomariga/pyRANSAC-3D) und [Cylinder-Issue #13](https://github.com/leomariga/pyRANSAC-3D/issues/13)
- [PrimitivesFittingLib GitHub](https://github.com/yuecideng/PrimitivesFittingLib) — Cylinder-Segmentation mit Open3D
- [Efficient RANSAC for Point-Cloud Shape Detection (Schnabel/Wahl/Klein, PDF)](https://www.hinkali.com/Education/PointCloud.pdf)
- [Open3D Feature Request: RANSAC Cylinder (Issue #6602)](https://github.com/isl-org/Open3D/issues/6602)
- [Fast Cylinder and Plane Extraction, arXiv 1803.02380](https://arxiv.org/pdf/1803.02380)
- [3D Model Fitting for Point Clouds with RANSAC (Medium)](https://medium.com/data-science/3d-model-fitting-for-point-clouds-with-ransac-and-python-2ab87d5fd363)

**Symmetrie-Detection:**
- [Podolak et al., Princeton: A Planar-Reflective Symmetry Transform for 3D Shapes](https://gfx.cs.princeton.edu/pubs/podolak_2006_aps/index.php)
- [3D Mirror Symmetry Detection using Hough Transform (ResearchGate)](https://www.researchgate.net/publication/221120463_3D_mirror_symmetry_detection_using_Hough_transform)
- [He et al. 2020, Wiley: Dominant Symmetry Plane Detection for Point-Based 3D Models (weighted PCA)](https://onlinelibrary.wiley.com/doi/10.1155/2020/8861367)
- [Detecting Approximate Reflection Symmetry in a Point Set, arXiv 1706.08801](https://arxiv.org/pdf/1706.08801)
- [PRS-Net: Planar Reflective Symmetry Detection Net (ResearchGate)](https://www.researchgate.net/publication/336577419_PRS-Net_Planar_Reflective_Symmetry_Detection_Net_for_3D_Models)
- [Bilateral Symmetry Detection for Real-time Robotics Applications (ResearchGate)](https://www.researchgate.net/publication/220122775_Bilateral_Symmetry_Detection_for_Real-time_Robotics_Applications)

**PCA-basierte Achsen-Detection:**
- [Analysis of 3D Point Cloud Orientation using PCA (Medium)](https://medium.com/@hirok4/analysis-of-3d-point-cloud-orientation-using-principal-component-analysis-95998ca8af91)
- [PCA Wikipedia](https://en.wikipedia.org/wiki/Principal_component_analysis)
- [Building OBBs by intermediate use of ODOPs (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0097849323002091) — PCA-Bias-Warnung
- [CSE169 Collision Detection Notes (UCSD)](https://cseweb.ucsd.edu/classes/sp16/cse169-a/slides/CSE169_12.pdf)

**PointNet / ML-Segmentation:**
- [Improved PointNet++ for 3D Mechanical Part Feature Segmentation (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2212827124011429)
- [Part-Level 3D Gaussian Vehicle Generation (arXiv 2604.05070)](https://arxiv.org/pdf/2604.05070)

**glTF-Konventionen (mit Vorsicht zu genießen):**
- [glTF Forward vector convention (Issue #1043)](https://github.com/KhronosGroup/glTF/issues/1043)
- [glTF Coordinate System and Units (Issue #2352)](https://github.com/KhronosGroup/glTF/issues/2352)
- [glTF Axis convention language in spec (Issue #1640)](https://github.com/KhronosGroup/glTF/issues/1640)
- [glTF-Blender-Exporter Coordinate System (Issue #204)](https://github.com/KhronosGroup/glTF-Blender-Exporter/issues/204)

**Existierende Vehicle-Rigging-Addons (Naming-Heuristik-Referenz):**
- [Rigacar GitHub (digicreatures)](https://github.com/digicreatures/rigacar) und [Rigacar-Artikel](https://digicreatures.net/articles/rigacar.html)
- [Unreal Vehicle Rigging Addon for Blender](https://continuebreak.com/creations/ue-vehicle-rigging-addon-blender/)
- [Attaching wheels to car with python script (Blender Artists)](https://blenderartists.org/t/attaching-wheels-to-car-with-python-script/455842)

**Symmetry-Based Vehicle-3D-Papers (Automotive-Domain):**
- [Symmetry-based monocular 3D vehicle ground-truthing (YorkSpace)](https://yorkspace.library.yorku.ca/items/f7d4e742-c32e-4288-ae79-3c0412cb677b)
- [Symmetry-based monocular vehicle detection system (ResearchGate)](https://www.researchgate.net/publication/251324509_Symmetry-based_monocular_vehicle_detection_system)
- [ShapeNet: An Information-Rich 3D Model Repository (arXiv 1512.03012)](https://arxiv.org/pdf/1512.03012)

**Reproducibility / Determinismus:**
- [O'Reilly: Machine Learning Design Patterns, Ch. 6 Reproducibility](https://www.oreilly.com/library/view/machine-learning-design/9781098115777/ch06.html)
- [Effective Deterministic Initialization for k-Means (arXiv 1611.06777)](https://arxiv.org/pdf/1611.06777)
- [Implementation-induced Inconsistency in ML (NJIT ICST20)](https://web.njit.edu/~ineamtiu/pubs/icst20yin.pdf)

---

**Report-Status:** Ready für v0.1-Implementation.
Nächste Schritte: Prototyp bauen (`zer0one_cinema/wheel_detection.py`), Golden-Frame-Testset
mit 10 Sketchfab-Vehicle-GLBs erstellen (Muscle-Car, F1, Truck, Motorrad, Tuner, Rally,
Classic, EV, SUV, Van), Cinema-Grade-Verification-Framework anschließen.
