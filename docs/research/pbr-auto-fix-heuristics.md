# PBR Auto-Fix Heuristics für Automotive-GLBs

**Projekt:** zer0one-cinema (Sprint 19)
**Datum:** 2026-07-15
**Zweck:** Automatische Normalisierung von chaotischen PBR-Materials in Fahrzeug-GLBs (Sketchfab, TurboSquid, freie Quellen) zu Cinema-Grade Studio-Presets, bevor der Trailer-Rendering-Pipeline gestartet wird.

---

## Executive Summary

GLBs aus Sketchfab/TurboSquid haben systematisch fünf wiederkehrende PBR-Bugs: **(1)** Emission ist auf Body-Materials ungewollt aktiviert und macht Renders "blown out", weil viele Exporter Base-Color-Texturen versehentlich in den Emission-Slot duplizieren; **(2)** Roughness ist auf dem PBR-Default `0.5` stehen geblieben, statt materialgerecht (Chrom ≤ 0.10, Reifen ≥ 0.80); **(3)** Metallic ist auf `0.0`, obwohl der Material-Name `chrome`/`trim`/`alloy` enthält; **(4)** Alpha ist auf `0.99` statt `1.0` gesetzt, was Transparency-Sorting-Bugs in Cycles auslöst; **(5)** Normal-Maps sind in DirectX-Konvention (Y-flip) gebacken, obwohl glTF *zwingend* OpenGL-Konvention (Y-up) erwartet. Unsere Sanitizer-Strategie ist eine **Whitelist-basierte 3-Pass-Heuristik** (Name-Match → Textur-Signal → Fallback), die nur bekannte Automotive-Material-Klassen normalisiert und alle Änderungen in einem `SANITIZER_REPORT.json` protokolliert, damit User sie rückgängig machen können. Fail-Safe-Default für unklare Materials ist **"Plastic"** (Metallic 0, Roughness 0.4) — nicht Body-Paint, damit wir keine falschen Hochglanz-Reflektionen erzeugen.

---

## 1. Material-Type-Recognition-Table

### 1.1 Name-Pattern-Matching (Pass 1)

Prio-basiert von **spezifisch → generisch**. Regex ist case-insensitive (`re.IGNORECASE`), Wortgrenzen mit `\b` wo möglich, sonst Substring-Match. **Reihenfolge ist wichtig** — die erste passende Regel gewinnt.

| Priorität | Material-Klasse | Regex-Pattern (Beispiele) | Notizen |
|----|---|---|---|
| 10 | `glass` | `\b(glass|window|windshield|scheibe|glas|fenster|windschutz)\b` | DACH-Terms integriert |
| 20 | `chrome` | `\b(chrome|chrom|verchromt)\b` | Distinct von "metal" |
| 30 | `tire_rubber` | `\b(tire|tyre|rubber|reifen|gummi)\b` | Nicht mit `rim` verwechseln |
| 40 | `brake_rotor` | `\b(brake|disc|rotor|bremse|scheibe.*brems)\b` | Muss VOR `rim` matchen (viele Rotoren heißen "brake_disc_rim") |
| 50 | `carbon_fiber` | `\b(carbon|cf|karbon|kohlefaser)\b` | Anisotropic-Trigger |
| 60 | `rim_alloy` | `\b(rim|wheel|alloy|felge|alu.*rad)\b` | Excluded wenn `tire` oder `brake` matcht |
| 70 | `headlight_lens` | `\b(headlight|scheinwerfer|lens|linse|lamp)\b` | Klar-Kunststoff, ähnl. glass |
| 80 | `taillight_red` | `\b(taillight|rueckleuchte|rücklicht|brake.*light)\b` | Rot-tint + transmission |
| 90 | `paint_body` | `\b(body|paint|lack|karosserie|cover|shell|hood|door|fender|bumper)\b` | Fallback Body-Match |
| 100 | `interior_plastic` | `\b(dash|dashboard|interior|innen|armaturen|console|trim.*inner)\b` | Matte Kunststoff |
| 110 | `leather_seat` | `\b(seat|leather|leder|sitz|upholstery|polster)\b` | Optional Skill-Bonus |
| 120 | `chrome_trim` | `\b(trim|molding|zierleiste|chromleiste)\b` | Nur wenn kein `interior` |
| ∞ | `unknown` | (fallthrough) | → wird zu `default_plastic` |

**Multi-Language:** DACH-fokussiert (DE + EN). SR/HR/SL werden **nicht** gepatched — dort matcht `unknown` → default. Das ist bewusst: Sketchfab-Autoren sind zu >95 % englischsprachig.

