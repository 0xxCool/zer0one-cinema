# Open-Source Ecosystem Research — zer0one-cinema

**Sprint 19 · Research-Snapshot 2026-07-15**
**Scope:** Landschafts-Analyse für den Launch eines MIT-lizenzierten Cinema-Grade-Rendering-Orchestrators (Blender-Wrapper + Preset-Library + QA-Verifikation). Ziel: Zero-Cost-Abhängigkeiten, ausschließlich CC0/CC-BY-Assets, keine Adobe/Substance/KeyShot-Kette.

---

## Executive Summary

1. **Es gibt keinen direkten Konkurrenten** zu einem Python-Wrapper, der Blender headless mit Preset-Presets + automatisiertem QA-Gate orchestriert — die adjazenten Projekte (Kubric, BlenderKit, glTF-Sample-Viewer) sind Inspiration oder Interop-Partner, keine Substitute.
2. **Asset-Fundament ist komplett CC0-machbar:** PolyHaven (CC0, 2000+ Assets, HDRIs standardmäßig 16k) [1][2] und ambientCG (CC0, 2800+ PBR-Materialien) [3][4] decken alle nicht-Vehicle-Anforderungen; Vehicle-GLBs kommen aus Sketchfab-CC0-Tag + Kenney + Khronos-Sample-Assets.
3. **Blender-eigene Chain reicht für Post-Processing:** AgX ist seit Blender 4.0 der Default (16.5 EV) [5][6], der Compositor liefert Grain/Vignette/Glare ohne externe Software, FFmpeg macht Encoding — DaVinci Resolve entfällt (Scripting nur in der kostenpflichtigen Studio-Version) [7].
4. **Distribution zweigleisig:** PyPI + ghcr.io als Phase 1 (sofort), `extensions.blender.org` als Phase 2 (Wheel-Bundling nötig, kein Runtime-PIP erlaubt) [8][9], Homebrew/conda-forge als Phase 3.
5. **Launch-Prioritäten:** Blender-Artists + r/blender als P1 (direkte Zielgruppe), Show-HN als P1-Multiplikator, YouTube-Reviews (Blender Guru, CG Cookie, CG Boost) als P2-Verstärker.

---

## 1 · Bestehende Open-Source-Tools (Landschaft)

| Tool | Zweck | Lizenz | Aktivität | Relation zu zer0one-cinema |
|---|---|---|---|---|
| **Kubric** (Google Research) | Synthetic-Scene-Generator, PyBullet + Blender headless für ML-Datasets | Apache-2.0 [10] | Aktiv (Commits 2026 im Repo), pinned auf Blender 2.93 | **Inspiration** — Python-orchestriert Blender headless, ähnlicher Docker-Ansatz. Nicht als Dependency (ML-Fokus, veraltete Blender-Version). |
| **Verge3D** (Soft8Soft) | WebGL-Exporter aus Blender/Max/Maya, Puzzle-Editor | Add-on GPL, aber Toolkit **kommerziell** (Freelance/Enterprise-Lizenz) [11] | Aktiv | **Orthogonal** — Web-Delivery, wir Cinema-Offline. Nicht Dep, nicht Konkurrenz. |
| **Sverchok** | Parametric-Node-Modeling in Blender | GPL-3 [12] | Aktiv (unterstützt Blender 5.1, 4.5, 3.6, 2.8) | **Inspiration** — Node-Editor-UX-Vorbild für unseren Preset-Editor. |
| **Animation Nodes** (Jacques Lucke) | Motion-Graphics-Nodes | GPL-3 | **Maintenance-Modus** — v2.3 als LTS-Release für Blender 4.2 LTS [13], neue Entwicklung fließt in Geometry Nodes (auch Lucke). Nicht deprecated, aber effektiv nachfolgereif. | **Inspiration** — Warnbeispiel: viele der Features sind in Blender-Core migriert. Wir sollten in-tree bleiben, wo möglich. |
| **BlenderKit** | Asset-Discovery-Panel IN Blender, 48000+ Assets (CG Channel 09/2025) [14] | Assets: RF + CC0-Filter [15]; Add-on: GPL-3 | Aktiv | **Konkurrenz (Asset-Discovery) + Interop-Kandidat** — deren Public-API könnte unser Import-Panel füttern. |
| **Filament** (Google) | Real-time PBR-Renderer (C++, Vulkan/Metal/GL) | Apache-2.0 | Aktiv | **Orthogonal** — Real-time, wir Offline-Cycles/OptiX. |
| **glTF Sample Viewer / Renderer** (Khronos) | Referenz-Impl PBR/glTF 2.0 (WebGL) [16][17] | Apache-2.0 | Aktiv | **Referenz** — Test-Corpus für Material-Compliance-Checks (unser QA-Gate kann Renders gegen Sample-Viewer visuell diffen). |

