"""bpy-side adapters — the only file that imports bpy/bpy_extras/mathutils.

All Blender interaction (rendering, transform reads/writes, NDC projection)
funnels through this module. Unit tests substitute a MockAdapter with the
same surface so the loop, frame_analyzer, and fix_rules are testable
without a real Blender interpreter.

Convention for the .blend files preflight consumes (produced by
`zocinema model-prep`):
- Camera: named by the user via CLI `--camera <name>`.
- Car: a Blender Collection named "car" (recommended) OR any object whose
  name matches `car_object_name` — its combined bounding-box drives all
  frustum checks. If neither is found, we fall back to the "body" group
  produced by model-prep.
- Ground: a plane named "Ground" (default) or `--ground-name <name>`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
from PIL import Image

from .fix_rules import SceneState
from .frame_analyzer import BBoxNDC
from .report import SceneMutation


@dataclass(frozen=True)
class RenderOutcome:
    """Result of one EEVEE preview render."""

    frame_path: str
    frame_bgr: np.ndarray  # (H, W, 3) uint8, OpenCV convention
    render_seconds: float


class PreflightAdapter(Protocol):
    """The surface the preflight loop needs from Blender."""

    def render_eevee_preview(self, output_path: str) -> RenderOutcome: ...

    def snapshot_scene_state(self, camera_name: str) -> SceneState: ...

    def bbox_to_ndc(self, camera_name: str) -> BBoxNDC: ...

    def apply_mutation(self, mutation: SceneMutation, camera_name: str) -> None: ...


class BlenderAdapter:
    """Real-Blender implementation of the preflight surface.

    Constructed by `make_blender_adapter()`. All bpy access is deferred to
    the class methods so importing this module never triggers a bpy import.
    """

    def __init__(
        self,
        car_object_name: str = "car",
        ground_object_name: str = "Ground",
        eevee_samples: int = 16,
        resolution_percentage: int = 50,
    ) -> None:
        self.car_object_name = car_object_name
        self.ground_object_name = ground_object_name
        self.eevee_samples = eevee_samples
        self.resolution_percentage = resolution_percentage

    def _get_scene(self) -> Any:
        import bpy

        return bpy.context.scene

    def _get_object(self, name: str) -> Any:
        import bpy

        obj = bpy.data.objects.get(name)
        if obj is None:
            raise KeyError(f"object '{name}' not found in the current .blend")
        return obj

    def _get_car_bbox_world_corners(self) -> np.ndarray:
        """Combined world-space bbox corners across the car collection / object.

        Prefers a Blender Collection named `car_object_name`; falls back to a
        single object with that name, then to every mesh whose name starts
        with 'body' (model-prep body-group convention).
        """
        import bpy
        from mathutils import Vector

        collection = bpy.data.collections.get(self.car_object_name)
        meshes: list[Any] = []
        if collection is not None:
            meshes = [o for o in collection.objects if o.type == "MESH"]
        elif self.car_object_name in bpy.data.objects:
            obj = bpy.data.objects[self.car_object_name]
            if obj.type == "MESH":
                meshes = [obj]
        if not meshes:
            meshes = [
                o
                for o in bpy.data.objects
                if o.type == "MESH" and o.name.lower().startswith("body")
            ]
        if not meshes:
            raise KeyError(
                f"no car geometry: looked for collection '{self.car_object_name}', "
                f"object '{self.car_object_name}', or meshes named 'body*'"
            )
        all_corners = []
        for m in meshes:
            for corner in m.bound_box:
                world = m.matrix_world @ Vector(corner)
                all_corners.append([world.x, world.y, world.z])
        return np.asarray(all_corners, dtype=np.float64)

    def render_eevee_preview(self, output_path: str, camera_name: str | None = None) -> RenderOutcome:
        import bpy

        scene = self._get_scene()
        prev_engine = scene.render.engine
        prev_samples = getattr(scene.eevee, "taa_render_samples", None)
        prev_pct = scene.render.resolution_percentage
        prev_filepath = scene.render.filepath
        prev_camera = scene.camera
        try:
            # If the .blend has no active render camera, or a specific one was
            # requested, promote the named camera to active before rendering.
            if camera_name is not None:
                cam_obj = self._get_object(camera_name)
                scene.camera = cam_obj
            elif scene.camera is None:
                # Fallback: first CAMERA object in the scene
                cams = [o for o in bpy.data.objects if o.type == "CAMERA"]
                if cams:
                    scene.camera = cams[0]
            scene.render.engine = "BLENDER_EEVEE_NEXT"
            scene.eevee.taa_render_samples = self.eevee_samples
            scene.render.resolution_percentage = self.resolution_percentage
            scene.render.filepath = output_path
            t0 = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            render_seconds = time.perf_counter() - t0
        finally:
            scene.render.engine = prev_engine
            if prev_samples is not None:
                scene.eevee.taa_render_samples = prev_samples
            scene.render.resolution_percentage = prev_pct
            scene.render.filepath = prev_filepath
            scene.camera = prev_camera

        img = Image.open(output_path).convert("RGB")
        rgb = np.asarray(img, dtype=np.uint8)
        # OpenCV convention: BGR. Flip channel axis explicitly.
        bgr = rgb[:, :, ::-1].copy()
        return RenderOutcome(
            frame_path=output_path,
            frame_bgr=bgr,
            render_seconds=render_seconds,
        )

    def snapshot_scene_state(self, camera_name: str) -> SceneState:
        cam = self._get_object(camera_name)
        scene = self._get_scene()

        cam_fov_x = float(cam.data.angle_x)

        try:
            corners = self._get_car_bbox_world_corners()
            car_center = corners.mean(axis=0)
        except KeyError:
            car_center = np.zeros(3, dtype=np.float64)
        cam_loc = np.asarray(cam.location, dtype=np.float64)
        distance = float(np.linalg.norm(car_center - cam_loc))

        try:
            ground = self._get_object(self.ground_object_name)
            gscale: tuple[float, float, float] = (
                float(ground.scale[0]),
                float(ground.scale[1]),
                float(ground.scale[2]),
            )
        except KeyError:
            gscale = (1.0, 1.0, 1.0)

        exposure = float(getattr(scene.view_settings, "exposure", 0.0))
        dof = cam.data.dof if hasattr(cam.data, "dof") else None
        dof_focus_name = (
            dof.focus_object.name if dof is not None and dof.focus_object is not None else None
        )
        dof_fstop = float(dof.aperture_fstop) if dof is not None else 2.8

        return SceneState(
            cam_fov_x_rad=cam_fov_x,
            cam_to_car_distance_m=max(distance, 0.001),
            image_width=int(scene.render.resolution_x),
            image_height=int(scene.render.resolution_y),
            ground_current_scale=gscale,
            view_exposure_current=exposure,
            dof_focus_object_name=dof_focus_name,
            dof_fstop_current=dof_fstop,
        )

    def bbox_to_ndc(self, camera_name: str) -> BBoxNDC:
        import bpy_extras.object_utils as bpy_extras_ou
        from mathutils import Vector

        scene = self._get_scene()
        cam = self._get_object(camera_name)
        corners = self._get_car_bbox_world_corners()

        ndc_points = [
            bpy_extras_ou.world_to_camera_view(scene, cam, Vector(corner))
            for corner in corners
        ]
        xs = [float(p.x) for p in ndc_points]
        ys = [float(p.y) for p in ndc_points]
        zs = [float(p.z) for p in ndc_points]
        return BBoxNDC(
            x_min=min(xs),
            x_max=max(xs),
            y_min=min(ys),
            y_max=max(ys),
            z_min=min(zs),
            z_max=max(zs),
        )

    def apply_mutation(self, mutation: SceneMutation, camera_name: str) -> None:
        import bpy
        from mathutils import Vector

        cam = self._get_object(camera_name)
        scene = self._get_scene()

        if mutation.cam_delta_local is not None:
            local_delta = Vector(mutation.cam_delta_local)
            world_delta = cam.matrix_world.to_3x3() @ local_delta
            cam.location = cam.location + world_delta

        if mutation.cam_rotation_delta_z_rad is not None:
            cam.rotation_euler.z += mutation.cam_rotation_delta_z_rad

        if mutation.ground_scale_factor is not None:
            try:
                ground = self._get_object(self.ground_object_name)
                ground.scale = tuple(s * mutation.ground_scale_factor for s in ground.scale)
            except KeyError:
                pass  # no ground to scale — skip silently

        if mutation.dof_focus_car and hasattr(cam.data, "dof"):
            try:
                # Prefer collection→first mesh, else the car_object_name object
                collection = bpy.data.collections.get(self.car_object_name)
                if collection is not None and len(collection.objects) > 0:
                    cam.data.dof.focus_object = collection.objects[0]
                elif self.car_object_name in bpy.data.objects:
                    cam.data.dof.focus_object = bpy.data.objects[self.car_object_name]
            except AttributeError:
                pass

        if (
            mutation.dof_min_fstop is not None
            and hasattr(cam.data, "dof")
            and cam.data.dof.aperture_fstop < mutation.dof_min_fstop
        ):
            cam.data.dof.aperture_fstop = mutation.dof_min_fstop

        if mutation.view_exposure_delta is not None:
            scene.view_settings.exposure = (
                scene.view_settings.exposure + mutation.view_exposure_delta
            )


def make_blender_adapter(
    car_object_name: str = "car",
    ground_object_name: str = "Ground",
    eevee_samples: int = 16,
    resolution_percentage: int = 50,
) -> PreflightAdapter:
    """Construct the real Blender adapter with sensible defaults."""
    return BlenderAdapter(
        car_object_name=car_object_name,
        ground_object_name=ground_object_name,
        eevee_samples=eevee_samples,
        resolution_percentage=resolution_percentage,
    )