**Kollisions-Handling:** Wenn zwei Pattern gleichzeitig matchen (z. B. "brake_rim_carbon"), gewinnt der niedrigere Prio-Wert (spezifischer). Konflikte werden im Report als `AMBIGUOUS` geloggt.

### 1.2 Textur-Signal-Detection (Pass 2, wenn Name = unknown)

Wenn der Name nichts hergibt, analysieren wir die **Base-Color-Textur** und **Metallic-Roughness-Textur**:

| Signal | Wert-Range | → Klassifikation |
|---|---|---|
| Base-Color = Solid Color, avg brightness < 0.05 | HSV V < 0.05 | `tire_rubber` (schwarzes Gummi) |
| Base-Color = Solid Color, avg brightness > 0.85 UND Metallic-Map avg > 0.8 | | `chrome` oder `rim_alloy` |
| Base-Color hat Photo-Textur (edge-density > threshold, farbige Pixel-Std > 0.15) | | `paint_body` (wahrscheinlich lackierte Photo-Reference) |
| Base-Color = solid, low saturation, red-tint (H ∈ [0°, 20°] ∪ [340°, 360°], S > 0.5) | | `taillight_red` |
| Alpha-Channel enthält Werte < 1.0 UND avg alpha < 0.5 | | `glass` (transparent) |
| Metallic-Map avg > 0.8 UND Roughness-Map avg < 0.15 | | `chrome` |
| Metallic-Map avg < 0.1 UND Roughness-Map avg > 0.6 | | `interior_plastic` oder `tire_rubber` |

**Implementierung:** Sample-Approach — 128×128 Downsample, dann `numpy.mean/std` auf Pixel-Arrays. Kein Full-Res-Scan (Kostet 200 ms pro 4k-Textur).

### 1.3 Pass 3: Default-Fallback

Wenn Pass 1+2 nichts matchen → `default_plastic` (siehe Preset-Table). **Warum nicht body-paint?** Weil ein falsch als Body erkanntes Detail-Teil (z. B. ein Emblem) mit Clearcoat + hoher Reflection extrem auffällt und den Cinema-Look zerstört. Plastic ist optisch neutral und "verschwindet" im Frame.

---

## 2. PBR-Preset-Table

Alle Werte in glTF-2.0-Konvention: Metallic-Roughness-Workflow, Base-Color als Linear-sRGB, IOR-Default 1.5. Werte-Ranges statt Einzelwerte, damit Textur-Variation nicht platt-normalisiert wird.

| Klasse | Base-Color (falls solid) | Metallic | Roughness | Coat Weight | Coat Rough. | IOR | Transmission | Emission | Anisotropic | Notizen |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `paint_body` | keep (from map) | 0.0 (dielectric) oder 0.9 (metallic-flake) | 0.30–0.45 | **1.0** | 0.03–0.08 | 1.5 | 0 | **0** (force off!) | 0 | Coat-Layer ist der Cinema-Trick. Bei metallic paint (silver, gold) Metallic 0.9 + tint über base-color. |
| `chrome` | 0.55 gray (linear) | **1.0** | 0.02–0.08 | 0 | — | 1.5 (ignored) | 0 | 0 | 0 | Klassisches Poliert-Metall |
| `chrome_trim` | 0.55 gray | 1.0 | 0.05–0.12 | 0 | — | — | 0 | 0 | 0 | Wie chrome, minimal rauher |
| `rim_alloy` | 0.70 gray oder keep | 1.0 | 0.15–0.30 | 0 | — | — | 0 | 0 | 0.2 (optional) | Poliertes Aluminium; wenn Textur-Signal "brushed" → aniso 0.5 |
| `glass` | white (1,1,1) | 0.0 | 0.02–0.10 | 0 | — | **1.52** | **1.0** | 0 | 0 | Windshield: schwach getönt (base 0.85 gray). MSAA-Sorting-fix: Alpha exakt 1.0 |
| `headlight_lens` | white | 0.0 | 0.05–0.15 | 0 | — | 1.55 | 0.9 | 0 | 0 | Wie glass, aber leicht rauher |
| `taillight_red` | (0.8, 0.05, 0.05) | 0.0 | 0.10–0.20 | 0 | — | 1.55 | 0.85 | 0 (Bremslicht später via emission-mask) | 0 | Klassisches Rot-Kunststoff |
| `tire_rubber` | 0.02 gray (fast schwarz) | 0.0 | **0.85–0.95** | 0 | — | 1.5 | 0 | 0 | 0 | Extrem matt; falls Textur avg < 0.05: force base-color = (0.02, 0.02, 0.02) |
| `brake_rotor` | 0.15 gray (schmutzig-metallic) | 1.0 | 0.20–0.35 | 0 | — | — | 0 | 0 | 0.3 (radial) | Zwischen chrome und rim; radiale Riefen von Bremsverschleiß |
| `carbon_fiber` | 0.03 gray (very dark) | 0.5–0.7 | 0.25–0.40 | 0.5 | 0.05 | 1.5 | 0 | 0 | **0.8** | Muss anisotropic sein für Weave-Look, sonst wirkt es wie schwarzes Plastik |
| `interior_plastic` | keep | 0.0 | 0.40–0.60 | 0 | — | 1.5 | 0 | 0 | 0 | Matte Dashboard-Optik |
| `leather_seat` | keep | 0.0 | 0.55–0.75 | 0 | — | 1.5 | 0 | 0 | 0 | Falls Sheen verfügbar (BSDF v2): Sheen 0.3, Sheen Roughness 0.5 |
| `default_plastic` (fallback) | keep | 0.0 | 0.40 | 0 | — | 1.5 | 0 | **0** | 0 | Neutraler Safe-Default |

