# GLB Test Fixtures — zer0one-cinema v0.1

Test-Suite von Vehicle-GLBs für die Wheel-Detection- und Model-Prep-Pipeline.

## Wichtig: Nicht im Git

Die `.glb`-Dateien selbst sind in `.gitignore` ausgeschlossen (`tests/glb_fixtures/*.glb`).
Nur dieses README und `.gitkeep` werden committet.

## Setup: Fixtures lokal beschaffen

Alle Files sind reproduzierbar per Direct-Download-URL. Zum Bootstrap:

```bash
cd tests/glb_fixtures/
bash download_fixtures.sh   # (nicht vorhanden — Setup manuell mit URLs unten)
```

## Fixture-Manifest

| Datei | Fahrzeug-Typ | Quelle | Lizenz | Größe | Qualität |
|---|---|---|---|---|---|
| `khronos_toy_car.glb` | Spielzeugauto (High-Poly, PBR: Clearcoat, Transmission, Sheen) | [Khronos glTF-Sample-Assets/ToyCar](https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/ToyCar/glTF-Binary/ToyCar.glb) | **CC0 1.0** (Guido Odendahl, Eric Chadwick) | 5.2 MB | Hero-Test (PBR-Materials) |
| `khronos_car_concept.glb` | Konzept-Sportwagen (High-Poly, Material Variants) | [Khronos glTF-Sample-Assets/CarConcept](https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CarConcept/glTF-Binary/CarConcept.glb) | CC-BY 4.0 (Darmstadt Graphics Group + Khronos-Logo TM) | 12 MB | Hero-Test (komplexes Chassis) |
| `khronos_cesium_milk_truck.glb` | Milchtransporter (Truck, animiert) | [Khronos glTF-Sample-Assets/CesiumMilkTruck](https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CesiumMilkTruck/glTF-Binary/CesiumMilkTruck.glb) | CC-BY 4.0 mit Trademark-Limitations (Cesium-Logo) | 364 KB | Animations-Test |
| `kenney_sedan.glb` | Limousine (Low-Poly) | [Kenney Car Kit](https://kenney.nl/media/pages/assets/car-kit/1a312ec241-1775131960/kenney_car-kit.zip) → `Models/GLB format/sedan.glb` | **CC0** | 172 KB | Standard-Sanity |
| `kenney_suv.glb` | SUV (Low-Poly) | Kenney Car Kit → `suv.glb` | **CC0** | 204 KB | Standard-Sanity |
| `kenney_van.glb` | Van (Low-Poly) | Kenney Car Kit → `van.glb` | **CC0** | 172 KB | Standard-Sanity |
| `kenney_truck.glb` | Pickup-Truck (Low-Poly) | Kenney Car Kit → `truck.glb` | **CC0** | 176 KB | Standard-Sanity |
| `kenney_firetruck.glb` | Feuerwehrauto (Low-Poly, Multi-Node) | Kenney Car Kit → `firetruck.glb` | **CC0** | 228 KB | Multi-Node-Test |
| `kenney_tractor.glb` | Traktor (unterschiedliche Vorne/Hinten-Radgrößen) | Kenney Car Kit → `tractor.glb` | **CC0** | 172 KB | Wheel-Size-Variance |
| `kenney_race.glb` | Rennwagen (futuristisch, Low-Poly) | Kenney Car Kit → `race.glb` | **CC0** | 164 KB | Sportwagen-Test |
| `kenney_monster_truck.glb` | Monster-Truck (übergroße Räder) | [Kenney Toy Car Kit](https://kenney.nl/media/pages/assets/toy-car-kit/42e19cc426-1736346027/kenney_toy-car-kit.zip) → `Models/GLB format/vehicle-monster-truck.glb` | **CC0** | 120 KB | Extreme-Wheel-Size |
| `kenney_racecar_green.glb` | F1-Style Rennwagen (Low-Poly) | [Kenney Racing Kit](https://kenney.nl/media/pages/assets/racing-kit/933b8fd9fd-1677580949/kenney_racing-kit.zip) → `Models/GLTF format/raceCarGreen.glb` | **CC0** | 104 KB | Formula-Style-Test |

**Total: 12 Fixtures, 19 MB, alle mit `.glb`-Header validiert.**

## Diversitäts-Coverage

| Achse | Abdeckung |
|---|---|
| Fahrzeug-Klasse | Limousine, SUV, Van, Truck, Firetruck, Tractor, Race-Car (2), Monster-Truck, Milk-Truck, Concept-Car, Toy-Car |
| Poly-Count | Low-Poly (Kenney, ~5 kB–230 kB) und Mid/High-Poly (Khronos, 370 kB–12 MB) |
| Material-Komplexität | Simple PBR (Kenney) bis Clearcoat/Transmission/Sheen/Variants (Khronos ToyCar, CarConcept) |
| Rad-Konfiguration | Standard-4-Rad, unterschiedliche Vorne/Hinten (Tractor), übergroße Räder (Monster-Truck), F1-freistehende Räder (RacecarGreen) |
| Animationen | statisch (die meisten) + animiert (CesiumMilkTruck) |
| Nodes/Hierarchie | flach (die meisten Kenney) + multi-node (Firetruck, Milktruck, CarConcept) |
| Motorrad | **fehlt** — keine CC0-Motorrad-GLBs in einer der geprüften Quellen. Für v0.2 ggf. selbst modellieren oder OpenGameArt manuell durchforsten. |

## Lizenz-Notiz

- **Kenney-Assets sind CC0** (Public Domain), Attribution "Kenney" oder "www.kenney.nl" ist willkommen, aber nicht erforderlich.
- **Khronos ToyCar ist CC0** (Guido Odendahl, Eric Chadwick).
- **Khronos CarConcept und CesiumMilkTruck sind CC-BY 4.0** — kommerzielle Nutzung erlaubt, Attribution erforderlich. CesiumMilkTruck enthält zusätzlich das Cesium-Logo als Trademark. Für rein interne Test-Suite unbedenklich, bei Weitergabe/Publishing Attribution nicht vergessen.

## Quellen, die geprüft aber verworfen wurden

- **PolyHaven** — Vehicle-Kategorie leer (0 Results). Einziges vage passendes Asset: `covered_car` = Auto unter Plane (nicht sinnvoll für Wheel-Detection). Zudem nur als `.gltf` + externe Texturen, nicht als single-file `.glb`.
- **Sketchfab** — CC0-Cars vorhanden, aber Login-Wall für Downloads → nicht für Automation.
- **OpenGameArt** — enthält CC0-Vehicle-Sammlungen, jedoch heterogen (viele als `.blend`/`.obj`, keine direkten `.glb`). Für v0.2 als manueller Nachtrag denkbar.
- **BlendSwap** — Login-Wall.
- Kenney "Toy Car Kit" enthält zusätzlich `vehicle-suv.glb` und `vehicle-speedster.glb` (redundant zu Car-Kit-SUV bzw. Race-Car — daher nicht zusätzlich übernommen).

## Reproduktion

Alle Direct-Download-URLs oben getestet am **2026-07-15**. Falls Kenney seine Media-URLs mit neuen Hash-Präfixen versioniert, `https://kenney.nl/assets/<slug>` besuchen und den "Continue without donating"-Link neu extrahieren.