---

## 2 · Empfehlung: Dependencies vs. Inspiration

### Als harte Dependency übernehmen
| Package | Rolle | Grund |
|---|---|---|
| **FFmpeg** | Delivery-Encoder (H.264, AV1, ProRes) | Universell, permissive Lizenz (LGPL/GPL je Build), wir nutzen es bereits in `video-post-pipeline`. |
| **OpenColorIO 2.5** (in Blender gebundelt) | Farbmanagement, AgX-Config | Kein externes Install nötig — kommt mit Blender, ist seit 4.0 Default [5][6]. |
| **Blender Compositor** (in-tree) | Grain, Vignette, Glare-Streaks, CA | Kein externes Comp-Tool nötig; Nuke/AE-Pipeline vermeiden. |
| **PolyHaven Asset-Browser API** (optional) | Live-HDRI/Material-Download | Offiziell CC0-legal, existiert als Blender-Add-on (Superhive). |

### Als Inspiration nutzen (NICHT als Dependency)
- **Kubric** — Docker/headless-Blender-Orchestrierung als Referenz-Architektur. Zu ML-lastig und blender-2.93-pinned für Reuse.
- **Sverchok** — Node-Editor-UI-Patterns für unseren Preset-Composer.
- **glTF Sample Viewer** — Test-Corpus + Golden-Frame-Set für Material-Regression-Tests.
- **BlenderKit** — API-Layout, Payment-Model (Free-Tier + Sub) als kommerzielles Vorbild ohne Code-Kopie.

### Explizit vermeiden
- **DaVinci Resolve Scripting-API** — nur in Resolve **Studio** (kostenpflichtig) verfügbar; Free-Version hat keinen externen Scripting-Support [7]. Bricht unsere Zero-Cost-Regel.
- **Verge3D** — kommerzielle Freelance/Enterprise-Lizenz [11].
- **Adobe Substance / KeyShot** — Abo-Zwang, per Anforderung ausgeschlossen.

---

## 3 · CC0-Asset-Bezugsquellen für die Test-Suite

### Test-Suite-Setup: ~15 Vehicle-GLBs + 8 HDRIs

**Vehicle-GLBs (Ziel: 15 Stück, alle CC0 oder CC-BY mit klaren Attributions-Files)**

| Quelle | Typ | Lizenz | Notiz |
|---|---|---|---|
| **Sketchfab** — Tag `cc0` + Kategorie `cars-vehicles` [18][19] | Concept Cars, Vehicle-Kits | CC0 | Beispiele: "FREE Concept Car 003/006/025" von @unityfan777 [20], "Vehicle Topology Kit" von @britdawgmasterfunk [21]. **Query:** `https://sketchfab.com/search?q=car&license=cc0&type=models&downloadable=true` |
| **Sketchfab** — Tag `cc-by` + Automotive | Real-brand-Look-Alikes | CC-BY (Attribution nötig!) | Attribution-File `ATTRIBUTIONS.md` in Repo pflegen. **Achtung:** kein Markenname/Logo im Preset-Namen (Ford-TurboSquid-Case) [22]. |
| **BlenderKit** — Filter `Free + CC0` [15] | Modern Cars | CC0/RF-Mix | Manuell prüfen — BlenderKit's Position ist, dass Non-Original-Uploads gelöscht werden. |
| **Kenney.nl** — Car-Kit | Low-Poly-Vehicles | CC0 | Für Placeholder/Smoke-Tests, nicht Cinema-Grade. |
| **KhronosGroup/glTF-Sample-Assets** (GitHub) | 2 Referenz-Vehicles (`ToyCar`, `MotorcycleHelmet`) | Apache-2.0 / CC-BY | **Pflicht** — offizielle Renderer-Test-Assets. Perfekt für Regression-Suite. |
| **PolyHaven Models** [2] | 3–5 Vehicles (begrenzt) | CC0 | PolyHaven ist stärker bei HDRIs/Materials als bei Vehicles. |

