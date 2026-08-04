"""RoboCasa/MuJoCo backend: the decision layer bound to a real kitchen scene.

Execution is oracle by design (see README): primitives are realized by
setting simulator state — free-joint poses for objects, door joint angles
for fixtures — through the robosuite/RoboCasa API, followed by mj_forward.
No physics stepping, no motion planning.

Grading queries are answered FROM GEOMETRY, not from this class's own
bookkeeping wherever the sim can answer: fixture containment uses
robocasa's object_utils point-in-fixture math on the object's actual pose,
and door state reads the door joints. The env/grader cannot be lied to by
the action layer.
"""

from __future__ import annotations

import numpy as np

from .base import FIXTURES

# object name -> robocasa asset category
CATEGORIES = {
    "leftovers": "tupperware",
    "juice_bottle": "juice",
    "butter_dish": "butter_stick",
    "expired_milk": "milk",
}

# deterministic shelf slots (fractional x offsets within the fridge region)
SHELF_XS = (-0.3, 0.0, 0.3)


def _make_env_class():
    """Deferred import so this module can be imported without robocasa."""
    from robocasa.environments.kitchen.kitchen import FixtureType, Kitchen

    class LeftoversKitchen(Kitchen):
        """One fixed kitchen with a fridge, microwave, cabinet, and counter."""

        def __init__(self, object_regions, **kwargs):
            self._initial_regions = object_regions
            super().__init__(**kwargs)

        def _setup_kitchen_references(self):
            super()._setup_kitchen_references()
            self.fridge = self.register_fixture_ref("fridge", dict(id=FixtureType.FRIDGE))
            self.microwave = self.register_fixture_ref("microwave", dict(id=FixtureType.MICROWAVE))
            self.cabinet = self.register_fixture_ref(
                "cabinet", dict(id=FixtureType.CABINET_WITH_DOOR, ref=self.microwave)
            )
            self.counter = self.register_fixture_ref(
                "counter", dict(id=FixtureType.COUNTER, ref=self.microwave)
            )
            self.init_robot_base_ref = self.counter

        def get_ep_meta(self):
            meta = super().get_ep_meta()
            meta["lang"] = "put the leftovers away in the fridge"
            return meta

        def _get_obj_cfgs(self):
            cfgs = []
            n_fridge = 0
            for name, region in self._initial_regions.items():
                if region == "counter":
                    placement = dict(
                        fixture=self.counter,
                        sample_region_kwargs=dict(ref=self.microwave),
                        size=(0.50, 0.40),
                        pos=("ref", -1.0),
                    )
                elif region == "fridge_shelf":
                    placement = dict(
                        fixture=self.fridge,
                        sample_region_kwargs=dict(rack_index=-1),
                        size=(0.4, 0.2),
                        pos=(SHELF_XS[n_fridge], -1.0),
                        ensure_object_boundary_in_range=False,
                    )
                    n_fridge += 1
                elif region == "microwave_interior":
                    placement = dict(
                        fixture=self.microwave,
                        size=(0.05, 0.05),
                        ensure_object_boundary_in_range=False,
                    )
                else:
                    raise ValueError(region)
                cfgs.append(
                    dict(
                        name=name,
                        obj_groups=CATEGORIES[name],
                        graspable=True,
                        placement=placement,
                    )
                )
            return cfgs

    return LeftoversKitchen


