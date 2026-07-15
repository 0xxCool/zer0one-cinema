"""Wheel-detection: deterministic 6-stage pipeline for finding k wheels in a vehicle scene.

Implementation of `docs/research/wheel-detection-methods.md`. Every stage is a
pure function taking primitive types and returning primitive types; the top-level
`detect_wheels()` composes them. This structure lets us unit-test each stage
independently without a Blender runtime.

Pipeline (in strict order):

    Stage 1 — compute_vehicle_frame   (body PCA → forward / right / up axes)
    Stage 2 — find_candidates         (aspect-ratio + position filter)
    Stage 4 — cluster_candidates      (K-Means k=4, bit-deterministic)
    Stage 5 — validate_rectangle      (wheelbase × track-width check)
              validate_symmetry       (left-right mirror check)
    Stage 6 — label_wheels            (FL / FR / RL / RR from vehicle-frame coords)
              aggregate_wheel_meshes  (rotating rim+tire vs. static caliper+disc)

Stage 0 (naming-heuristic fast-path) and Stage 3 (per-candidate cylinder-fit
PCA) from the research doc are intentionally deferred — v0.1 uses the
geometric pipeline exclusively, with per-cluster radius estimated from the
Stage-2 candidate bboxes.

Determinism guarantees:
- All candidate lists are lexicographically sorted (4-decimal rounded)
  before K-Means, so `n_init=1, random_state=seed` produces identical labels.
- PCA eigenvector signs are canonicalized (first non-zero component ≥ 0).
- No RANSAC, no ML — pure sklearn K-Means + numpy PCA.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

from .bbox_utils import MeshLike, world_bbox_corners

# ==========================================================================
# Extended protocol — MeshLike + `name` + `world_verts` for PCA
# ==========================================================================


class NamedMeshLike(MeshLike, Protocol):
    """MeshLike extended with name (for reporting) and all-verts access (for PCA)."""

    @property
    def name(self) -> str: ...

    @property
    def world_verts(self) -> np.ndarray:
        """All vertices of this mesh in world space, shape (N, 3)."""
        ...


# ==========================================================================
# Data structures (all frozen dataclasses)
# ==========================================================================


WheelLabel = Literal["FL", "FR", "RL", "RR", "L", "R", "W0", "W1", "W2", "W3"]


@dataclass(frozen=True)
class VehicleFrame:
    """Vehicle's local coordinate frame, computed via body-vertex PCA."""

    center: tuple[float, float, float]
    forward_axis: tuple[float, float, float]  # unit vector, longest bbox dim
    right_axis: tuple[float, float, float]  # unit vector
    up_axis: tuple[float, float, float]  # unit vector


@dataclass(frozen=True)
class WheelCandidate:
    """A mesh that passed the Stage-2 aspect-ratio + position filter."""

    mesh: NamedMeshLike
    center_world: tuple[float, float, float]
    center_local: tuple[float, float, float]  # in vehicle-frame coords
    dims_local_sorted: tuple[float, float, float]  # (short, mid, long)


@dataclass(frozen=True)
class WheelGroup:
    """One detected wheel with its rotating and static sub-meshes."""

    meshes: tuple[NamedMeshLike, ...]  # rotating parts (rim + tire + hub-nuts)
    center: tuple[float, float, float]  # world-space center of rotation
    rolling_axis_vector: tuple[float, float, float]  # unit vector in world coords
    radius: float  # in metres
    label: str  # WheelLabel value
    static_meshes: tuple[NamedMeshLike, ...] = ()  # caliper + brake disc bracket


@dataclass(frozen=True)
class WheelDetectionResult:
    """Return of `detect_wheels()`."""

    wheels: tuple[WheelGroup, ...]
    frame: VehicleFrame
    source: Literal["geometric", "naming", "fallback"]
    confidence: float


class WheelDetectionError(ValueError):
    """Raised when no confident wheel detection is possible."""


# ==========================================================================
# Stage 1 — Vehicle frame from body-vertex PCA
# ==========================================================================


def _canonicalize_eigenvector(v: np.ndarray) -> np.ndarray:
    """Sign-canonicalize an eigenvector: first non-zero component must be positive."""
    idx = int(np.argmax(np.abs(v)))
    return v if v[idx] >= 0 else -v