**Empfohlener konkreter Mix (Sprint-19-Test-Suite):**
- 2× Khronos-Sample-Vehicles (Regression-Basis)
- 4× Unity-Fan-Concept-Cars (Sketchfab CC0)
- 1× Vehicle-Topology-Kit (Sketchfab CC0)
- 3× BlenderKit-CC0-Cars (händisch kuratiert)
- 3× PolyHaven-Vehicles (was verfügbar ist, CC0)
- 2× Kenney-Low-Poly (Placeholder + Perf-Baseline)

**HDRIs (Ziel: 8 Stück, alle PolyHaven CC0, mind. 8k)**

Alle PolyHaven, Lizenz CC0 [1], keine Attribution nötig. Für Cinema-Grade zählt Dynamic-Range ≥12 EV (Innen) bzw. ≥16–22 EV (Aussen mit Sonne) und Auflösung ≥4k für scharfe Auto-Reflexionen [23][24]:

| Slot | Beispiel-HDRI (PolyHaven-Slug) | Warum |
|---|---|---|
| Studio | `studio_small_08` (16k) | Neutraler Product-Shot |
| Studio-Dark | `photo_studio_01` (16k) | Für Dark-Car-Reveal |
| Night-Urban | `moonless_golf` / `night_bridge_01` | Neon-Reflection-Test |
| Golden-Hour | `venice_sunset` / `aristea_wreck` (16k+) | Warm-Rim-Light |
| Overcast | `kloppenheim_02` (16k) | Diffuse-Base, härtester Roughness-Test |
| Underground | `parking_garage_01` (16k) | Enge Reflexionen, Punktlicht |
| Desert-Day | `qwantani` (16k) | High-Dynamic-Range, harte Schatten |
| Blue-Hour | `dresden_station_night` | Cool-warm-Kontrast |

Alle bereits im Sprint-14-Repo unter `/assets/hdri/*` — nur Ergänzungen nötig.

**Was NICHT nehmen:**
- HDRI-Skies / HDRI-Hub — kommerziell, keine CC0.
- TurboSquid Free / CGTrader Free — Editorial-only für Marken-Vehicles, Attribution unklar [22].
- Free3D — Community-Uploads mit inkonsistenter Lizenzangabe, hohes Copyright-Risiko.

---

## 4 · Post-Processing & Grading (In-tree-Lösung)

| Bedarf | Free-Tool | Verwendung |
|---|---|---|
| Farbmanagement / Tone-Mapping | **OpenColorIO 2.5 + AgX** (Blender-Default seit 4.0) [5][6] | 16.5 EV Dynamic-Range, ersetzt Filmic (Notorious-Six-Problem). Kein Extra-Install. |
| Grain / Vignette / Glare / CA | **Blender Compositor** (in-tree) | Node-Setup exportierbar als `.blend`-Preset in Repo. |
| Encoding (H.264, AV1, ProRes) | **FFmpeg** (LGPL) | Bereits in `video-post-pipeline` verankert. |
| Grading (Curves/LUTs) | Blender Compositor **Color Balance/Curves-Nodes** oder LUT via OCIO | DaVinci Resolve **entfällt** (Studio-lizenz-only für Scripting [7]). |

---

## 5 · Distribution-Strategie (Phasen)

### Phase 1 — Launch-Woche (Tag 0)
| Kanal | Was | Warum |
|---|---|---|
| **PyPI** | `pip install zer0one-cinema` | Standard-Python-Nutzer erwarten das. Setuptools/Poetry-Build, `zer0one_cinema` als Package-Name. |
| **GitHub Releases** | Tarball + `.zip` + Docker-`digest.txt` | Für Nutzer die kein PyPI/Docker nutzen. |
| **ghcr.io** | `ghcr.io/0xxcool/zer0one-cinema:vX.Y.Z` | Wir haben schon `ghcr.io/0xxCool/blender-worker` — konsistente Registry. |

### Phase 2 — Woche 2–4
| Kanal | Was | Constraint |
|---|---|---|
| **extensions.blender.org** | Blender-Add-on-Bundle | **Regel:** kein Runtime-`pip install` erlaubt; alle Deps als **gebundelte Wheels** [8][9]. `bpy.app.online_access==False` respektieren (keine Netz-Calls, wenn Nutzer offline). Approval-Queue-Prozess mit Community-Test-Phase [8]. |