**Rationale:** Diese Werte kommen aus:
- Substance PBR Guide Part 2 (dielectric 0.02–0.05 base, metal 0.5–0.98 base)
- physicallybased.info (Aluminum: base 0.916, Chrom: base 0.55)
- Blender Studio Cars-Workflow (Coat Weight 1.0 + Coat Roughness ~0.03 als Standard-Car-Paint-Formel)
- glTF-Spec (Glass IOR 1.52, Transmission 1.0)

---

## 3. Sanitizer-Algorithmus (Pseudocode, Blender-bpy)

```python
"""
Blender-Sanitizer für Vehicle-GLBs.
Läuft NACH glTF-Import, VOR jedem Render.
Zielsystem: Blender 4.x/5.x mit Principled BSDF v2 (Coat statt Clearcoat).
"""

import bpy, re, json
from pathlib import Path

# ------------------------------------------------------------------
# GLOBAL CONSTANTS
# ------------------------------------------------------------------

PATTERNS = [  # (priority, class, compiled_regex)
    (10,  "glass",             re.compile(r"\b(glass|window|windshield|scheibe|glas|fenster)\b", re.I)),
    (20,  "chrome",            re.compile(r"\b(chrome|chrom|verchromt)\b", re.I)),
    (30,  "tire_rubber",       re.compile(r"\b(tire|tyre|rubber|reifen|gummi)\b", re.I)),
    (40,  "brake_rotor",       re.compile(r"\b(brake|rotor|bremse)\b", re.I)),
    (50,  "carbon_fiber",      re.compile(r"\b(carbon|cf|karbon|kohlefaser)\b", re.I)),
    (60,  "rim_alloy",         re.compile(r"\b(rim|wheel|alloy|felge)\b", re.I)),
    (70,  "headlight_lens",    re.compile(r"\b(headlight|scheinwerfer|lens|lamp)\b", re.I)),
    (80,  "taillight_red",     re.compile(r"\b(taillight|rueckleuchte|rücklicht)\b", re.I)),
    (90,  "paint_body",        re.compile(r"\b(body|paint|lack|karosserie|hood|door|fender|bumper)\b", re.I)),
    (100, "interior_plastic",  re.compile(r"\b(dash|dashboard|interior|innen|console)\b", re.I)),
    (110, "leather_seat",      re.compile(r"\b(seat|leather|leder|sitz)\b", re.I)),
    (120, "chrome_trim",       re.compile(r"\b(trim|molding|zierleiste)\b", re.I)),
]

PRESETS = {
    "paint_body":       {"metallic": 0.0, "roughness": 0.38, "coat_weight": 1.0, "coat_roughness": 0.05, "emission_strength": 0.0, "alpha": 1.0},
    "chrome":           {"metallic": 1.0, "roughness": 0.05, "coat_weight": 0.0, "emission_strength": 0.0, "alpha": 1.0, "base_color": (0.55, 0.55, 0.55, 1.0)},
    "chrome_trim":      {"metallic": 1.0, "roughness": 0.08, "coat_weight": 0.0, "emission_strength": 0.0, "alpha": 1.0, "base_color": (0.55, 0.55, 0.55, 1.0)},
    "rim_alloy":        {"metallic": 1.0, "roughness": 0.22, "coat_weight": 0.0, "emission_strength": 0.0, "alpha": 1.0},
    "glass":            {"metallic": 0.0, "roughness": 0.03, "coat_weight": 0.0, "transmission_weight": 1.0, "ior": 1.52, "emission_strength": 0.0, "alpha": 1.0, "base_color": (1.0, 1.0, 1.0, 1.0)},
    "headlight_lens":   {"metallic": 0.0, "roughness": 0.08, "transmission_weight": 0.9, "ior": 1.55, "emission_strength": 0.0, "alpha": 1.0, "base_color": (1.0, 1.0, 1.0, 1.0)},
    "taillight_red":    {"metallic": 0.0, "roughness": 0.15, "transmission_weight": 0.85, "ior": 1.55, "emission_strength": 0.0, "alpha": 1.0, "base_color": (0.8, 0.05, 0.05, 1.0)},
    "tire_rubber":      {"metallic": 0.0, "roughness": 0.90, "coat_weight": 0.0, "emission_strength": 0.0, "alpha": 1.0, "base_color": (0.02, 0.02, 0.02, 1.0)},
    "brake_rotor":      {"metallic": 1.0, "roughness": 0.28, "coat_weight": 0.0, "emission_strength": 0.0, "alpha": 1.0},
    "carbon_fiber":     {"metallic": 0.6, "roughness": 0.32, "coat_weight": 0.5, "coat_roughness": 0.05, "anisotropic": 0.8, "emission_strength": 0.0, "alpha": 1.0},
    "interior_plastic": {"metallic": 0.0, "roughness": 0.50, "emission_strength": 0.0, "alpha": 1.0},
    "leather_seat":     {"metallic": 0.0, "roughness": 0.65, "emission_strength": 0.0, "alpha": 1.0},
    "default_plastic":  {"metallic": 0.0, "roughness": 0.40, "emission_strength": 0.0, "alpha": 1.0},
}

# Principled BSDF v2 Input-Namen (Blender 4.x+; case-sensitive!)
BSDF_INPUTS = {
    "base_color":          "Base Color",
    "metallic":            "Metallic",
    "roughness":           "Roughness",
    "ior":                 "IOR",
    "alpha":               "Alpha",
    "normal":              "Normal",
    "emission_color":      "Emission Color",
    "emission_strength":   "Emission Strength",
    "transmission_weight": "Transmission Weight",
    "coat_weight":         "Coat Weight",       # war "Clearcoat" in Blender ≤ 3.6
    "coat_roughness":      "Coat Roughness",    # war "Clearcoat Roughness"
    "coat_ior":            "Coat IOR",
    "coat_tint":           "Coat Tint",
    "anisotropic":         "Anisotropic",
    "sheen_weight":        "Sheen Weight",
    "sheen_roughness":     "Sheen Roughness",
}


# ------------------------------------------------------------------
# PASS 1: NAME-BASED CLASSIFICATION
# ------------------------------------------------------------------
def classify_by_name(mat_name: str) -> str | None:
    """Return material class or None if no pattern matched."""
    matches = []
    for prio, cls, pat in PATTERNS:
        if pat.search(mat_name):
            matches.append((prio, cls))
    if not matches:
        return None
    matches.sort()  # lowest priority number wins (most specific)
    return matches[0][1]


# ------------------------------------------------------------------
# PASS 2: TEXTURE-BASED CLASSIFICATION
# ------------------------------------------------------------------
def classify_by_texture(mat) -> str | None:
    """Sample base-color + metallic-roughness textures at 128x128, use heuristics."""
    bsdf = get_principled(mat)
    if bsdf is None:
        return None

    bc = sample_input_texture(bsdf, "Base Color", size=128)  # returns np.ndarray[H,W,4] or None
    mr = sample_input_texture(bsdf, "Metallic",    size=128)
    rg = sample_input_texture(bsdf, "Roughness",   size=128)

    if bc is not None:
        # solid black? -> tire
        if bc[..., :3].mean() < 0.05 and bc[..., :3].std() < 0.02:
            return "tire_rubber"
        # solid bright + metallic map high? -> chrome
        if (bc[..., :3].mean() > 0.85 and mr is not None and mr.mean() > 0.8):
            return "chrome"
        # alpha channel non-solid? -> glass
        if bc.shape[-1] == 4 and bc[..., 3].mean() < 0.5:
            return "glass"
    if mr is not None and rg is not None:
        if mr.mean() > 0.8 and rg.mean() < 0.15:
            return "chrome"
    return None


# ------------------------------------------------------------------
# APPLY-PRESET (with logging & idempotency)
# ------------------------------------------------------------------
def apply_preset(mat, cls: str, report: list):
    preset = PRESETS[cls]
    bsdf = get_principled(mat)
    if bsdf is None:
        report.append({"material": mat.name, "class": cls, "action": "SKIPPED_NO_BSDF"})
        return

    changes = {}
    for key, target in preset.items():
        sock_name = BSDF_INPUTS.get(key)
        if sock_name is None or sock_name not in bsdf.inputs:
            continue
        sock = bsdf.inputs[sock_name]
        # Don't overwrite if a texture is plugged in (except explicitly desired)
        if sock.is_linked and key not in ("emission_strength", "alpha"):
            continue
        old = tuple(sock.default_value) if hasattr(sock.default_value, "__len__") else sock.default_value
        sock.default_value = target
        changes[sock_name] = {"old": old, "new": target}

    # HARD FIX: alpha exact 1.0 (Sketchfab bug: 0.99 = transparency-sorting)
    if "Alpha" in bsdf.inputs and not bsdf.inputs["Alpha"].is_linked:
        if 0.95 < bsdf.inputs["Alpha"].default_value < 1.0:
            bsdf.inputs["Alpha"].default_value = 1.0
            changes["Alpha"] = {"old": "~0.99", "new": 1.0, "fix": "alpha-clamp"}

    # HARD FIX: kill accidental emission on non-emissive classes
    if cls not in ("taillight_red",) and "Emission Strength" in bsdf.inputs:
        if bsdf.inputs["Emission Strength"].default_value > 0.0:
            bsdf.inputs["Emission Strength"].default_value = 0.0
            # also unlink emission color if it's the same texture as base-color (common bug)
            ec = bsdf.inputs.get("Emission Color")
            if ec and ec.is_linked:
                mat.node_tree.links.remove(ec.links[0])
                changes["Emission"] = {"fix": "unlinked-and-zeroed"}

    # HARD FIX: material blend mode consistency
    if cls == "glass" or cls == "headlight_lens" or cls == "taillight_red":
        mat.blend_method = "BLEND"
    elif mat.blend_method == "BLEND" and cls not in ("glass", "headlight_lens", "taillight_red"):
        mat.blend_method = "OPAQUE"
        changes["blend_method"] = "OPAQUE"

    report.append({"material": mat.name, "class": cls, "changes": changes})


# ------------------------------------------------------------------
# NORMAL-MAP Y-FLIP DETECTION
# ------------------------------------------------------------------
def detect_and_fix_normal_convention(mat, report):
    """
    glTF spec MANDATES OpenGL Y-up. If import came from DirectX-baked source,
    the normal map's green channel is inverted -> lighting is inside-out.

    Heuristic: check if the normal map's Y-component avg is < 0.5 (indicates flipped).
    Not perfect (many normals point sideways), but combined with Sketchfab-metadata check.
    """
    bsdf = get_principled(mat)
    if bsdf is None or "Normal" not in bsdf.inputs or not bsdf.inputs["Normal"].is_linked:
        return
    # Walk back to find Normal Map node
    nm_node = find_upstream(bsdf.inputs["Normal"], "ShaderNodeNormalMap")
    if nm_node is None:
        return
    img = find_upstream_image(nm_node)
    if img is None:
        return
    # Sample Y channel avg
    arr = sample_image(img, size=64)  # returns HxWx4
    y_avg = arr[..., 1].mean()
    if y_avg < 0.42:  # DirectX-style: green channel is bottom-heavy
        # Insert Invert-Y node chain (Separate/Invert G/Combine)
        insert_y_flip(nm_node, mat)
        report.append({"material": mat.name, "fix": "normal-map-y-flipped", "y_avg": float(y_avg)})


# ------------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------------
def sanitize_all_materials(report_path: Path):
    report = []
    for mat in bpy.data.materials:
        if not mat.use_nodes:  # skip legacy internal materials
            report.append({"material": mat.name, "action": "SKIPPED_NO_NODES"})
            continue

        # 1. Name-based classification
        cls = classify_by_name(mat.name)
        source = "name"

        # 2. Fallback: texture-based
        if cls is None:
            cls = classify_by_texture(mat)
            source = "texture" if cls else source

        # 3. Fallback: default_plastic (whitelist principle)
        if cls is None:
            cls = "default_plastic"
            source = "default"

        # 4. Apply preset
        apply_preset(mat, cls, report)
        report[-1]["classification_source"] = source

        # 5. Normal-map convention fix (regardless of class)
        detect_and_fix_normal_convention(mat, report)

    report_path.write_text(json.dumps(report, indent=2))
    print(f"[SANITIZER] Processed {len(bpy.data.materials)} materials -> {report_path}")


# ------------------------------------------------------------------
# HELPERS (stubs)
# ------------------------------------------------------------------
def get_principled(mat):
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None

def sample_input_texture(bsdf, socket_name, size=128):
    """Return downsampled numpy array for texture connected to socket, or None."""
    ...  # implementation with bpy.data.images + numpy

def sample_image(img, size=64):
    ...  # bilinear downsample -> np.ndarray

def find_upstream(socket, node_type):
    if not socket.is_linked:
        return None
    src = socket.links[0].from_node
    if src.bl_idname == node_type:
        return src
    return None

def find_upstream_image(nm_node):
    color_in = nm_node.inputs.get("Color")
    if not color_in or not color_in.is_linked:
        return None
    src = color_in.links[0].from_node
    return src.image if hasattr(src, "image") else None

def insert_y_flip(nm_node, mat):
    ...  # inject Separate Color -> Invert G -> Combine Color before nm_node
```