def compute_vehicle_frame(all_verts: np.ndarray) -> VehicleFrame:
    """Determine vehicle's forward / right / up axes from all vehicle vertices.

    Assumes: vehicle is longer than wide (forward = longest bbox dim),
    and sits on a floor (up = shortest bbox dim). Cross-check builds a
    right-handed frame.
    """
    if all_verts.shape[0] < 4:
        raise WheelDetectionError(f"need >=4 verts for PCA, got {all_verts.shape[0]}")

    center = all_verts.mean(axis=0)
    centered = all_verts - center
    cov = np.cov(centered, rowvar=False)  # 3x3 symmetric
    eigvals, eigvecs = np.linalg.eigh(cov)  # ascending

    # eigvecs columns are eigenvectors; sort by descending eigenvalue
    order = np.argsort(eigvals)[::-1]  # [long, wide, tall]
    forward = _canonicalize_eigenvector(eigvecs[:, order[0]])
    right = _canonicalize_eigenvector(eigvecs[:, order[1]])
    up = _canonicalize_eigenvector(eigvecs[:, order[2]])

    # Enforce right-handed frame: if forward × right doesn't align with up, flip right
    if np.dot(np.cross(forward, right), up) < 0:
        right = -right

    return VehicleFrame(
        center=(float(center[0]), float(center[1]), float(center[2])),
        forward_axis=(float(forward[0]), float(forward[1]), float(forward[2])),
        right_axis=(float(right[0]), float(right[1]), float(right[2])),
        up_axis=(float(up[0]), float(up[1]), float(up[2])),
    )


# ==========================================================================
# Stage 2 — Geometric candidate filter
# ==========================================================================


def _project_to_frame(points: np.ndarray, frame: VehicleFrame) -> np.ndarray:
    """Convert world-space points (N, 3) to vehicle-frame coords."""
    r_matrix = np.array([frame.forward_axis, frame.right_axis, frame.up_axis])
    result: np.ndarray = (points - np.array(frame.center)) @ r_matrix.T
    return result


# Thresholds (from research/wheel-detection-methods.md §Stage 2)
_ASPECT_SHORT_MIN, _ASPECT_SHORT_MAX = 0.15, 0.60  # short-dim / long-dim
_ASPECT_DISC_MIN, _ASPECT_DISC_MAX = 0.80, 1.05  # mid-dim / long-dim (round disc)
# wheel-diameter (longest bbox dim) / vehicle-length. Small for cars (~0.15),
# larger for motorcycles (~0.30), even larger for monster-trucks (~0.45).
# Kept generous to survive candidate-filtering; stage 5 rectangle+symmetry is
# the real gate. Real vehicles rarely exceed 0.50 outside of stunt props.
_DIAM_FRAC_MIN, _DIAM_FRAC_MAX = 0.03, 0.50
_Y_FRAC_MAX = 0.45  # wheel must be in bottom 45% of vehicle bbox


def find_candidates(
    meshes: Sequence[NamedMeshLike],
    frame: VehicleFrame,
) -> list[WheelCandidate]:
    """Filter meshes to wheel-shape candidates via aspect ratios and position.

    Args:
        meshes: all meshes in the vehicle scene.
        frame: vehicle's PCA frame from `compute_vehicle_frame()`.

    Returns:
        List of `WheelCandidate` — meshes that look like wheels geometrically.
    """
    # Overall vehicle bbox in frame coords
    all_verts = np.concatenate([np.asarray(m.world_verts, dtype=np.float64) for m in meshes])
    local_verts = _project_to_frame(all_verts, frame)
    veh_min = local_verts.min(axis=0)
    veh_max = local_verts.max(axis=0)
    veh_len = float(veh_max[0] - veh_min[0])  # forward-axis extent
    veh_height = float(veh_max[2] - veh_min[2])
    if veh_len == 0 or veh_height == 0:
        return []

    candidates: list[WheelCandidate] = []
    for m in meshes:
        corners = world_bbox_corners(m)  # (8, 3) world
        corners_local = _project_to_frame(corners, frame)
        c_min = corners_local.min(axis=0)
        c_max = corners_local.max(axis=0)
        c_dims = c_max - c_min
        dims_sorted_arr = np.sort(c_dims)  # ascending: short, mid, long
        short = float(dims_sorted_arr[0])
        mid = float(dims_sorted_arr[1])
        longd = float(dims_sorted_arr[2])
        if longd == 0:
            continue

        aspect_short = short / longd
        aspect_disc = mid / longd
        # Use wheel-diameter (longest dim) directly, not 3D-diagonal, because
        # a wheel's diameter is what makes it "wheel-sized" relative to the car.
        diam_frac = longd / veh_len
        c_center_local = (c_min + c_max) / 2.0
        y_frac = (c_center_local[2] - veh_min[2]) / veh_height

        is_wheel_shape = (
            _ASPECT_SHORT_MIN <= aspect_short <= _ASPECT_SHORT_MAX
            and _ASPECT_DISC_MIN <= aspect_disc <= _ASPECT_DISC_MAX
            and _DIAM_FRAC_MIN <= diam_frac <= _DIAM_FRAC_MAX
            and y_frac <= _Y_FRAC_MAX
        )
        if not is_wheel_shape:
            continue

        # Convert local center back to world coords for storage
        c_center_world = (
            np.array(frame.center)
            + c_center_local[0] * np.array(frame.forward_axis)
            + c_center_local[1] * np.array(frame.right_axis)
            + c_center_local[2] * np.array(frame.up_axis)
        )
        candidates.append(
            WheelCandidate(
                mesh=m,
                center_world=(
                    float(c_center_world[0]),
                    float(c_center_world[1]),
                    float(c_center_world[2]),
                ),
                center_local=(
                    float(c_center_local[0]),
                    float(c_center_local[1]),
                    float(c_center_local[2]),
                ),
                dims_local_sorted=(short, mid, longd),
            )
        )
    return candidates


