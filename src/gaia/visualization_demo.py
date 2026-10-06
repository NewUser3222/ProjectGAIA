"""Developer launcher for a detached synthetic GAIA town."""

from src.gaia.rendering import TkCanvasRenderer
from src.gaia.visualization import Camera, Footprint, VisualEntity, VisualResource, WorldScene, build_scene_frame


def _entity(entity_id, kind, name, position, size, *, anchor, state="active", details=()):
    footprint = (
        Footprint(position, size[0], size[1], anchor, "visualization_default")
        if position is not None else None
    )
    return VisualEntity(
        entity_id=entity_id,
        kind=kind,
        name=name,
        position=position,
        state=state,
        details=details,
        footprint=footprint,
        footprint_status="available" if footprint is not None else "unplaced",
    )


def build_demo_world_scene():
    """Return a static presentation fixture; this is not a live simulation."""
    entities = (
        _entity("citizen-ada", "citizen", "Ada", (5, 8), (0.8, 0.8), anchor="center", state="alive"),
        _entity("citizen-lee", "citizen", "Lee", (10, 13), (0.8, 0.8), anchor="center", state="alive"),
        _entity("citizen-mira", "citizen", "Mira", (22, 10), (0.8, 0.8), anchor="center", state="alive"),
        _entity("citizen-noor", "citizen", "Noor", (39.8, 22.8), (0.8, 0.8), anchor="center", state="alive"),
        _entity("home-1", "building", "Homes", (2, 2), (5, 4), anchor="top_left", details=(("condition", "good"),)),
        _entity("market-building", "building", "Market", (12, 3), (6, 5), anchor="top_left", details=(("condition", "good"), ("business_id", "market-1"))),
        _entity("greenhouse", "building", "Greenhouse", (23, 4), (7, 8), anchor="top_left", details=(("condition", "good"),)),
        _entity("large-storehouse", "building", "Storehouse", (27, 14), (11, 8), anchor="top_left", details=(("condition", "good"),)),
        _entity("market-1", "business", "Market Co-op", (15, 5.5), (1, 1), anchor="center", details=(("building_id", "market-building"),)),
        _entity("future-business", "business", "Unplaced venture", None, (1, 1), anchor="center", state="inactive"),
        _entity("cart-1", "vehicle", "Handcart", (10, 7), (0.9, 0.6), anchor="center", state="operational"),
        _entity("wagon-2", "vehicle", "Wagon", (34, 17), (1.4, 0.8), anchor="center", state="operational"),
        _entity("project-1", "construction", "Clinic", (19, 7), (5, 4), anchor="top_left", state="under_construction", details=(("work_completed", 42.0), ("work_required", 100.0))),
    )
    entities = tuple(sorted(entities, key=lambda item: (item.kind, item.entity_id)))
    return WorldScene(
        simulation_tick=0,
        world_tick=0,
        bounds=(40, 24),
        environment=(
            ("day", 1),
            ("precipitation", 0.0),
            ("season", "spring"),
            ("temperature", 19.0),
            ("weather", "clear"),
            ("wind_speed", 2.0),
        ),
        population=4,
        living_population=4,
        entities=entities,
        resources=(
            VisualResource("food", 64),
            VisualResource("water", 38),
            VisualResource("wood", 120),
        ),
    )