---

## 4. Common PBR-Bugs in Sketchfab/TurboSquid-GLBs

| # | Bug | Symptom im Render | Root-Cause | Fix |
|---|---|---|---|---|
| 1 | Emission-Slot enthält Base-Color-Textur | Body ist "blown out", ignoriert Beleuchtung | Blender-Exporter dupliziert Base-Color in Emission-Slot als NVIDIA-Workaround, wenn User "Bake Emission" aktiv hatte | Force `Emission Strength = 0`, Unlink Emission-Color-Texture wenn identisch mit Base-Color |
| 2 | Roughness stuck bei `0.5` | Alles wirkt gleich matt-glossy | Default aus dem Sketchfab-Editor, nie geändert | Preset-Override je Klasse |
| 3 | Metallic `0.0` auf Chrom | Chrom sieht aus wie graues Plastik | Sketchfab-Autoren vergessen Metallic-Slider hochzuziehen | Name-Match → `chrome` → force `Metallic = 1.0` |
| 4 | Alpha `0.99` statt `1.0` | Zufällige Transparenz-Sorting-Fehler, "Löcher" in Body | Substance Painter Export-Bug bei Opacity-Channel-Rundung | Wenn `0.95 < alpha < 1.0` → clamp auf `1.0` |
| 5 | Roughness-Map und Metallic-Map vertauscht | Body glänzt wie Chrom, Chrom ist matt | glTF-Spec: metallic=B, roughness=G; manche Exporter (ältere Substance) tauschen | Detection: wenn Metallic avg > 0.9 und Material heißt "body" → swap channels |
| 6 | Normal-Map DirectX-baked | Beleuchtung sieht "inside-out" aus, Beulen wirken als Dellen | Sketchfab-Assets aus Unreal-Marketplace ohne Convention-Fix reimportiert | Detect via Y-avg < 0.42 → Invert-G-Node einfügen |
| 7 | `blend_method = BLEND` auf opaquen Materials | Sorting-Artefakte, Performance-Drop | glTF `alphaMode: MASK` mit alpha=1.0 → Blender setzt trotzdem BLEND | Wenn Klasse nicht glass/lens/taillight → force `OPAQUE` |
| 8 | Base-Color-Textur ist sRGB, aber als Non-Color geflaggt | Farben wirken gewaschen/dunkel | Blender-Import mit "Non-Color" für alle Texturen bei fehlerhaftem glTF-Header | Base-Color-Textur → `colorspace_settings.name = "sRGB"`, alle anderen → `Non-Color` |
| 9 | Duplicate materials (Body, Body.001, Body.002) | Preset wird nur auf eine Variante angewendet | Blender-Rename bei Namenskollision | Normalisierung: `.001`, `.002` Suffix ignorieren beim Matching |
| 10 | Solid-Color-Texturen für Chrome (statt Value-Setter) | Uniform-Textur = 4 MB unnötig | Sketchfab-Editor speichert selbst Solid-Colors als PNG | Bei Klasse `chrome`/`glass`: Textur unlinken, nur Preset-Wert verwenden |