# ==========================================================================
# Stage 4 — K-Means clustering (bit-deterministic)
# ==========================================================================


def _sort_candidates_canonical(candidates: Sequence[WheelCandidate]) -> list[WheelCandidate]:
    """Lexicographic sort by (rounded) local-frame center — required for K-Means determinism."""
    return sorted(
        candidates,
        key=lambda c: (
            round(c.center_local[0], 4),
            round(c.center_local[1], 4),
            round(c.center_local[2], 4),
        ),
    )


def cluster_candidates(
    candidates: Sequence[WheelCandidate],
    k: int,
    seed: int = 0,
) -> list[int]:
    """Cluster candidates via K-Means with bit-deterministic guarantees.

    Prerequisites:
        - Candidates must be canonically sorted (see `_sort_candidates_canonical`).
        - `k` must be ≤ len(candidates).

    Returns:
        Per-candidate cluster label (0..k-1), same order as input.
    """
    from sklearn.cluster import KMeans  # local import to keep test-time footprint small

    if k > len(candidates):
        raise WheelDetectionError(f"k={k} exceeds candidate count {len(candidates)}")

    points = np.array([c.center_local for c in candidates], dtype=np.float64)
    km = KMeans(
        n_clusters=k,
        init="k-means++",
        n_init=1,
        random_state=seed,
        algorithm="lloyd",
    )
    labels: np.ndarray = km.fit_predict(points)
    return [int(x) for x in labels]


# ==========================================================================
# Stage 5 — Symmetry & rectangle validation
# ==========================================================================


def validate_rectangle(wheel_centers_local: np.ndarray, tol_rel: float = 0.10) -> bool:
    """Verify 4 wheel centers form a rectangle in the (forward, right) plane.

    A rectangle has 6 pairwise distances that form 3 pairs: 2 shortest edges
    (either wheelbase or track-width; equal), 2 next-shortest (the other; equal),
    and 2 longest (the diagonals; equal).
    """
    if wheel_centers_local.shape != (4, 3):
        return False
    xy = wheel_centers_local[:, :2]  # (forward, right) coords
    dists = []
    for i in range(4):
        for j in range(i + 1, 4):
            dists.append(float(np.linalg.norm(xy[i] - xy[j])))
    dists.sort()
    # dists[0..1] should be equal (short edge, e.g. track-width)
    # dists[2..3] should be equal (long edge, e.g. wheelbase)
    # dists[4..5] should be equal (diagonal)
    for a, b in ((0, 1), (2, 3), (4, 5)):
        if dists[b] == 0:
            return False
        if abs(dists[a] - dists[b]) > tol_rel * dists[b]:
            return False
    return True