class VisualizationDemo:
    """Canvas demo; synthetic by default, or bridged to the live engine."""

    def __init__(self, *, live=False):
        import tkinter as tk
        from tkinter import ttk

        self.live_mode = bool(live)
        self.controller = None
        if self.live_mode:
            from src.gaia.live_visualization import (
                LiveVisualizationController, create_live_demo_simulation,
            )
            self.controller = LiveVisualizationController(
                create_live_demo_simulation(),
                simulation_factory=create_live_demo_simulation,
            )
        self.root = tk.Tk()
        self.root.title("Project GAIA — Live 2D Simulation" if live else "Project GAIA — 2D Visualization Demo")
        self.root.geometry("1100x760")
        self.scene = None if live else build_demo_world_scene()
        self.canvas = tk.Canvas(self.root, background="#17212b", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.renderer = TkCanvasRenderer(self.canvas, show_labels=True)
        self.camera = None
        self._fit_on_resize = False
        self._last_size = None
        self._timer_id = None
        self.status_text = tk.StringVar(value="Paused at tick 0" if live else "Synthetic renderer demo")
        if live:
            controls = ttk.Frame(self.root, padding=(8, 4))
            controls.pack(fill="x", side="bottom")
            ttk.Button(controls, text="Run", command=self._resume).pack(side="left")
            ttk.Button(controls, text="Pause", command=self._pause).pack(side="left", padx=(4, 0))
            ttk.Button(controls, text="Step", command=self._step_once).pack(side="left", padx=(4, 0))
            ttk.Button(controls, text="Reset", command=self._reset).pack(side="left", padx=(4, 12))
            ttk.Label(controls, textvariable=self.status_text).pack(side="left")
            self._timer_id = self.root.after(250, self._on_timer)
        self.canvas.bind("<Configure>", self._on_resize)
        self.root.bind("<KeyPress>", self._on_key)
        self.canvas.focus_set()

    def _initial_camera(self, width, height):
        zoom = min(width / 28.0, height / 18.0)
        return Camera((0, 0), width, height, zoom)

    def _fit_camera(self, width, height):
        if self.controller is not None:
            return self.controller.fit_camera()
        world_width, world_height = self.scene.bounds
        zoom = min(width / world_width, height / world_height) * 0.92
        view_width, view_height = width / zoom, height / zoom
        position = (-(view_width - world_width) / 2,
                    -(view_height - world_height) / 2)
        return Camera(position, width, height, zoom)

    def _on_resize(self, event):
        width, height = int(event.width), int(event.height)
        if width <= 20 or height <= 20 or self._last_size == (width, height):
            return
        self._last_size = (width, height)
        if self.controller is not None:
            self.camera = self.controller.set_viewport(width, height)
            if self._fit_on_resize:
                self.camera = self.controller.fit_camera()
        elif self.camera is None:
            self.camera = self._initial_camera(width, height)
        elif self._fit_on_resize:
            self.camera = self._fit_camera(width, height)
        else:
            self.camera = Camera(self.camera.position, width, height, self.camera.zoom)
        self._draw()

    def _draw(self):
        if self.controller is not None and self.controller.camera is not None:
            self.camera = self.controller.camera
            self.renderer.draw_frame(self.controller.current_frame())
        elif self.camera is not None:
            self.renderer.draw_frame(build_scene_frame(self.scene, self.camera))

    def _resume(self):
        try:
            self.controller.resume()
            self.status_text.set(f"Running from tick {self.controller.simulation_tick}")
        except Exception as exc:
            self.status_text.set(f"Could not start simulation: {exc}")

    def _pause(self):
        try:
            self.controller.pause()
            self.status_text.set(f"Paused at tick {self.controller.simulation_tick}")
        except Exception as exc:
            self.status_text.set(f"Could not pause simulation: {exc}")

    def _step_once(self):
        try:
            self.renderer.draw_frame(self.controller.step_once())
            self.camera = self.controller.camera
            status = "Running" if not self.controller.paused else "Paused"
            self.status_text.set(f"{status} at tick {self.controller.simulation_tick}")
        except Exception as exc:
            self.controller.pause()
            self.status_text.set(f"Step failed; simulation paused: {exc}")

    def _reset(self):
        try:
            self.renderer.draw_frame(self.controller.reset())
            self.camera = self.controller.camera
            self.status_text.set("Paused at tick 0")
        except Exception as exc:
            self.status_text.set(f"Reset failed: {exc}")

    def _on_timer(self):
        if self.controller is not None and not self.controller.paused:
            try:
                frame = self.controller.advance_frame()
                self.renderer.draw_frame(frame)
                self.camera = self.controller.camera
                self.status_text.set(f"Running · tick {frame.simulation_tick}")
            except Exception as exc:
                self.controller.pause()
                self.status_text.set(f"Simulation stopped after frame error: {exc}")
        self._timer_id = self.root.after(250, self._on_timer)

    def _on_key(self, event):
        camera = self.controller.camera if self.controller is not None else self.camera
        if camera is None:
            return
        key = event.keysym.lower()
        if key in {"left", "a", "right", "d", "up", "w", "down", "s"}:
            span_x, span_y = camera.world_view_size
            dx = -span_x * 0.08 if key in {"left", "a"} else span_x * 0.08 if key in {"right", "d"} else 0
            dy = -span_y * 0.08 if key in {"up", "w"} else span_y * 0.08 if key in {"down", "s"} else 0
            self.camera = self.controller.pan(dx, dy) if self.controller else camera.pan_by(dx, dy)
            self._fit_on_resize = False
        elif key in {"plus", "equal", "kp_add"}:
            self.camera = self.controller.zoom(1.2) if self.controller else camera.zoom_by(1.2)
            self._fit_on_resize = False
        elif key in {"minus", "underscore", "kp_subtract"}:
            self.camera = self.controller.zoom(1 / 1.2) if self.controller else camera.zoom_by(1 / 1.2)
            self._fit_on_resize = False
        elif key == "f":
            self.camera = self._fit_camera(*camera.viewport_size)
            self._fit_on_resize = True
        elif key in {"0", "r"}:
            self.camera = self.controller.reset_camera() if self.controller else self._initial_camera(*camera.viewport_size)
            self._fit_on_resize = False
        else:
            return
        self._draw()

    def run(self):
        self.root.mainloop()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Open the GAIA 2D visualization.")
    parser.add_argument(
        "--live", action="store_true",
        help="run the configured real Simulation Engine demo world",
    )
    arguments = parser.parse_args()
    try:
        VisualizationDemo(live=arguments.live).run()
    except ImportError as exc:
        raise SystemExit(f"Tkinter is required for the window demo: {exc}") from exc
    except Exception as exc:
        if exc.__class__.__name__ != "TclError":
            raise
        raise SystemExit(
            "Could not open the GAIA window. Run this command in a desktop session."
        ) from exc


if __name__ == "__main__":
    main()