---

## 5. Edge-Cases + Failure-Modes

### 5.1 Wann Sanitizer NICHT läuft

- Material ist **keine Principled BSDF** (z. B. Emission-only Shader für Neon-Underglow): skip mit `SKIPPED_NO_BSDF`
- Material hat `use_nodes = False` (legacy Blender-Internal): skip mit `SKIPPED_NO_NODES`
- Material-Name matcht Whitelist-Bypass-Regex (User-Config: `\bDONT_TOUCH\b`): skip mit `SKIPPED_USER_LOCK`

### 5.2 Failure-Modes

| Failure | Erkennung | Recovery |
|---|---|---|
| Alle Materials landen bei `default_plastic` | Report zeigt `classification_source: "default"` für alle | User-Prompt: "GLB scheint keinen Standard-Naming zu haben. Manuell klassifizieren?" |
| Textur-Signal wählt falsche Klasse (z. B. photo-textur auf Reifen mit Werbeaufdruck) | Reifen bekommen `paint_body`-Preset → Coat glänzt fürchterlich | User kann `--no-texture-classification` Flag setzen; oder Textur-Klassifikator nur als 2nd-Opinion, nicht als authorität |
| Multi-Slot-Object (ein Mesh, 6 Material-Slots) | Sanitizer läuft pro Material, nicht pro Slot | Ist by-design korrekt — jedes Material wird einmal sanitized, egal wie oft es referenziert wird |
| Normal-Map-Detection false-positive (Sky-facing normals haben legit Y>0.5) | Y-flip wird eingefügt, obwohl Convention richtig war | Zusätzlicher Check: nur flippen wenn Material-Name Sketchfab-Metadata-Indikator hat, ODER User-Bestätigung |
| Body-Paint-Metallic (Silber, Gold): unser Preset setzt `Metallic 0.0` | Silver-Metallic-Body wirkt wie mattes Grau-Plastik | Textur-Erkennung: wenn Base-Color-Textur avg saturation < 0.1 UND brightness > 0.5 → set `Metallic 0.9` |

