"""Read-only presentation bridge and real-engine demo-world factory.

The controller owns presentation camera state and invokes only the Simulation
Engine's existing start/stop/step API. Renderers receive detached SceneFrames.
"""

from src.gaia.agents.citizen import Citizen
from src.gaia.building import Building
from src.gaia.business import Business
from src.gaia.construction import BuildingDefinition, ConstructionProject
from src.gaia.core.simulation import Simulation
from src.gaia.agents.job import Job
from src.gaia.vehicle import Vehicle
from src.gaia.visualization import Camera, build_scene_frame, snapshot_simulation


def create_live_demo_simulation():
    """Build starting conditions through GAIA's real Simulation models."""
    simulation = Simulation()
    simulation.world.width = 40
    simulation.world.height = 24
    simulation.world.set_resource("food", 120)
    simulation.world.set_resource("water", 120)
    simulation.world.set_resource("wood", 90)
    simulation.world.set_resource("stone", 50)

    citizens = (
        Citizen("citizen-ada", "Ada", age=28, location=(6, 8)),
        Citizen("citizen-lee", "Lee", age=35, location=(10, 13)),
        Citizen("citizen-mira", "Mira", age=22, location=(21, 11)),
        Citizen("citizen-noor", "Noor", age=42, location=(31, 18)),
    )
    for citizen in citizens:
        simulation.add_citizen(citizen)

    homes = Building("homes", "homes", (2, 2), dimensions=(5, 4), construction_status="completed")
    market_site = Building("market", "market", (12, 3), dimensions=(6, 5), construction_status="completed")
    greenhouse = Building("greenhouse", "greenhouse", (23, 3), dimensions=(7, 7), construction_status="completed")
    for building in (homes, market_site, greenhouse):
        simulation.world.add_building(building)

    market = Business("town-market", "Town Market")
    simulation.add_business(market)
    market_site.set_associated_business(market)

    project = ConstructionProject(
        "clinic-project", simulation.world,
        BuildingDefinition("clinic", {"wood": 8, "stone": 5}),
        "clinic", (17, 12), dimensions=(5, 4), work_required=30,
    )
    project.set_worker_job(Job("clinic-builder", "Construction Worker"))
    start_result = project.start()
    if not start_result["success"]:
        raise RuntimeError(f"Could not start live demo construction: {start_result['reason']}")
    if not project.add_worker(citizens[2]):
        raise RuntimeError("Could not assign the live demo construction worker.")
    simulation.add_construction_project(project)

    handcart = Vehicle("handcart", "handcart", (10, 7), speed=1.5)
    wagon = Vehicle("wagon", "wagon", (34, 18), speed=1.0)
    simulation.world.transportation.add_vehicle(handcart)
    simulation.world.transportation.add_vehicle(wagon)
    for vehicle, destination in (
        (handcart, (17, 9)), (wagon, (27, 14)),
    ):
        result = simulation.world.transportation.assign_destination(vehicle, destination)
        if not result["success"]:
            raise RuntimeError(f"Could not route live demo vehicle: {result['reason']}")
    simulation.world.environment.temperature = 19.0
    simulation.world.environment.wind_speed = 2.0
    return simulation


class LiveVisualizationController:
    """Headless-testable live bridge; renderer sees only returned frames."""

    def __init__(self, simulation, camera=None, *, simulation_factory=None):
        if simulation is None or not hasattr(simulation, "step"):
            raise TypeError("A Simulation Engine instance is required.")
        if camera is not None and not isinstance(camera, Camera):
            raise TypeError("Camera must be a Camera instance or None.")
        self._simulation = simulation
        self._camera = camera
        self._simulation_factory = simulation_factory

    @property
    def camera(self):
        return self._camera

    @property
    def paused(self):
        return not bool(self._simulation.is_running)

    @property
    def simulation_tick(self):
        return self._simulation.tick

    def set_viewport(self, width, height):
        if self._camera is None:
            zoom = min(width / 28.0, height / 18.0)
            self._camera = Camera((0, 0), width, height, zoom)
        else:
            self._camera = Camera(
                self._camera.position, width, height, self._camera.zoom,
            )
        return self._camera

    def pan(self, dx, dy):
        self._require_camera()
        self._camera = self._camera.pan_by(dx, dy)
        return self._camera

    def zoom(self, factor):
        self._require_camera()
        self._camera = self._camera.zoom_by(factor)
        return self._camera

    def reset_camera(self):
        self._require_camera()
        width, height = self._camera.viewport_size
        zoom = min(width / 28.0, height / 18.0)
        self._camera = Camera((0, 0), width, height, zoom)
        return self._camera

    def fit_camera(self, bounds=None):
        self._require_camera()
        width, height = self._camera.viewport_size
        if bounds is None:
            bounds = (self._simulation.world.width, self._simulation.world.height)
        world_width, world_height = bounds
        zoom = min(width / world_width, height / world_height) * 0.92
        view_width, view_height = width / zoom, height / zoom
        position = (-(view_width - world_width) / 2,
                    -(view_height - world_height) / 2)
        self._camera = Camera(position, width, height, zoom)
        return self._camera

    def resume(self):
        self._simulation.start()

    def pause(self):
        self._simulation.stop()

    def current_frame(self):
        """Snapshot current engine state exactly once; never advances it."""
        self._require_camera()
        scene = snapshot_simulation(self._simulation)
        return build_scene_frame(scene, self._camera)

    def advance_frame(self):
        """Advance one tick if running, then create one detached frame."""
        if self._simulation.is_running:
            try:
                self._simulation.step()
            except Exception:
                self._simulation.stop()
                raise
        return self.current_frame()

    def step_once(self):
        """Advance exactly one tick and preserve the prior run/pause state."""
        was_running = bool(self._simulation.is_running)
        if not was_running:
            self._simulation.start()
        try:
            self._simulation.step()
        except Exception:
            if self._simulation.is_running:
                self._simulation.stop()
            raise
        finally:
            if not was_running and self._simulation.is_running:
                self._simulation.stop()
        return self.current_frame()

    def reset(self):
        """Replace the engine with a fresh configured world, remaining paused."""
        if self._simulation_factory is None:
            raise RuntimeError("Reset requires a simulation factory.")
        if self._simulation.is_running:
            self._simulation.stop()
        self._simulation = self._simulation_factory()
        return self.current_frame()

    def _require_camera(self):
        if self._camera is None:
            raise RuntimeError("Set the viewport before requesting a scene frame.")
