# Cinema-Look Analysis — Referenz-Trailer, Universal-Rules, Look-Presets

> **Zweck:** Grundlage für Sprint 19 (`zer0one-cinema v0.3`) — welche Look-Presets liefern wir, welche Anti-Patterns muss unser Verification-Layer erkennen, welche Grading-Konventionen sind messbar?
> **Vorwissen (nicht wiederholt):** Die 15 Cinema-Detail-Standards + 6 Verification-Gates aus `.claude/skills/cinema-grade-verification/`. Dieses Dokument ergänzt sie mit Trailer-Analyse-Evidenz und daraus abgeleiteten Preset-Rezepten.
> **Datum:** 2026-07-15

---

## Executive Summary

Cinema-Grade Automotive-Trailer trennen sich von Amateur-Renders durch **drei messbare Faktoren**, die sich in jedem der analysierten Referenz-Werke wiederholen:

1. **Motivierte, quellenbasierte Beleuchtung statt Ambient-Wash.** Papamichael (Ford v Ferrari) verweigert das artifizielle „lift" in Nachtszenen und lässt Scheinwerfer + Streckenbeleuchtung + Rim das Bild alleine tragen — hoher Kontrast, echte Silhouetten, keine flache Fill-Anhebung. Amateur-Renders scheitern hier durch AO-Overkill und einen einzigen Sun-Emitter.
2. **Hard-mounted, low-height Kamera-Geometrie.** Sowohl Papamichael als auch Jouffret (Gran Turismo) montieren Kameras zentimeternah an der Karosserie bzw. wenige Zoll über dem Asphalt — der Betrachter wird zum Rad, nicht zum Zuschauer. Kombiniert mit anamorphotischen Brennweiten (Panavision C/T Series bei FvF, Venice-2 + Rialto bei GT) ergibt sich der „gepresste" Kino-FoV.
3. **Nasser Asphalt + reflektierendes Environment als Story-Ebene.** NFS Heat/Unbound machen die Straße selbst zur zweiten Lichtquelle — Neon-Reflektionen unter dem Auto tragen 40–60 % der visuellen Faszination. Ohne Wet-Ground + High-Detail-HDRI wirkt jedes Auto wie ein Turntable-Product-Shot.

**Direkte Konsequenz für v0.3:** Wir liefern **5 kuratierte Presets** (`studio_hero`, `night_neon_wet`, `golden_hour_hero`, `documentary_race`, `bmw_films_hire`) statt eines generischen „cinematic"-Buttons; jeder Preset hat feste Kamera-Geometrie, HDRI-Klasse, Grading-LUT, VFX-Chain und Waveform/Vectorscope-Targets, die im Post-Gate messbar sind.

---

## 1. Referenz-Trailer-Analysen

### 1.1 Ford v Ferrari (2019, DP Phedon Papamichael ASC)

**Kamera & Optik:** ARRI ALEXA LF + **Panavision C-Series Anamorphic + T-Series Anamorphic + H-Series Spherical**. Die C-Series-Anamorphs geben oval-Bokeh und den namensgebenden 60er-Jahre-Look, H-Series wird für Close-Ups auf Bale genutzt, damit die Perspektive nicht auf lange Teles komprimiert. Kameras werden **hard-mounted** an die Picture-Cars — keine langen Lenses, die den Blick vom Fahrer entkoppeln.

**Lighting:** Motivated-Lighting-Doktrin. Tag-Racing = harte, ungefilterte Sonne (Le-Mans-Erschöpfung wird sensorisch, nicht narrativ vermittelt). Nacht-Racing = Headlights + Streckenlichter + strategisches Rim, keine artifizielle Fill-Anhebung. Kontrast bleibt bewusst hoch, Schatten bleiben schwarz.

**Grading:** Warme Highlights (leicht Gold-versetzt), neutrale Midtones, saturierte Roll-Off. Kein aggressives Teal-Orange — mehr „vintage Kodachrome". 35mm-Filmkorn wurde in Post ergänzt.

**Für uns:** Preset `documentary_race` — hard-mount POV, hoher Kontrast, warme Highlights, gedämpftes Teal in den Schatten (nicht Blockbuster-Teal).