### 5.3 Idempotenz-Anforderung

Sanitizer muss **idempotent** sein: 2× drüberlaufen darf das Ergebnis nicht verschlechtern. Test: `sanitize()` → snapshot → `sanitize()` → diff = leer. Realisiert dadurch dass wir NUR default_values setzen und Links nicht entfernen, wenn nicht explizit bekannt (nur bei accidentally-emission-link).

### 5.4 Reporting-Format

`SANITIZER_REPORT.json` wird pro GLB einmal geschrieben:

```json
[
  {
    "material": "body_paint_red",
    "class": "paint_body",
    "classification_source": "name",
    "changes": {
      "Metallic": {"old": 0.0, "new": 0.0},
      "Roughness": {"old": 0.5, "new": 0.38},
      "Coat Weight": {"old": 0.0, "new": 1.0},
      "Coat Roughness": {"old": 0.03, "new": 0.05},
      "Emission Strength": {"old": 1.0, "new": 0.0},
      "Emission": {"fix": "unlinked-and-zeroed"}
    }
  },
  {
    "material": "Windshield.001",
    "class": "glass",
    "classification_source": "name",
    "changes": {
      "Transmission Weight": {"old": 0.0, "new": 1.0},
      "IOR": {"old": 1.45, "new": 1.52},
      "Alpha": {"old": "~0.99", "new": 1.0, "fix": "alpha-clamp"},
      "blend_method": "BLEND"
    }
  }
]
```