def validate_symmetry(wheel_centers_local: np.ndarray, tol_rel: float = 0.10) -> bool:
    """Verify wheel centers are mirror-symmetric across the vehicle's mid-plane.

    Mid-plane = right-axis = 0 in vehicle frame. Every wheel at +right must
    have a mirror at -right within tolerance.
    """
    if wheel_centers_local.shape[0] < 2:
        return False
    right_coords = wheel_centers_local[:, 1]
    track_width = float(right_coords.max() - right_coords.min())
    if track_width == 0:
        return False
    tol_abs = tol_rel * track_width

    reflected = wheel_centers_local.copy()
    reflected[:, 1] *= -1

    matched = [False] * len(wheel_centers_local)
    for orig in wheel_centers_local:
        best_i = -1
        best_d = float("inf")
        for i, refl in enumerate(reflected):
            if matched[i]:
                continue
            d = float(np.linalg.norm(orig - refl))
            if d < best_d:
                best_d = d
                best_i = i
        if best_i == -1 or best_d > tol_abs:
            return False
        matched[best_i] = True
    return all(matched)


# ==========================================================================
# Stage 6 — FL/FR/RL/RR labeling + sub-mesh aggregation + caliper filter
# ==========================================================================


def label_wheels_flfr_rlrr(wheel_centers_local: np.ndarray) -> list[str]:
    """Label 4 wheels as FL / FR / RL / RR based on (forward, right) coords.

    Vehicle frame: forward = index 0 (positive = front), right = index 1
    (positive = right side of vehicle).

    Split point = median of each axis (robust to slight asymmetric offsets).
    """
    n = wheel_centers_local.shape[0]
    if n != 4:
        return [f"W{i}" for i in range(n)]

    med_forward = float(np.median(wheel_centers_local[:, 0]))
    med_right = float(np.median(wheel_centers_local[:, 1]))

    labels: list[str] = []
    for pt in wheel_centers_local:
        is_front = pt[0] > med_forward
        is_right = pt[1] > med_right
        if is_front and not is_right:
            labels.append("FL")
        elif is_front and is_right:
            labels.append("FR")
        elif not is_front and not is_right:
            labels.append("RL")
        else:
            labels.append("RR")
    return labels


_CALIPER_RADIAL_THRESHOLD = 0.20  # fraction of wheel-radius
_WHEEL_INFLATION_FACTOR = 1.10  # bbox distance ≤ 1.1 × radius counts as "near the wheel"


def aggregate_wheel_meshes(
    wheel_center_world: np.ndarray,
    wheel_radius: float,
    rolling_axis: np.ndarray,
    all_meshes: Iterable[NamedMeshLike],
) -> tuple[list[NamedMeshLike], list[NamedMeshLike]]:
    """Group meshes into rotating (rim + tire) and static (caliper + disc bracket).

    A mesh belongs to this wheel if its bbox-center is within 1.1 × radius
    from the wheel center. It rotates if its radial offset from the wheel's
    rolling axis is < 20% of the wheel radius (concentric); else it's static
    (caliper hangs to one side of the hub).

    Returns:
        (rotating, static) — two lists of meshes.
    """
    axis_norm = float(np.linalg.norm(rolling_axis))
    if axis_norm == 0:
        raise WheelDetectionError("rolling_axis must be non-zero")
    axis_unit = rolling_axis / axis_norm

    rotating: list[NamedMeshLike] = []
    static: list[NamedMeshLike] = []
    if wheel_radius <= 0:
        return rotating, static

    for m in all_meshes:
        corners = world_bbox_corners(m)
        m_center = corners.mean(axis=0)
        offset = m_center - wheel_center_world
        # Distance test: mesh must be near the wheel
        dist = float(np.linalg.norm(offset))
        if dist > _WHEEL_INFLATION_FACTOR * wheel_radius:
            continue
        # Radial component (perpendicular to rolling axis)
        axial_component = float(np.dot(offset, axis_unit))
        radial_vec = offset - axial_component * axis_unit
        radial_dist = float(np.linalg.norm(radial_vec))
        radial_frac = radial_dist / wheel_radius
        if radial_frac < _CALIPER_RADIAL_THRESHOLD:
            rotating.append(m)
        else:
            static.append(m)
    return rotating, static


# ==========================================================================
# Top-level pipeline
# ==========================================================================