class RoboCasaBackend:
    name = "robocasa"

    def __init__(self, layout_id: int = 1, style_id: int = 8,
                 cam_azimuth: float = 40.0, cam_distance: float = 3.6):
        self.layout_id = layout_id
        self.style_id = style_id
        self._cam_azimuth = cam_azimuth
        self._cam_distance = cam_distance
        self.env = None

    # ------------------------------------------------------------ lifecycle
    def reset(self, object_regions: dict[str, str], seed: int) -> None:
        cls = _make_env_class()
        self.env = cls(
            object_regions=object_regions,
            robots="PandaOmron",
            seed=seed,
            obj_registries=("objaverse", "lightwheel", "aigen"),
            layout_ids=[self.layout_id],
            style_ids=[self.style_id],
            has_renderer=False,
            has_offscreen_renderer=True,
            use_camera_obs=False,
            ignore_done=True,
        )
        self.env.reset()
        self._held: str | None = None
        self._trash: set[str] = set()
        # a spot guaranteed empty: 1.5 m above the fridge (nothing falls —
        # we never step physics, only mj_forward)
        f = self.env.fridge
        self._held_pos = np.array(f.pos) + np.array([0.0, 0.0, f.height + 1.5])
        self._shelf_slot = 0

    # ---------------------------------------------------------------- doors
    def _fixture(self, name: str):
        return getattr(self.env, name)

    def set_door(self, fixture: str, open_: bool) -> None:
        fix = self._fixture(fixture)
        if open_:
            fix.open_door(env=self.env, min=1.0, max=1.0)
        else:
            fix.close_door(env=self.env)
        self.env.sim.forward()

    def door_open(self, fixture: str) -> bool:
        fix = self._fixture(fixture)
        try:
            return bool(fix.is_open(env=self.env))
        except TypeError:
            return bool(fix.is_open(env=self.env, joint_names=fix.door_joint_names))

    # -------------------------------------------------------------- objects
    def _obj_pos(self, obj: str) -> np.ndarray:
        body = self.env.objects[obj].root_body
        return np.array(self.env.sim.data.get_body_xpos(body))

    def _teleport(self, obj: str, pos, quat=(0, 0, 0, 1.0)) -> None:
        joint = self.env.objects[obj].joints[0]
        self.env.sim.data.set_joint_qpos(
            joint, np.concatenate([np.asarray(pos, dtype=float), np.asarray(quat, dtype=float)])
        )
        self.env.sim.forward()

    def _region_pos(self, region: str) -> np.ndarray:
        env = self.env
        if region == "counter":
            # in front of the microwave on the counter surface
            mw = np.array(env.microwave.pos)
            c = env.counter
            top_z = np.array(c.pos)[2] + c.height / 2
            return np.array([mw[0], mw[1] - 0.45, top_z + 0.06])
        if region == "fridge_shelf":
            regions = env.fridge.get_reset_regions(env, reg_type="shelf")
            name, reg = sorted(regions.items())[0]
            offset = np.array(reg["offset"])
            pos = np.array(env.fridge.pos) + offset
            pos[0] += SHELF_XS[self._shelf_slot % len(SHELF_XS)]
            self._shelf_slot += 1
            pos[2] += 0.05
            return pos
        if region == "microwave_interior":
            mw = env.microwave
            return np.array(mw.pos) + np.array([0.0, 0.0, 0.03])
        raise ValueError(region)

    def move_object(self, obj: str, region: str) -> None:
        self._held = None if self._held == obj and region != "held" else self._held
        self._trash.discard(obj)
        if region == "held":
            self._held = obj
            self._teleport(obj, self._held_pos)
        elif region == "trash":
            # pseudo-bin: a fixed pose well outside the scene footprint
            self._trash.add(obj)
            self._teleport(obj, self._held_pos + np.array([0.0, 0.0, 1.0]))
        else:
            self._teleport(obj, self._region_pos(region))

    def object_region(self, obj: str) -> str:
        # held/trash are pseudo-regions owned by the oracle layer
        if obj == self._held:
            return "held"
        if obj in self._trash:
            return "trash"
        from robocasa.utils import object_utils as OU

        env = self.env
        pos = self._obj_pos(obj)
        if OU.point_in_fixture(pos, env.fridge, only_2d=False):
            return "fridge_shelf"
        if OU.point_in_fixture(pos, env.microwave, only_2d=False):
            return "microwave_interior"
        if OU.point_in_fixture(pos, env.cabinet, only_2d=False):
            return "cabinet_shelf"
        return "counter"

    def objects_in(self, region: str) -> list[str]:
        return sorted(o for o in self.env.objects if self.object_region(o) == region)

    # --------------------------------------------------------------- render
    def render(self):
        """Free-camera render framing the fridge/microwave/counter work area,
        through robosuite's own offscreen context (a fresh mujoco.Renderer
        context loses robosuite's uploaded textures; the robot-mounted cameras
        face wherever the base spawned)."""
        sim = self.env.sim
        if getattr(sim, "_render_context_offscreen", None) is None:
            sim.render(width=64, height=64, camera_name="robot0_agentview_center")
        cam = sim._render_context_offscreen.cam
        mid = (np.array(self.env.fridge.pos) + np.array(self.env.microwave.pos)) / 2
        cam.lookat[:] = [mid[0], mid[1], 1.1]
        cam.distance = self._cam_distance
        cam.azimuth = self._cam_azimuth
        cam.elevation = -18
        cam.fixedcamid = -1
        cam.type = 0  # mjCAMERA_FREE
        return sim.render(width=640, height=480)[::-1].copy()