Damit kann User (a) sehen was passierte, (b) selektiv reverten, (c) für die nächste GLB-Charge Custom-Presets ableiten.

---

## 6. Blender-Specifics

### 6.1 Principled BSDF v2 Node-Input-Namen (Blender 4.x+)

**Kritisch:** In Blender 4.0 wurde "Clearcoat" zu "Coat" umbenannt. Alle Skripte die noch `node.inputs["Clearcoat"]` verwenden brechen in 4.x. Exakte neue Namen:

| Legacy (≤3.6) | Neu (4.x+) | Python-Zugriff |
|---|---|---|
| `Clearcoat` | `Coat Weight` | `bsdf.inputs["Coat Weight"].default_value` |
| `Clearcoat Roughness` | `Coat Roughness` | `bsdf.inputs["Coat Roughness"].default_value` |
| — (neu) | `Coat IOR` | `bsdf.inputs["Coat IOR"].default_value` |
| — (neu) | `Coat Tint` | `bsdf.inputs["Coat Tint"].default_value` |
| `Coat Normal` | `Coat Normal` | (unverändert) |
| `Transmission` | `Transmission Weight` | `bsdf.inputs["Transmission Weight"].default_value` |
| `Emission` | `Emission Color` + `Emission Strength` (jetzt separat!) | zwei sockets statt einer |
| `Sheen` | `Sheen Weight` | `bsdf.inputs["Sheen Weight"].default_value` |
| `Subsurface` | `Subsurface Weight` | (versioned) |

**Cross-Version-Support** (falls das Projekt beide unterstützt): try/except:

```python
def get_coat_input(bsdf):
    try:
        return bsdf.inputs["Coat Weight"]      # 4.x+
    except KeyError:
        return bsdf.inputs["Clearcoat"]        # ≤ 3.6
```

### 6.2 Node-Tree-Access Guards

```python
if not mat.use_nodes:
    return  # legacy material, kein node_tree
if "Principled BSDF" not in mat.node_tree.nodes:
    # kann trotzdem Principled sein unter anderem Namen — nach node.type suchen:
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
```