### Phase 3 — Monat 2–3
| Kanal | Was | Warum |
|---|---|---|
| **Homebrew Tap** (`brew tap 0xxcool/tap && brew install zer0one-cinema`) | CLI-Formula | macOS/Linux-Power-User-Convenience. |
| **conda-forge** (Feedstock) | conda-Package | Wichtig für ML-/DataViz-Publikum (die stark auf conda-forge stehen [25]). Der Feedstock-Prozess dauert Wochen (Community-Review), daher Phase 3. |

**Nicht empfohlen:**
- Snap/Flatpak — Blender selbst hat Sonderbeziehung zu diesen, wir würden 3 Wege pflegen ohne User-Nachfrage.
- Windows-MSI — später, wenn Windows-Adoption > 25 % ist.

---

## 6 · Marketing / Launch-Plan-Grundgerüst

### Priorität 1 (Launch-Tag, koordiniert innerhalb 24 h)
| Kanal | Format | Notiz |
|---|---|---|
| **Blender-Artists.org** (Add-ons-Thread) [26] | Add-on-Ankündigung + Demo-GIF + Link zum Repo | Direkte Zielgruppe, aktive Community. |
| **r/blender** | Post: "I made a Blender-Wrapper for Cinema-Grade Car Renders — open source" + 15 s Demo-Clip | Weitester Trichter für Blender-User. |
| **Show HN** | Titel-Template: `Show HN: zer0one-cinema – MIT-licensed Cinema-Grade Blender Orchestrator` (siehe erfolgreiche Vorlagen VSC, StratusGFX, Chili3d, Thermion [27–30]) | Techniker-Reichweite; guter Show-HN-Post = kurzer Titel, klare Value-Prop, GitHub-Link im ersten Kommentar, Author antwortet 6 h aktiv. |
| **HN Comment-Standby** | Autor beantwortet Fragen 6 h live | Kritischer Erfolgsfaktor bei Show-HN. |

### Priorität 2 (Woche 2)
| Kanal | Aktion |
|---|---|
| **r/vfx**, **r/compositing** [31] | Tiefere Technik-Posts (AgX-Vergleich, QA-Gate-Metrics), nicht nur Marketing. |
| **YouTube-Outreach** | Review-Pakete an **Andrew Price (Blender Guru)**, **CG Cookie** [32], **CG Boost** [33] senden — mit Test-Repo, Beispiel-Renders, 1-Klick-Reproducer. Fokus auf Blender Guru (breiteste Reichweite unter Blender-Anfängern und Casual-Users). |
| **Blender Developers Blog** | Passiv — ergibt sich aus extensions.blender.org-Publikation. |

### Priorität 3 (Monat 2+)
| Kanal | Aktion |
|---|---|
| **Blender Studio Newsletter** | Kontakt via Blender Studio Team, wenn ≥3 Referenzprojekte im Repo. |
| **CG Channel News** | Submission (BlenderKit hat dort 09/2025 Coverage bekommen [14] — Blueprint für uns). |
| **Blender Conference Talk** (Herbst) | CFP früh einreichen. |
| **Blender-Stack-Exchange** | Präsenz aufbauen — bei Fragen zu unserem Tool antworten. |

### Anti-Muster (nicht tun)
- Twitter/X-Ads oder Reddit-Ads — Community reagiert allergisch bei OSS-Launches.
- Newsletter-Blast an ungefragte Adressen (Cold-Outreach ist B2B, nicht Community).
- Multi-Subreddit-Cross-Post am gleichen Tag — als Spam gewertet.

---

## 7 · Referenzen