def detect_wheels(
    meshes: Sequence[NamedMeshLike],
    k: int | None = None,
    seed: int = 0,
) -> WheelDetectionResult:
    """Detect wheel-groups in a vehicle scene deterministically.

    Runs the 6-stage pipeline: PCA-frame → candidate-filter → K-Means →
    symmetry-and-rectangle-validation → labeling → sub-mesh-aggregation.

    Args:
        meshes: all meshes in the vehicle scene (post ground_anchor).
        k: expected wheel count. None → auto-detect (4 if ≥4 candidates, 2 for motorcycle).
        seed: RNG seed for K-Means (must be int for bit-determinism).

    Returns:
        `WheelDetectionResult` with per-wheel groups + vehicle frame + confidence.

    Raises:
        WheelDetectionError: if no confident detection is possible.
    """
    if not meshes:
        raise WheelDetectionError("no meshes given")

    # ── Stage 1: Vehicle frame ──
    verts_arrays = [np.asarray(m.world_verts, dtype=np.float64) for m in meshes]
    all_verts = np.concatenate([v for v in verts_arrays if v.size > 0])
    if all_verts.size == 0:
        raise WheelDetectionError("no vertices in any mesh")
    frame = compute_vehicle_frame(all_verts)

    # ── Stage 2: Candidate filter ──
    candidates = find_candidates(meshes, frame)
    if not candidates:
        mesh_count = len(list(meshes))
        raise WheelDetectionError(
            f"no wheel-shape candidates found in {mesh_count} meshes. "
            f"Common cause: the GLB stores the whole vehicle as one or few "
            f"merged meshes instead of separate wheel objects. v0.1 requires "
            f"wheel-per-object structure; connected-components sub-mesh "
            f"splitting is a v0.2 feature (see docs/research/wheel-detection-methods.md §3)."
        )

    # Auto-detect k
    if k is None:
        n_cands = len(candidates)
        if n_cands >= 4:
            k = 4
        elif n_cands >= 2:
            k = 2
        else:
            raise WheelDetectionError(f"only {n_cands} candidate(s); need >= 2")

    # ── Stage 4: K-Means with canonical sort ──
    canonical = _sort_candidates_canonical(candidates)
    labels = cluster_candidates(canonical, k=k, seed=seed)

    # Group by cluster; compute per-cluster local center
    clusters: dict[int, list[WheelCandidate]] = {}
    for lbl, cand in zip(labels, canonical, strict=True):
        clusters.setdefault(lbl, []).append(cand)

    wheel_centers_local = np.array(
        [np.mean([c.center_local for c in clusters[i]], axis=0) for i in sorted(clusters)],
        dtype=np.float64,
    )
    wheel_centers_world = np.array(
        [np.mean([c.center_world for c in clusters[i]], axis=0) for i in sorted(clusters)],
        dtype=np.float64,
    )

    # ── Stage 5: Rectangle + symmetry validation (only for k == 4) ──
    if k == 4:
        if not validate_rectangle(wheel_centers_local):
            raise WheelDetectionError("wheel centers do not form a rectangle")
        if not validate_symmetry(wheel_centers_local):
            raise WheelDetectionError("wheel centers not left-right symmetric")

    # ── Stage 6: Label + aggregate + caliper filter ──
    wheel_labels = (
        label_wheels_flfr_rlrr(wheel_centers_local) if k == 4 else [f"W{i}" for i in range(k)]
    )
    # Rolling axis in world = vehicle's right-axis (wheels rotate around it)
    rolling_axis_world = np.array(frame.right_axis, dtype=np.float64)

    wheels: list[WheelGroup] = []
    for i in sorted(clusters):
        cluster_cands = clusters[i]
        # Radius = half of the longest cluster-candidate bbox dimension
        radius = float(max(c.dims_local_sorted[2] for c in cluster_cands)) / 2.0
        wc_world = wheel_centers_world[i]
        rotating, static = aggregate_wheel_meshes(
            wheel_center_world=wc_world,
            wheel_radius=radius,
            rolling_axis=rolling_axis_world,
            all_meshes=meshes,
        )
        wheels.append(
            WheelGroup(
                meshes=tuple(rotating),
                center=(float(wc_world[0]), float(wc_world[1]), float(wc_world[2])),
                rolling_axis_vector=(
                    float(rolling_axis_world[0]),
                    float(rolling_axis_world[1]),
                    float(rolling_axis_world[2]),
                ),
                radius=radius,
                label=wheel_labels[i],
                static_meshes=tuple(static),
            )
        )

    # Sort output by label for consistency (FL, FR, RL, RR)
    label_order = {"FL": 0, "FR": 1, "RL": 2, "RR": 3, "L": 0, "R": 1}
    wheels.sort(key=lambda w: label_order.get(w.label, 99))

    # Confidence: for a clean k=4 detection with symmetric + rectangular wheels,
    # 0.9. Downgrade when candidates outnumber wheels a lot (noise).
    confidence = 0.9 if k == 4 else 0.7

    return WheelDetectionResult(
        wheels=tuple(wheels),
        frame=frame,
        source="geometric",
        confidence=confidence,
    )