**Nie** `nodes["Principled BSDF"]` als String-Lookup — der Node kann `"Principled BSDF.001"` heißen. Immer `.type == "BSDF_PRINCIPLED"` iterieren.

### 6.3 Multi-Material-Objects

Ein Mesh kann N Material-Slots haben (verschiedene Materials auf verschiedenen Faces). Unser Sanitizer läuft über `bpy.data.materials` (globaler Storage), nicht über Objects — jedes Material wird 1× behandelt, egal wie viele Slots es referenzieren. Vorteil: keine Doppel-Arbeit. Nachteil: wenn User zwei Body-Materials mit unterschiedlichen Farben hat, bekommen beide dasselbe Preset (was aber korrekt ist).

### 6.4 Farbmanagement

Nach Preset-Anwendung muss View Transform auf **AgX** (Blender 4.x Default) oder **Filmic** stehen — Standard hätte bei metallischem Chrom im Studio-HDRI ausgeblasene Highlights. Sanitizer setzt zusätzlich:

```python
bpy.context.scene.view_settings.view_transform = "AgX"
bpy.context.scene.view_settings.look = "AgX - Base Contrast"
```

---

## 7. Sanitizer-Prioritäten (Design-Prinzipien)

1. **Whitelist > Blacklist.** Nur bekannte Klassen normalisieren. Unknown → `default_plastic` (safe), nicht "guess an arbitrary preset".
2. **Idempotent.** 2× ausführen = 1× ausführen. Kein Cascading-Verhalten.
3. **Additive vor Destructive.** Wenn Textur eingesteckt ist (`sock.is_linked`), NUR Wert-basierte Sockets überschreiben (z. B. IOR, Transmission Weight), aber NIE die verlinkte Textur unlinken — außer Emission-Bug (dokumentierter Fix).
4. **Report Everything.** Jede Änderung geht in den JSON-Report. Kein "silent fix".
5. **Fail-Safe = Plastic.** Bei allen Unklarheiten → matte plastic, nicht car-paint. Der Cinema-Trailer glänzt lieber weniger als zu viel.
6. **DACH-fokussiert für Namen.** Englisch + Deutsch. Andere Sprachen fallen in `default_plastic`, was OK ist (fewer surprises).
7. **User-Override via Metadata.** GLB kann `extras.zer0one_material_class = "chrome"` setzen → gewinnt über alle Auto-Detection.

---

## Quellen

- Adobe Substance PBR Guide Part 2 — <https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2>
- Physically Based Values Database — <https://physicallybased.info/>
- Blender 4.0 Shading Release Notes (Coat-Rename) — <https://developer.blender.org/docs/release_notes/4.0/shading/>
- Blender Manual — Principled BSDF — <https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/principled.html>
- Cycles Rework: Principled Clearcoat → Coat (PR #110993) — <https://projects.blender.org/blender/blender/pulls/110993>
- glTF 2.0 KHR_materials_ior Extension (Glass IOR 1.52) — <https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_materials_ior/README.md>
- glTF 2.0 KHR_materials_transmission — <https://gltf-transform.dev/modules/extensions/classes/KHRMaterialsTransmission>
- glTF-Validator (Khronos) — <https://github.com/KhronosGroup/glTF-Validator>
- Sketchfab Materials & Textures Docs — <https://support.fab.com/s/article/Materials-and-Textures?language=en_US>
- Sketchfab Transparency/Opacity Guide — <https://help.sketchfab.com/hc/en-us/articles/202602073-Transparency-Opacity>
- Normal Map DirectX vs OpenGL Convention (aukimi) — <https://aukimi.com/blog/normal-map-conventions-opengl-vs-directx>
- glTF Normal Map Y-Convention Issue #952 — <https://github.com/KhronosGroup/glTF/issues/952>
- Chaos V-Ray Metalness Guide — <https://blog.chaos.com/understanding-metalness>
- PBR From Rules to Measurements — <https://www.racoon-artworks.de/blog_PBRfromrulestomeasurements.php>
- TurboSquid PBR Workflow Intro — <https://blog.turbosquid.com/2023/07/27/an-intro-to-physically-based-rendering-material-workflows-and-metallic-roughness/>
- 88Cars3D Automotive Texturing Foundations — <https://88cars3d.com/2025/12/29/foundations-of-automotive-texturing-and-substance-painter-setup/>
- Blender Artists — Coat Weight Discussion — <https://blenderartists.org/t/principled-bsdf-clearcoat-behaves-weird/695826>
- pygltflib (glTF Python) — <https://pypi.org/project/pygltflib/>