**Sources:** [Color Culture Analysis](https://colorculture.org/ford-v-ferrari-cinematography-analysis/) · [Film Independent DP Interview](https://www.filmindependent.org/blog/dp-phedon-papamichael-on-the-vintage-look-and-analog-action-of-ford-v-ferrari/) · [No Film School Interview](https://nofilmschool.com/ford-ferrari-phedon-papamichael-interview) · [ShotOnWhat Tech Specs](https://shotonwhat.com/ford-v-ferrari-2019)

---

### 1.2 Need for Speed Heat + Unbound (EA Ghost Trailers, 2019 / 2022)

**Look-Kern:** Miami-Neon nach Sonnenuntergang. Palette dominiert von **Magenta ↔ Cyan** — genau der Split-Complementary, den unsere Verification als „NFS-Look" erkennen muss. Wet-Asphalt ist kein Zusatz, sondern **Bühne**: Neon-Schilder reflektieren als vertikale Streaks unter dem Auto. Unbound legt zusätzlich einen **cartoon-artistischen Speed-Line-Overlay** über die photorealistischen Cars — das ist ein Stilbruch, den wir explizit **NICHT** kopieren (unsere Zielgruppe ist Automotive-B2B, nicht Arcade-Games).

**Kamera:** Frei bewegte Chase-Cams, oft zentriert-hinter-dem-Auto (dritte-Person-Perspektive-inspiriert), tiefe Brennweiten (24–35 mm sphärisch), leichte Handheld-Vibration.

**Post-Chain:** Bloom auf jeder Emissive-Fläche (Threshold niedrig — sub-1.0), starker chromatischer Split in Highlights, schwerer Vignette (Corner-Falloff bis –0.4 EV), Schwarz-Punkt bewusst angehoben (Crushed Blacks aber mit blauem Cast).

**Für uns:** Preset `night_neon_wet` — Wet-Ground obligatorisch, Emissive-Density ≥ 100 im HDRI, Cyan-Shadows / Magenta-Highlights, Bloom Threshold 0.8.

**Sources:** [HotCars — NFS Unbound Trailer Analysis](https://www.hotcars.com/new-need-for-speed-unbound-trailer-sets-tone-for-franchise/) · [GamesRadar — Palm City Neon-Aesthetic](https://www.gamesradar.com/need-for-speed-heats-palm-city-is-a-neon-lit-beauty-in-new-launch-trailer/) · [Filmmakers Academy — NFS Camera & Rigging](https://www.filmmakersacademy.com/camera-need-for-speed/) · [Nexus Mods — NFS Heat ReShade Preset](https://www.nexusmods.com/needforspeedheat/mods/478)

---

### 1.3 Gran Turismo (2023, Dir. Blomkamp / DP Jacques Jouffret ASC)

**Kamera:** Sony **Venice 2 mit Rialto-Extension** — der Sensor kann per Kabel vom Body getrennt in **wenige Zoll über dem Asphalt** oder in Radkasten-Nähe montiert werden. Bis zu 20 Kameras gleichzeitig auf der Strecke. **Kein IBIS, keine Full-Stabilization** — Blomkamp will „raw footage feel", keine Werbespot-Glätte.

**Look-Doktrin:** „Absolute reality" — Jouffret vermeidet Filter, Diffusion und übertriebenes Grading. Real-shot at Circuit de la Sarthe, Nürburgring, Suzuka. Der Trailer wirkt trotz seiner Herkunft *nicht* wie ein Sony-Werbespot, sondern wie Motorsport-Doku.

**Grading:** Sehr subtil — kaum sichtbares Teal, natürliche Skintones, cleane Highlights ohne Roll-Off-Push. Motion-Blur klassisch 180°-Shutter.

**Für uns:** Preset `documentary_race` (siehe 1.1) ist eine Fusion aus FvF-Grading + GT-Kamera-Geometrie. Wichtig für unser Kamera-Rig-System: **Low-Mount-Preset mit 12–18 cm Bodenabstand** ist Pflicht-Feature.

**Sources:** [Hollywood Reporter — Jouffret NAB 2023 Talk](https://www.hollywoodreporter.com/movies/movie-news/gran-turismo-racing-scenes-cinematographer-nab-2023-1235376240/) · [ASC — In the Driver's Seat](https://theasc.com/article/in-drivers-seat-for-gran-turismo/) · [Sony Cine — Venice 2 + Rialto Feature](https://sony-cinematography.com/articles/shot-on-venice-jacques-jouffret-asc-brings-racing-realism-to-gran-turismo-using-venice-2-and-the-rialto-extension-system/) · [Leitz Cine — Gran Turismo 2023](https://www.leitz-cine.com/production/gran-turismo-2023)

---

### 1.4 BMW Films „The Hire" (2001/2002, div. Directors) + Mercedes „Lucky Star" (Michael Mann, 2002)

**Der Referenz-Meilenstein für Auto-Cinema.** 8 Kurzfilme (~10 min), Regie u. a. **Ang Lee, John Woo, Guy Ritchie, Tony Scott, Wong Kar-wai, Alejandro González Iñárritu**. Clive Owen als „The Driver". Keine klassische Werbung — narrativer Kurzfilm mit BMW als Charakter. Charakteristisch: **Golden Hour + Low-Angle-Hero-Shots + Fluid Chase-Coverage**, aber unterschiedliche Handschriften pro Director (Wong Kar-wai's „The Follow" ist z. B. jump-cut-lastig und crushed-color, während Tony Scott's „Beat the Devil" hoch-kontrast-orange gradet).

**Learning für v0.3:** Ein „BMW Films"-Preset ist eher ein **Frame-Rhythmus** als ein Grading — narrativer Aufbau, Reveal-Choreographie (Detail → Wide → Push-In), unterschätzte Nutzung von Stille + Motorgeräusch (keine ständige Trailer-Musik). Wir sollten das als **Cut-Template**, nicht nur als Farbraum modellieren.

**Sources:** [Wikipedia — The Hire](https://en.wikipedia.org/wiki/The_Hire) · [Open Culture — 8 Films Directors List](https://www.openculture.com/2014/07/watch-the-bmw-film-series-the-hire.html) · [Motor1 — 4K Remaster](https://www.motor1.com/news/420770/bmw-the-hire-films-remastered/) · [Film Stories — BMW Cinematic Universe](https://filmstories.co.uk/features/david-fincher-tony-scott-john-woo-and-more-the-bmw-mini-cinematic-universe/)

---

### 1.5 Blender Studio — Sprite Fright / Charge / Wing It

**Wichtig als Gegenposition:** Blender Studio produziert **stilisierte, nicht photorealistische** Cinema. Aber die Pipeline-Learnings gelten für uns 1:1:

- **HDRI wird für Reflection genutzt, aber im Background durch Solid Color ersetzt** (via Ray-Visibility) → das verhindert, dass ein Studio-HDRI wie ein „echter Ort" wirkt. Für unsere Studio-Presets identisches Muster übernehmen.
- **Face-Lighting-Regel:** nie exakt von Kamera-Achse — überträgt sich direkt auf Car-Paint: Reflexion niemals frontal, sondern immer 15–30° off-axis, sonst wirkt der Lack tot.
- **shotbuilder-Addon** linkt Sets/Characters/Props/Lighting in Layer-Collections — Blueprint für unsere Preset-Injektion (ein Preset ist eine Collection, keine Blob-Datei).
- **Charge** wurde komplett in **EEVEE** produziert — belegt, dass Cinematic-Look nicht Cycles-exklusiv ist. Für unsere Preview-Renders sollten wir EEVEE-Fallback vorsehen (10–20× schneller).

**Für uns:** Kein direktes Grading-Preset ableiten, aber **Pipeline-Konventionen** (Collection-basierte Preset-Injektion, HDRI-Reflection-only-Trick, EEVEE-Preview) übernehmen.

**Sources:** [Sprite Fright Master Class — Lighting & Rendering](https://studio.blender.org/blog/Sprite-Fright-Master-Class-Lighting-Rendering/) · [Sprite Fright Workflow — Lighting & Set Dressing](https://studio.blender.org/blog/sprite-fright-workflow-lighting-set-dressing/) · [Charge Premiere](https://studio.blender.org/blog/charge-premiere/)

---

## 2. Universal Automotive Cinematography Rules

Aus der Kreuzanalyse aller 5 Referenzen destilliert. Diese Rules gelten preset-übergreifend und werden im Verification-Gate hart geprüft.

| # | Rule | Konkrete Zahl / Test | Quelle |
|---|------|----------------------|--------|
| U1 | **Hero-Shot = Front-¾** | Yaw −30 bis −45° zur Kamera, Front-Wheels 15–20° zur Kamera gedreht, Kamera-Höhe **Fender-Height (0.7–0.9 m)** — nicht Augenhöhe. | [Blendnow — Car Photography Angles](https://www.blendnow.com/blog/car-photography-angles) · [Spyne — Top 10 Angles](https://www.spyne.ai/blogs/car-photography-angles) |
| U2 | **Low-Angle für Power** | Camera unter Auto-Center-of-Mass — Höhe 20–40 cm über Boden. Wirkt automatisch dominant/heroisch. | [ISO1200 — Hero Shot Low Angles](https://www.iso1200.com/2026/01/the-hero-shot-how-low-angles-transform.html) · [LensViewing — Cinematic Car Camera Angles](https://lensviewing.com/camera-angles-cars-driving-cinematic/) |
| U3 | **Wheel-Focus-Reveal** | Macro-DoF auf Rad (f/2.0–f/2.8, Focus-Distance 0.5–1 m), dann Focus-Pull nach hinten aufs Auto. Klassische Reveal-Choreo. | [Furoore — Automotive Photography Guide](https://furoore.com/automotive-photography/) · [Soundstripe — Filmmaker Tips Car Commercial](https://www.soundstripe.com/blogs/how-to-shoot-a-car-commercial) |
| U4 | **CinemaScope 2.39:1** | Aspect-Ratio-Check gegen 2.39 ± 0.05. Alternativ 2.35:1 (pre-1970s). 16:9 disqualifiziert. | [Wolfcrow — Scope 2.35/2.39/2.40](https://wolfcrow.com/is-scope-2-4-2-39-or-2-35-to-1/) · [FirstDraftFilmworks — Mastering 2.39:1](https://firstdraftfilmworks.com/blog/mastering-2-39-1-aspect-ratio-film-production/) |
| U5 | **180°-Shutter Motion Blur** | Bei 24 fps → shutter 1/48 s → Cycles `motion_blur_shutter = 0.5`. Directional, nicht Gaussian. | [Wallpics — 180° Shutter Rule](https://www.wallpics.com/blogs/news/create-professional-cinematic-motion-blur-with-the-180-degree-shutter-rule) |
| U6 | **Anamorphic-Bokeh** | Sensor-Fit „Horizontal" + Anamorphic-Squeeze 2.0 in Cycles. Bokeh wird oval, nicht rund. Optional bei Studio-Presets. | [7Wonders — Anamorphic vs Spherical](https://www.7wonders.com/post/anamorphic-vs-spherical-lenses) · [Blazar — Anamorphic Guide](https://blazarlens.com/blog/whatisanamorphic/) |
| U7 | **Teal-Shadow / Warm-Highlight** | Vectorscope: Mittelwert der Shadow-Hues (Lum < 0.3) im Sektor 160–220°, Highlight-Hues (Lum > 0.7) im Sektor 20–60°. | [DaVinci Resolve Blog — Waveform/Vectorscope Guide](https://aaapresets.com/blogs/davinci-resolve-color-grading-gradient-tutorials/unlocking-videos-true-potential-a-deep-dive-into-waveform-parade-and-vectorscope-in-2025) · [VideoEditorLondon — Scopes Guide](https://www.videoeditorlondon.co.uk/post/how-to-use-davinci-resolve-scopes) |
| U8 | **Beat-Sync Trailer-Cut** | 24 fps + 120 BPM → 12 Frames/Beat exakt. 96 BPM → 15 Frames/Beat. Cuts auf Downbeats. | [Silverman Sound — BPM to FPS Calculator](https://www.silvermansound.com/bpm-to-fps-calculator) · [BChill Mix — Frame Rate to BPM](https://bchillmix.com/pages/frame-rate-bpm) |
| U9 | **Vertical Cut (9:16) für Social** | Muss aus derselben Szene rausgeschnitten werden, nicht separat gedreht. Center-Framing kompatibel halten (kein wichtiges Detail links/rechts vom Center-16:9-Column). | [FirstDraftFilmworks — Multi-Aspect Considerations](https://firstdraftfilmworks.com/blog/mastering-2-39-1-aspect-ratio-film-production/) |
| U10 | **AgX View Transform statt sRGB/Filmic** | Blender default seit 4.0. Highlights rollen kontrolliert nach Weiß statt Neon-Farben zu clippen. Verpflichtend, sonst brennen unsere Neon-Presets aus. | [Blender 4.0 Color Management Notes](https://developer.blender.org/docs/release_notes/4.0/color_management/) · [CG Cookie — AgX Raw Workflow](https://cgcookie.com/posts/the-secret-to-rendering-vibrant-colors-with-agx-in-blender-is-the-raw-workflow) |
| U11 | **Rule of Thirds — Auto auf Left-Third oder Right-Third bei Wide-Shots** | Auto-Center-Punkt darf nicht in Frame-Center (Bullseye-Look). Ausnahme: symmetrischer Front-Shot. | [Wolfcrow — 100 Camera Angles/Shots](https://wolfcrow.com/100-camera-angles-shots-and-movements-in-filmmaking/) |
| U12 | **Chase-Cam mit Auto in unteren zwei Dritteln** | Bei fahrenden Shots: Kamera behält Auto in unteren 66 % des Frames, oben Sky/Skyline für Kontext. | [In Depth Cine — 2 Ways to Shoot Car Scenes](https://www.indepthcine.com/videos/car-scenes) |

---

## 3. Look-Preset-Vorschläge für zer0one-cinema v0.3

Fünf Presets als First-Class-Feature. Jeder Preset ist ein **YAML-Manifest + Blender-Collection** (Kamera-Rig + Light-Rig + World-Setup + Compositor-Chain), das über die Pipeline injiziert wird. Namen bewusst deskriptiv statt marketing-y — Developer-Kunden verstehen sofort was drin ist.

### Preset 1 — `studio_hero_v1` (Product-Turntable)

**Referenz-DNA:** Sprite-Fright-Reflection-Only-HDRI + BMW-Product-Shot + Mike Pan's Car-Paint-Shader.

| Parameter | Wert |
|-----------|------|
| **HDRI** | `studio_softbox_8k.exr` (großflächige Softbox-Wraps, ≤ 3 Farbwerte, keine sichtbaren Objekte) — Ray-Visibility Camera OFF, Solid #0A0A0A Background |
| **Key Light** | Area 4×2 m, 45° Camera-Left, 30° oben, 800 W, 5600 K |
| **Fill** | Area 3×3 m, Camera-Right, 300 W, 5600 K |
| **Rim** | Area 1×2 m, Backside 20°-off, 500 W, 4500 K (leicht warm für Kontrast zu Fill) |
| **Camera** | 85 mm spherical, f/4.0, Sensor 36×15 (2.4:1 aspect), Height 0.75 m (Fender), Yaw −35° |
| **Animation** | 6-sec Turntable-Orbit + 2-sec End-Push-In auf Grille |
| **Compositor** | Vignette −0.15 EV, Glare Streaks 3, Subtle Grain (post-encode) |
| **Grading** | Neutral — nur Sat +5 %, kein Teal-Orange |
| **Verification-Target** | Body-Reflection Coverage ≥ 25 %, Rim-Ratio ≥ 1.8, DoF-Edge-Ratio ≥ 3× |

**Use Case:** Kunde will „mein Auto sieht cool aus" ohne Story — Katalog, Landingpage, Datenblatt.

---

### Preset 2 — `night_neon_wet_v1` (NFS-Style)

**Referenz-DNA:** NFS Heat + NFS Unbound + Blade-Runner-Palette.

| Parameter | Wert |
|-----------|------|
| **HDRI** | `neon_alley_8k.exr` (Tokio/Miami-Neon, ≥ 200 Emissive-Punkte, dominant Magenta+Cyan) |
| **Ground** | Puddle-Mask 40 % Coverage, Roughness 0.05 in Puddles / 0.3 dry, Base #050508 |
| **Fog** | Volumetric Scatter Density 0.008 global + 0.03 in Light-Cones |
| **Key Light** | 3× Emissive-Card „Neon-Sign" (Magenta 320 nm-analog, Cyan 190 nm-analog, White) — je 200 W über der Fahrbahn |
| **Rim** | Cyan Area-Light 90° hinter Auto, 600 W, 8500 K |
| **Camera** | 40 mm anamorphic (2.0× squeeze), f/2.8, Height 0.30 m, tracking-shot 3 m/s alongside |
| **Compositor** | Bloom Threshold 0.8 (aggressive), CA Dispersion 0.004, Vignette −0.3 EV, Cyan-Shadow-Lift, Magenta-Highlight-Gain |
| **Grading** | Vectorscope-Target: Shadows Hue 190°, Highlights Hue 320° |
| **Verification-Target** | Wet-Ground-Emissive-Reflection-Cluster ≥ 8, Volumetric-Cones ≥ 3, Bloom-Coverage 5–15 % |

**Use Case:** Game-Studios, Sportwagen-Launches, Sneaker-Kollab-Videos.

---

### Preset 3 — `golden_hour_hero_v1` (BMW/Mercedes-Werbespot)

**Referenz-DNA:** BMW iX „Driven by Emotion" + Mercedes-Benz „Lucky Star" + The-Hire Ang-Lee-Sequenz.

| Parameter | Wert |
|-----------|------|
| **HDRI** | `desert_road_sunset_8k.exr` oder `alpine_pass_sunset_8k.exr` — Sonne 5° über Horizont, warme Sky-Gradation |
| **Key Light** | Sun-Emitter 3.5 W/m², 2700 K (warmes Gold), Angle 5°, Sun-Size 2° |
| **Fill** | Sky-Contribution via HDRI, keine Zusatz-Area |
| **Rim** | Automatisch durch flachen Winkel + Backlight aus Sonne |
| **Camera** | 50 mm anamorphic, f/2.8 für Details / f/5.6 für Wide, Height 0.6 m, Slow-Dolly parallel |
| **Animation** | Slow 30 % Time-Warp (Slow-Motion-Feel), Long-Take 8–12 sec |
| **Compositor** | Bloom Threshold 1.2 (subtle), Warm-Halation, Vignette −0.15 EV, kein CA, Grain minimal |
| **Grading** | Split-Tone Orange-Highlights / Teal-Shadows (klassisch), Sat 1.10 |
| **Verification-Target** | Sun-Angle 3–8°, Mean-Highlight-Hue 35–55°, Halation-Radius ≥ 8 px an Highlights |

**Use Case:** Premium-OEM-Kunden, Luxury-Sedan-Launches, „Lifestyle-nicht-Performance"-Positionierung.

---

### Preset 4 — `documentary_race_v1` (Le-Mans / GT-Movie Style)

**Referenz-DNA:** Ford v Ferrari + Gran Turismo 2023 + Formula-1-Onboards.

| Parameter | Wert |
|-----------|------|
| **HDRI** | `racetrack_overcast_8k.exr` (Le-Mans, Nürburgring-Nordschleife) — flaches Licht |
| **Key Light** | Sun-Emitter 2.5 W/m², 5500 K (neutrale Sonne), Angle 30° hoch |
| **Fill** | Overcast-HDRI liefert automatisch |
| **Rim** | Bewusst schwach — kein artifizielles Rim, nur Sun-Backlight bei 45°-Yaw |
| **Camera** | 24 mm spherical für Hard-Mount-POV, 100 mm spherical für Rig-Cars, f/5.6 (deep DoF für Motorsport-Feel), Height 0.15 m für Onboard / 0.25 m für Track-Cam |
| **Animation** | Micro-Shake ±0.5° auf Camera-Rotation (raw feel), keine Full-Stabilization |
| **Compositor** | Kein Bloom, Vignette −0.10 EV, 35mm-Grain (temporal, mid), kein CA |
| **Grading** | Fast neutral — leicht warm-Highlight-Push, Kontrast +10 %, keine Teal-Shadows |
| **Verification-Target** | Camera-Shake-Amplitude ≥ 0.3° RMS, Bloom-Coverage < 2 %, Motion-Blur Direction-Consistency ≥ 0.90 |

**Use Case:** Sim-Racing-Trailer, Motorsport-Sponsoren, Endurance-Race-Teaser, „echt"-Ästhetik statt Werbespot.

---

### Preset 5 — `bmw_films_hire_v1` (Narrative Short)

**Referenz-DNA:** BMW Films „The Hire" (Ritchie/Fincher/Woo-Episoden), Baby Driver, Drive (2011).

| Parameter | Wert |
|-----------|------|
| **HDRI** | `urban_night_8k.exr` (Straßenschluchten, mixed sodium+LED, weniger neon-lastig als Preset 2) |
| **Key Light** | Practicals — Street-Lamps als Emissive-Meshes 3200 K, Car-Headlights 5000 K |
| **Fill** | Sky-Fill nur 5 %, Rest via Bounce-Cards nahe Camera |
| **Rim** | Situativ — von passierender Ampel/Storefront |
| **Camera** | 35 mm anamorphic Master + 85 mm für Insert-Close-Ups, f/2.0 (shallow DoF für Charakter-Feel), Height variabel (Insert 0.3 m, Master 1.6 m) |
| **Animation** | Cut-Rhythmus als First-Class: 4-sec Wide → 1-sec Wheel-Insert → 2-sec Driver-POV → 6-sec Chase (BPM-sync ≥ 96) |
| **Compositor** | Halation gold-warm um Practicals, Grain mid, Vignette −0.20 EV, moderate CA |
| **Grading** | Crushed Blacks (Black-Point +5 % but with cyan cast), warm Amber Highlights (Sodium-Lamps) |
| **Verification-Target** | Cut-BPM-Sync ± 2 Frames, Practicals-Count ≥ 6, Halation-Ring auf ≥ 40 % der Practicals |

**Use Case:** Kunden die Storytelling wollen — Marken-Filme, Founder-Stories, Auto als Character.

---

### Optional Preset 6 — `blender_studio_stylized_v1` (Ausblick, nicht in v0.3)

Nicht photoreal — cell-shaded / painterly. Wenn wir Game-Dev-Kunden im Casual-Segment adressieren wollen (Mario-Kart-Style, Rocket-League-Kollab). Basiert auf Blender-Studio-Shader-Pack. **Empfehlung: für v0.4 zurückstellen** — würde die Positionierung zu breit machen.

---

## 4. Cinema-Look-Analysis-Tools (Open-Source)

Für unser Verification-Gate müssen wir Look-Metriken **automatisiert** messen können — nicht per Auge. Diese Toolchain ist praxiserprobt und ohne Lizenzkosten.

| Tool | Nutzung bei uns | Command / Filter |
|------|-----------------|------------------|
| **FFmpeg + `signalstats`** | Frame-weise Luminance, Chroma-Mean, Saturation-Peaks als CSV | `ffmpeg -i input.mp4 -vf signalstats,metadata=print -f null -` |
| **FFmpeg + `waveform`** | Waveform-Monitor als Bild rendern (visueller Check + Diff gegen Reference) | `ffmpeg -i in.mp4 -vf waveform=intensity=0.1:mode=column out_wave.png` |
| **FFmpeg + `vectorscope`** | Vectorscope als Bild — Test ob Shadows im Teal-Sektor liegen | `ffmpeg -i in.mp4 -vf vectorscope=mode=color4:x=UV out_vs.png` |
| **FFmpeg + `histogram`** | Per-Channel-Histogram für Black-Point / White-Point Verifikation | `ffmpeg -i in.mp4 -vf histogram=level_height=200 out_hist.png` |
| **FFprobe + `-show_frames`** | Frame-Metadaten (Aspect-Ratio-Check gegen 2.39:1, fps, color_space) | `ffprobe -select_streams v:0 -show_frames -of json in.mp4` |
| **QCtools (BAVC)** | Batch-Analyse mit vielen Filtern gleichzeitig, XML-Report für CI | `qcli -i in.mp4 -o report.xml.gz` |
| **DaVinci Resolve Free** | Manueller Deep-Check bei Preset-Kalibrierung (nicht in CI-Pipeline) | GUI |
| **OpenCV + Sobel** | Edge-Strength für DoF-Verification (Auto scharf vs. Background weich) | Python-Script in unserem verify_frame.py bereits vorhanden |

**Empfehlung:** In `zer0one-cinema/tools/analyze/` einen `look_probe.py` bauen, der FFmpeg-Vectorscope + Waveform + Histogram parst und JSON gegen Preset-Manifest-Targets vergleicht. Dann Gate 6 (Grading) im CGVF-Framework wird deterministisch prüfbar.

**Sources:** [Programming Historian — FFmpeg Color Analysis](https://programminghistorian.org/en/lessons/introduction-to-ffmpeg) · [QCtools Playback Filters](http://bavc.github.io/qctools/playback_filters.html) · [FFmpeg Vectorscope Gist](https://gist.github.com/sam210723/f455b3b95b0f6a9edae5a083ee8fcab4) · [Frame.io — When to Use Color Scopes](https://blog.frame.io/2023/09/18/when-to-use-color-scopes-and-when-not-to/)

---

## 5. Anti-Pattern-Katalog (Amateur-Signals)

Diese müssen wir im Verification-Layer **hart erkennen** (Fail-Gate, nicht Warning) und in Preset-Templates konstruktiv vermeiden.

| # | Anti-Pattern | Warum tödlich | Auto-Detection |
|---|--------------|---------------|----------------|
| A1 | **AO überzogen** (Ambient-Occlusion-Slider hochgezogen als „Detail"-Ersatz) | Wirkt wie Dirty-Wash unter jeder Kante, killt Lack-Realismus | AO-Pass-Extraction + Mean Compare: AO-Contrib > 0.15 im Body-Bereich → Fail |
| A2 | **Flat Lighting** (nur HDRI ohne Key/Rim/Fill) | Kein Highlight-Modeling, Silhouette verschwindet | Rim-Ratio (Kanten-Lum vs. Innen-Lum) < 1.2 → Fail |
| A3 | **Kein AgX / Filmic** (sRGB View oder gar Raw-Linear direkt) | Neon-Highlights clippen zu Solid-Color, Sunlight brennt weiß aus | Read Blender-File Color-Space Metadata; wenn nicht AgX oder Filmic → Fail |
| A4 | **Auto Frame-Rand-Cropping** (Wheel oder Bumper aus Frame ragen ungewollt) | Wirkt wie Amateur-Composition, „Kamera-Mann-Fehler" | Bounding-Box vs. Frame-Edge Distance < 20 px → Warning (Fail wenn Overlap) |
| A5 | **Wheels floating oder versinken** | Contact-Patch-Check aus Detail 14 (Cinema-Standards) — hier ergänzt um Detection: kein Contact-Shadow unter Wheel | Sample 40 px Radius unter jedem Wheel-Center, wenn Luminance = Ground-Baseline → Fail |
| A6 | **Uniform Roughness auf Body** | Ganze Karosserie hat exakt gleichen Glanz — verrät Standard-Shader ohne Variation | Body-Mask + Variance der Specular-Highlights, wenn σ < threshold → Fail |
| A7 | **Flat Ground ohne Detail** | Perfekt-eben, keine Bump-Map, keine Puddles, keine Cracks — sofort CGI-Signal | Frequency-Analyse der Ground-Region: high-frequency energy < threshold → Fail |
| A8 | **Gaussian statt Directional Motion Blur** | Wirkt wie Foto-Fehler statt Bewegung | Optical-Flow-Vergleich (bereits in verify_frame.py) |
| A9 | **Kein Contact-Shadow** (Ground-Shadow nur global, nicht scharf am Berührungspunkt) | „Pasted"-Look | Shadow-Density direkt an Wheel-Base < 0.6 → Fail |
| A10 | **Sun in wrong Hemisphere** (Sun-Emitter über Horizont eingezeichnet, aber Sky-HDRI zeigt Sun woanders) | Physikalisch unmöglich, sofort erkennbar | Cross-Check Sun-Direction vs. HDRI-Peak-Luminance-Location |
| A11 | **Overdone Lens-Flares** (Star-Wars-Style, > 6 Streaks) | Amateur-„coole Effekte" | Streak-Detection (bereits Detail 6), Count > 5 → Fail |
| A12 | **Bullseye-Composition** (Auto exakt in Frame-Center bei Wide-Shot) | Verletzt Rule of Thirds | Bounding-Box-Center vs. Frame-Center Distance in wide-shots < 10 % Frame-Width → Warning |
| A13 | **16:9 als Trailer-Aspect** | Ist TV-Format, nicht Kino | Aspect-Check gegen 2.39 ± 0.05 |
| A14 | **Uniform-Color-Environment** (leerer Background, Solid-Sky, keine Skyline) | Test-Setup-Feeling | Non-Black-Pixel-Ratio im Bg < 20 % → Fail |
| A15 | **Perfectly aligned RGB** (kein CA-Hint an High-Contrast-Edges) | Digital-CGI-Signal, keine „Optik" | Chromatic-Aberration-Distance an Edges < 0.5 px → Warning für Cinematic-Presets |

**Sources:** [360Render — Why 3D Product Renders Look Fake](https://www.360render.com/3d-rendering/why-your-3d-product-renders-look-fake-5-common-lighting-and-material-mistakes/) · [3SFarm — 10 Blender Render Mistakes](https://blog.3sfarm.com/10-blender-3d-render-mistakes-and-how-to-fix-them) · [Archiviz — Top Rendering Mistakes](https://archiviz.io/blog/rendering-mistakes/) · [Coohom — 3D Rendering Looks Flat Fix](https://www.coohom.com/article/how-to-render-3d-objects-on-a-2d-plane)

---

## 6. Konkrete v0.3-Empfehlungen (Handoff an Sprint-19-Planning)

1. **5 Presets als First-Class-Feature** (`studio_hero`, `night_neon_wet`, `golden_hour_hero`, `documentary_race`, `bmw_films_hire`) — YAML-Manifest + Blender-Collection, injizierbar per CLI (`zer0one-cinema render --preset night_neon_wet vehicle.glb`).
2. **`look_probe.py` bauen** — FFmpeg-basiertes Scope-Reading, JSON-Output, das Gate 6 (Grading) deterministisch macht.
3. **Preset-Manifest-Schema** enthält für jedes Preset die Waveform/Vectorscope-Targets (siehe Preset-Tabellen oben) — Verification kann dann pro Preset unterschiedliche Toleranzen anwenden (documentary_race darf kein starkes Teal haben, night_neon_wet muss es haben).
4. **Anti-Pattern A1–A15 im verify_frame.py implementieren** — jeder Fail blockiert den Final-Render, Warning erzeugt Notice im QA-Report.
5. **EEVEE-Preview-Modus für alle Presets** (Learning aus Blender-Studio Charge) — 10-20× schneller für Iteration, Cycles nur für Final auf RunPod.
6. **BMW-Films-Preset = Cut-Template-Feature** — der Preset ist mehr als Farbe, er ist Choreo (Wide → Insert → POV → Chase). Erfordert dass unser Storyboard-Modul Sequence-Templates unterstützt.

---

## Anhang — Vollständige Quellen-Übersicht

**Trailer & Cinematography:**
- Ford v Ferrari: [Color Culture](https://colorculture.org/ford-v-ferrari-cinematography-analysis/), [Film Independent](https://www.filmindependent.org/blog/dp-phedon-papamichael-on-the-vintage-look-and-analog-action-of-ford-v-ferrari/), [Deadline](https://deadline.com/2019/12/ford-v-ferrari-cinematographer-phedon-papamichael-the-trial-of-the-chicago-7-the-art-of-craft-interview-news-1202812909/), [No Film School](https://nofilmschool.com/ford-ferrari-phedon-papamichael-interview), [ShotOnWhat](https://shotonwhat.com/ford-v-ferrari-2019), [Newsshooter](https://www.newsshooter.com/2019/11/28/ford-v-ferrari-cinematography/)
- NFS Heat/Unbound: [HotCars](https://www.hotcars.com/new-need-for-speed-unbound-trailer-sets-tone-for-franchise/), [GamesRadar](https://www.gamesradar.com/need-for-speed-heats-palm-city-is-a-neon-lit-beauty-in-new-launch-trailer/), [Filmmakers Academy](https://www.filmmakersacademy.com/camera-need-for-speed/), [Nexus Mods Cinematic Preset](https://www.nexusmods.com/needforspeedheat/mods/478)
- Gran Turismo: [Hollywood Reporter](https://www.hollywoodreporter.com/movies/movie-news/gran-turismo-racing-scenes-cinematographer-nab-2023-1235376240/), [ASC](https://theasc.com/article/in-drivers-seat-for-gran-turismo/), [Sony Cine](https://sony-cinematography.com/articles/shot-on-venice-jacques-jouffret-asc-brings-racing-realism-to-gran-turismo-using-venice-2-and-the-rialto-extension-system/), [Leitz Cine](https://www.leitz-cine.com/production/gran-turismo-2023), [Befores & Afters](https://beforesandafters.com/2023/09/16/make-them-go-f-a-s-t/), [GTPlanet BTS](https://www.gtplanet.net/gran-turismo-bts-video-20230726/)
- BMW Films / Mercedes: [Wikipedia — The Hire](https://en.wikipedia.org/wiki/The_Hire), [Open Culture](https://www.openculture.com/2014/07/watch-the-bmw-film-series-the-hire.html), [Motor1](https://www.motor1.com/news/420770/bmw-the-hire-films-remastered/), [Film Stories](https://filmstories.co.uk/features/david-fincher-tony-scott-john-woo-and-more-the-bmw-mini-cinematic-universe/), [BMWBlog — BMW Films Retrospective](https://www.bmwblog.com/2019/11/15/bmw-films-showed-the-world-what-a-car-commercial-could-be/), [AutoAds Automotive Marketing Evolution](https://autoads.co.za/video-marketing-that-moves-cinematic-campaigns-in-automotive-advertising)
- Blender Studio: [Sprite Fright Master Class](https://studio.blender.org/blog/Sprite-Fright-Master-Class-Lighting-Rendering/), [Sprite Fright Workflow](https://studio.blender.org/blog/sprite-fright-workflow-lighting-set-dressing/), [Charge Premiere](https://studio.blender.org/blog/charge-premiere/), [Charge Project](https://studio.blender.org/films/charge)

**Techniken:**
- Framing/Angles: [Blendnow](https://www.blendnow.com/blog/car-photography-angles), [Spyne](https://www.spyne.ai/blogs/car-photography-angles), [ISO1200](https://www.iso1200.com/2026/01/the-hero-shot-how-low-angles-transform.html), [Furoore](https://furoore.com/automotive-photography/), [LensViewing](https://lensviewing.com/camera-angles-cars-driving-cinematic/), [Wolfcrow — 100 Angles](https://wolfcrow.com/100-camera-angles-shots-and-movements-in-filmmaking/), [In Depth Cine](https://www.indepthcine.com/videos/car-scenes), [Red Summit Productions](https://redsummitproductions.com/blog/pro-tips-how-to-film-a-car-commercial), [Soundstripe](https://www.soundstripe.com/blogs/how-to-shoot-a-car-commercial)
- Lenses: [7Wonders](https://www.7wonders.com/post/anamorphic-vs-spherical-lenses), [Blazar](https://blazarlens.com/blog/whatisanamorphic/), [Cooke Optics](https://cookeoptics.com/news-and-events/spherical-vs-anamorphic-lenses/), [Better Focus](https://better-focus.com/blogs/news/anamorphic-spherical-fov)
- Aspect / Shutter: [Wolfcrow — Scope Ratios](https://wolfcrow.com/is-scope-2-4-2-39-or-2-35-to-1/), [FirstDraftFilmworks — 2.39:1](https://firstdraftfilmworks.com/blog/mastering-2-39-1-aspect-ratio-film-production/), [Widescreen.org — Aspect Ratios](https://widescreen.org/aspect_ratios.shtml), [Wallpics — 180° Shutter](https://www.wallpics.com/blogs/news/create-professional-cinematic-motion-blur-with-the-180-degree-shutter-rule)
- Color/Grading: [DaVinci Waveform Deep Dive](https://aaapresets.com/blogs/davinci-resolve-color-grading-gradient-tutorials/unlocking-videos-true-potential-a-deep-dive-into-waveform-parade-and-vectorscope-in-2025), [VideoEditorLondon Scopes Guide](https://www.videoeditorlondon.co.uk/post/how-to-use-davinci-resolve-scopes), [CROMO Scopes Guide](https://cromostudio.it/cromo-tips/how-to-read-scopes-in-davinci-resolve-a-complete-guide), [Frame.io Scopes](https://blog.frame.io/2023/09/18/when-to-use-color-scopes-and-when-not-to/), [Tektronix Color Grading Primer PDF](https://download.tek.com/document/Color-Grading-Primer-Full_App-Note_2PW_28619_1.pdf), [AramK Teal-Orange Tutorial](https://aramk.us/blog/davinci-resolve-18-simple-teal-and-orange-look-color-grading-tutorial/)
- Color Management: [Blender 4.0 Release Notes](https://developer.blender.org/docs/release_notes/4.0/color_management/), [CG Cookie AgX Raw](https://cgcookie.com/posts/the-secret-to-rendering-vibrant-colors-with-agx-in-blender-is-the-raw-workflow), [TooDee AgX Setup](https://www.toodee.de/exploring-hdr-displays/blender-and-agx/), [Blendergrid Color Management](https://blendergrid.com/articles/color-management-in-blender)
- Materials: [Beffio Car Paint 3.0 Docs](https://www.beffio.com/car-paint-documentation), [Oded Erell Cycles Car Paint](https://odederell3d.blog/2019/09/30/customizable-photo-realistic-car-paint-shader-for-cycles/), [Mike Pan Car Paint BRDF](https://blog.mikepan.com/post/137759885931/realistic-car-paint-brdf-material), [88Cars3D Substance Setup](https://88cars3d.com/2025/12/29/foundations-of-automotive-texturing-and-substance-painter-setup/)
- Wet Ground: [Morphic Wet Shader](https://www.themorphicstudio.com/wet-shader-in-blender/), [BlenderNation Cyberpunk Puddles](https://www.blendernation.com/2019/04/24/realistic-puddles-and-wet-ground-cyberpunk-reflections-in-blender-2-8-eevee/), [Blender Guru Puddles](https://www.blenderguru.com/tutorials/how-to-create-realistic-puddles)
- Lighting Basics: [Vagon Product Lighting](https://vagon.io/blog/mastering-product-lighting-in-blender-techniques-for-stunning-3d-renders), [Lightmap Smart Car](https://www.lightmap.co.uk/learning/blender-tutorial-02/), [MattePaint 3-Point HDRI](https://mattepaint.com/academy/tutorial/three-point-lighting-in-blender/), [Creative Bloq Key/Fill/Rim](https://www.creativebloq.com/3d/how-to-use-key-fill-and-rim-lighting-in-3d-art)
- Anti-Patterns: [360Render Fake Renders](https://www.360render.com/3d-rendering/why-your-3d-product-renders-look-fake-5-common-lighting-and-material-mistakes/), [3SFarm 10 Mistakes](https://blog.3sfarm.com/10-blender-3d-render-mistakes-and-how-to-fix-them), [Archiviz Rendering Mistakes](https://archiviz.io/blog/rendering-mistakes/), [Coohom Flat Fix](https://www.coohom.com/article/how-to-render-3d-objects-on-a-2d-plane), [GiveNewLook Common Mistakes](https://givenewlook.com/common-3d-rendering-mistakes-and-how-to-avoid-them/)
- Analysis Tools: [Programming Historian FFmpeg](https://programminghistorian.org/en/lessons/introduction-to-ffmpeg), [QCtools Playback Filters](http://bavc.github.io/qctools/playback_filters.html), [FFmpeg Vectorscope Gist](https://gist.github.com/sam210723/f455b3b95b0f6a9edae5a083ee8fcab4), [Drastic Software Waveform](https://www.drastic.tv/support-59/232-software-based-video-waveform-vectorscope-monitoring-a-comprehensive-guide)
- Post-Processing: [Gamine AI Cinematics 2026](https://www.gamineai.com/blog/color-grading-and-post-processing-for-game-cinematics-2026), [Dehancer Bloom](https://blog.dehancer.com/articles/bloom-what-it-is-and-how-it-works/), [Evergine Postprocessing Docs](https://docs.evergine.com/2024.6.28/manual/graphics/postprocessing_graph/default_postprocessing_graph/tonemapping.html)
- BPM/Cutting: [Silverman BPM-to-FPS](https://www.silvermansound.com/bpm-to-fps-calculator), [BChill Frame-to-BPM](https://bchillmix.com/pages/frame-rate-bpm), [LA Music Trailer 101](https://losangelesmusic.io/blog/trailer-music), [Audiodrome Car Reels Music](https://audiodrome.net/use-cases/music-for-car-reels/)