1. Poly Haven — License Page. https://polyhaven.com/license — CC0, keine Attribution nötig.
2. Poly Haven — Home / All Assets. https://polyhaven.com/all — 2000+ Assets, HDRIs 16k Standard.
3. ambientCG — Home. https://ambientcg.com/ — CC0, keine Restriktionen.
4. cgtricks — "Free PBR Materials & Textures | AmbientCG". https://cgtricks.com/free-pbr-materials-textures-ambientcg/ — 2800+ Assets seit 2017.
5. Blender Developer Docs — "Color Management - Filmic AgX (4.0 Release Notes)". https://developer.blender.org/docs/release_notes/4.0/color_management/
6. Blender — Merge-PR #106355 "Replace Default OCIO config with AgX". https://projects.blender.org/blender/blender/pulls/106355
7. Wild Lion Media — "DaVinci Resolve Python Scripting: The Complete Guide". https://wildlion.media/davinci-resolve-python-scripting-the-complete-guide-to-the-api/ — Free-Version hat keinen externen Scripting-Support; Studio nötig.
8. Blender Developer Docs — "Extensions Moderation Guidelines". https://developer.blender.org/docs/features/extensions/moderation/guidelines/
9. Blender Developer Docs — "Add-on Guidelines" (Wheel-Bundling, `bpy.app.online_access`). https://developer.blender.org/docs/handbook/extensions/addon_guidelines/
10. Kubric — LICENSE (Apache-2.0). https://github.com/google-research/kubric/blob/main/LICENSE
11. Soft8Soft — "Verge3D Licensing". https://www.soft8soft.com/licensing/
12. Sverchok — GitHub. https://github.com/nortikin/sverchok
13. Animation Nodes — Releases. https://github.com/JacquesLucke/animation_nodes/releases — v2.3 als LTS für Blender 4.2 LTS.
14. CG Channel — "Get 48,000 free 3D models, HDRIs and materials from BlenderKit" (09/2025). https://www.cgchannel.com/2025/09/get-over-48000-free-3d-models-materials-and-hdris-from-blenderkit/
15. BlenderKit — "Our position on CC0 models". https://www.blenderkit.com/articles/our-position-on-cc0-models/
16. Khronos — glTF Sample Viewer. https://github.com/KhronosGroup/glTF-Sample-Viewer
17. Khronos — glTF Sample Renderer. https://github.com/KhronosGroup/glTF-Sample-Renderer
18. Sketchfab — Cars & Vehicles Kategorie. https://sketchfab.com/categories/cars-vehicles
19. Sketchfab — CC0-Tag. https://sketchfab.com/tags/cc0
20. Sketchfab — "FREE Concept Car 025 (CC0)" von @unityfan777. https://sketchfab.com/3d-models/free-concept-car-025-public-domain-cc0-e3a65443d3e44c33b594cec591c01c05
21. Sketchfab — "Vehicle Topology Kit CC0". https://sketchfab.com/3d-models/vehicle-topology-kit-cc0-c13e54a5c560400cb343f2284e9961e4
22. CGTrader Forum — "Ford and TurboSquid Exclusive License" (Editorial-only für Marken-Vehicles). https://www.cgtrader.com/forum/topics/ford-and-turbosquid-exclusive-license
23. Poly Haven Blog — "How to Create High Quality HDR Environments". https://blog.polyhaven.com/how-to-create-high-quality-hdri/ — 22 EV für Aussen mit Sonne.
24. Adaptive Samples — "What Makes a Good HDRI and How to Use It Correctly". https://blog.gregzaal.com/2016/02/23/what-makes-good-hdri/ — Auflösung ≥4000×2000 für Auto-Reflexionen.
25. conda-forge — Introduction. https://conda-forge.org/docs/user/introduction/ — 25000+ Feedstocks, community-driven.
26. Blender Artists — Community-Forum. https://blenderartists.org/
27. Show HN — "VSC – Open Source 3D Rendering Engine in C++" (03/2025). https://news.ycombinator.com/item?id=43339584
28. Show HN — "StratusGFX real-time 3D rendering engine" (03/2024). https://news.ycombinator.com/item?id=35370284
29. Show HN — "Chili3d – browser-based 3D CAD" (06/2025). https://news.ycombinator.com/item?id=44238171
30. Show HN — "Thermion, open source 3D rendering toolkit". https://news.ycombinator.com/item?id=40818835
31. PainOnSocial — "15 Best Subreddits for VFX Artists 2026". https://painonsocial.com/subreddits/vfx-artists
32. CG Cookie — YouTube-Kanal. https://www.youtube.com/blendercookie
33. CG Boost — Home. https://www.cgboost.com/

---

*Erstellt Sprint 19 (2026-07-15). Nächster Review: nach Launch (Nachbetrachtung welche Kanäle Traffic gebracht haben).*
