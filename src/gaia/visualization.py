"""Detached renderer-neutral live scene and coordinate projection utilities.

The simulation's coordinates remain authoritative. This module only reads
live state and copies it into immutable values; it never advances or controls
the Simulation Engine. Persisted historical views remain in ``HistoryReader``.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class VisualEntity:
    """Minimum detached entity data needed by a renderer."""

    entity_id: str
    kind: str
    name: str
    position: tuple | None
    state: str
    details: tuple = ()
    footprint: "Footprint | None" = None
    footprint_status: str = "not_provided"

    @property
    def world_position(self):
        return self.position


@dataclass(frozen=True)
class VisualResource:
    """Aggregate world resource total (not a spatial resource deposit)."""

    name: str
    quantity: object
    position: tuple | None = None


@dataclass(frozen=True)
class WorldScene:
    """Immutable, renderer-neutral description of one current live world."""

    simulation_tick: int
    world_tick: int
    bounds: tuple
    environment: tuple
    population: int
    living_population: int
    entities: tuple
    resources: tuple


# Backward-compatible public name from the first visualization foundation.
VisualizationSnapshot = WorldScene


@dataclass(frozen=True)
class Projection:
    """Position mapped to normalized/world-viewport coordinates."""

    source_position: tuple
    normalized_position: tuple
    viewport_position: tuple | None
    inside_world: bool


@dataclass(frozen=True)
class Footprint:
    """World-space rectangle, detached from engine state.

    ``world_position`` is the entity's existing location interpreted according
    to ``anchor``. Buildings/construction use a top-left anchor; point-like
    entities use a center anchor. ``size_source`` distinguishes physical
    dimensions supplied by the simulation from a visualization-only marker
    default. Footprints contain no camera or screen-space values.
    """

    world_position: tuple
    width: float
    height: float
    anchor: str
    size_source: str

    def __post_init__(self):
        position = _position(self.world_position)
        if position is None:
            raise ValueError("Footprint position must contain two coordinates.")
        _coordinate_pair(position, "Footprint position")
        width = _positive_finite(self.width, "Footprint width")
        height = _positive_finite(self.height, "Footprint height")
        if not isinstance(self.anchor, str) or self.anchor not in {"top_left", "center"}:
            raise ValueError("Footprint anchor must be 'top_left' or 'center'.")
        if not isinstance(self.size_source, str) or self.size_source not in {"simulation", "visualization_default"}:
            raise ValueError("Invalid footprint size source.")
        object.__setattr__(self, "world_position", position)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)
        if not all(math.isfinite(value) for value in (
            position[0] - width if self.anchor == "top_left" else position[0] - width / 2,
            position[0] + width, position[1] - height if self.anchor == "top_left" else position[1] - height / 2,
            position[1] + height,
        )):
            raise ValueError("Footprint bounds must be finite.")

    @property
    def left(self):
        return self.world_position[0] - (self.width / 2 if self.anchor == "center" else 0)

    @property
    def top(self):
        return self.world_position[1] - (self.height / 2 if self.anchor == "center" else 0)

    @property
    def right(self):
        return self.left + self.width

    @property
    def bottom(self):
        return self.top + self.height


@dataclass(frozen=True)
class ScreenRect:
    """Projected rectangle in viewport screen units; coordinates may be negative."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self):
        object.__setattr__(self, "x", _finite_number(self.x, "Screen rectangle X"))
        object.__setattr__(self, "y", _finite_number(self.y, "Screen rectangle Y"))
        object.__setattr__(self, "width", _positive_finite(self.width, "Screen rectangle width"))
        object.__setattr__(self, "height", _positive_finite(self.height, "Screen rectangle height"))
        if not math.isfinite(self.x + self.width) or not math.isfinite(self.y + self.height):
            raise ValueError("Screen rectangle bounds must be finite.")

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height


@dataclass(frozen=True)
class Camera:
    """Top-left world-space viewport with a deterministic linear zoom.

    ``position`` is the world-space coordinate at screen (0, 0). Zoom is
    screen units per world unit, so viewport dimensions divided by zoom give
    the visible world span. Pan and zoom methods return new cameras.
    """

    position: tuple = (0.0, 0.0)
    viewport_width: float = 800.0
    viewport_height: float = 600.0
    zoom: float = 1.0

    def __post_init__(self):
        position = _coordinate_pair(self.position, "Camera position")
        width = _positive_finite(self.viewport_width, "Viewport width")
        height = _positive_finite(self.viewport_height, "Viewport height")
        zoom = _positive_finite(self.zoom, "Zoom")
        world_width, world_height = width / zoom, height / zoom
        if not all(math.isfinite(value) and value > 0 for value in (
            world_width, world_height,
        )) or not all(math.isfinite(value) for value in (
            position[0] + world_width, position[1] + world_height,
        )):
            raise ValueError("Camera visible world bounds must be finite and positive.")
        object.__setattr__(self, "position", position)
        object.__setattr__(self, "viewport_width", width)
        object.__setattr__(self, "viewport_height", height)
        object.__setattr__(self, "zoom", zoom)

    @property
    def viewport_size(self):
        return (self.viewport_width, self.viewport_height)

    @property
    def world_view_size(self):
        return (self.viewport_width / self.zoom, self.viewport_height / self.zoom)

    def world_to_screen(self, position):
        x, y = _coordinate_pair(position, "World position")
        projected = ((x - self.position[0]) * self.zoom,
                     (y - self.position[1]) * self.zoom)
        if not all(math.isfinite(value) for value in projected):
            raise ValueError("Projected screen position must be finite.")
        return projected

    def screen_to_world(self, position):
        x, y = _coordinate_pair(position, "Screen position")
        return _coordinate_pair(
            (self.position[0] + x / self.zoom,
             self.position[1] + y / self.zoom),
            "Projected world position",
        )

    def contains_world_position(self, position):
        x, y = _coordinate_pair(position, "World position")
        right = self.position[0] + self.viewport_width / self.zoom
        bottom = self.position[1] + self.viewport_height / self.zoom
        return self.position[0] <= x < right and self.position[1] <= y < bottom

    def contains_screen_position(self, position):
        x, y = _coordinate_pair(position, "Screen position")
        return 0 <= x < self.viewport_width and 0 <= y < self.viewport_height

    def project_footprint(self, footprint):
        if not isinstance(footprint, Footprint):
            raise TypeError("A Footprint is required.")
        x, y = self.world_to_screen((footprint.left, footprint.top))
        return ScreenRect(
            x, y, footprint.width * self.zoom, footprint.height * self.zoom,
        )

    def pan_by(self, dx, dy):
        dx = _finite_number(dx, "Horizontal pan")
        dy = _finite_number(dy, "Vertical pan")
        return Camera(
            (self.position[0] + dx, self.position[1] + dy),
            self.viewport_width, self.viewport_height, self.zoom,
        )

    def with_zoom(self, zoom):
        return Camera(self.position, self.viewport_width, self.viewport_height, zoom)

    def zoom_by(self, factor):
        factor = _positive_finite(factor, "Zoom factor")
        return self.with_zoom(self.zoom * factor)


@dataclass(frozen=True)
class RenderLayer:
    """Stable renderer ordering group."""

    order: int
    name: str


SCENE_LAYERS = (
    RenderLayer(0, "background"),
    RenderLayer(10, "construction"),
    RenderLayer(20, "buildings"),
    RenderLayer(30, "businesses"),
    RenderLayer(40, "vehicles"),
    RenderLayer(50, "citizens"),
    RenderLayer(60, "foreground"),
)
_ENTITY_LAYER = {
    "construction": 10,
    "building": 20,
    "business": 30,
    "vehicle": 40,
    "citizen": 50,
}


@dataclass(frozen=True)
class FrameEntity:
    """Detached entity state plus per-frame visibility and projection."""

    entity_id: str
    kind: str
    name: str
    position: tuple | None
    footprint: Footprint | None
    screen_position: tuple | None
    screen_footprint: ScreenRect | None
    state: str
    details: tuple
    layer: int
    visible: bool
    inside_world: bool
    world_relation: str
    viewport_relation: str
    visibility: str

    @property
    def world_position(self):
        return self.position


@dataclass(frozen=True)
class SceneFrame:
    """Immutable renderer input; it contains no Simulation or engine objects."""

    simulation_tick: int
    world_tick: int
    world_bounds: tuple
    environment: tuple
    population: int
    living_population: int
    resources: tuple
    camera: Camera
    layers: tuple
    entities: tuple

    @property
    def render_entities(self):
        """Visible entities in deterministic draw order."""
        return tuple(entity for entity in self.entities if entity.visible)

    @property
    def culled_entities(self):
        """Unplaced or off-viewport entities retained in the source scene."""
        return tuple(entity for entity in self.entities if not entity.visible)


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite integer or float.")
    return float(value)


def _coordinate_pair(value, label):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(f"{label} must contain two coordinates.")
    return (_finite_number(value[0], f"{label} X"),
            _finite_number(value[1], f"{label} Y"))


def _positive_finite(value, label):
    value = _finite_number(value, label)
    if value <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return value


def _rect_relation(rect, left, top, right, bottom):
    """Classify a positive-area rectangle against half-open bounds."""
    if rect.right <= left or rect.x >= right or rect.bottom <= top or rect.y >= bottom:
        return "outside"
    if rect.x >= left and rect.y >= top and rect.right <= right and rect.bottom <= bottom:
        return "inside"
    return "partial"


def _freeze(value):
    """Recursively detach containers used in the renderer-facing model."""
    if isinstance(value, dict):
        frozen = ((str(key), _freeze(item)) for key, item in value.items())
        return tuple(sorted(frozen, key=lambda pair: (pair[0], repr(pair[1]))))
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze(item) for item in value), key=repr))
    if value is None or isinstance(value, (str, bytes, bool, int, float)):
        return value
    # Never let an unsupported mutable engine value cross the read boundary.
    return None


def _position(value):
    """Copy a model location without imposing renderer transforms on it."""
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    return tuple(_freeze(item) for item in value)


def _make_footprint(position, dimensions=None, *, anchor, default=(1.0, 1.0)):
    """Return detached footprint plus status; defaults are presentation-only."""
    copied = _position(position)
    if copied is None:
        return None, "unplaced" if position is None else "invalid_position"
    source = "visualization_default"
    size = default
    if dimensions is not None:
        if not isinstance(dimensions, (tuple, list)) or len(dimensions) != 2:
            return None, "invalid_dimensions"
        try:
            size = tuple(_positive_finite(value, "Simulation dimension") for value in dimensions)
            source = "simulation"
        except ValueError:
            return None, "invalid_dimensions"
    try:
        return Footprint(copied, size[0], size[1], anchor, source), "available"
    except ValueError:
        return None, "invalid_dimensions" if source == "simulation" else "invalid_position"


def snapshot_simulation(simulation):
    """Copy current simulation/world state into a deterministic immutable scene."""
    if simulation is None or not hasattr(simulation, "world"):
        raise TypeError("A simulation with a world is required.")
    world = simulation.world
    citizens = tuple(getattr(simulation, "citizens", ()))
    buildings = tuple(getattr(world, "buildings", ()))
    entities = []

    for citizen in citizens:
        movement = (
            simulation.get_movement_state(citizen)
            if hasattr(simulation, "get_movement_state")
            else None
        )
        movement_intent = getattr(movement, "intent", None)
        citizen_position = _position(citizen.location)
        footprint, footprint_status = _make_footprint(
            citizen.location, anchor="center",
        )
        entities.append(VisualEntity(
            entity_id=str(citizen.citizen_id), kind="citizen",
            name=str(citizen.name), position=citizen_position,
            state=str(citizen.lifecycle_state),
            details=(
                ("age", _freeze(citizen.age)),
                ("health", _freeze(citizen.health)),
                ("life_stage", str(citizen.life_stage)),
                ("occupation", _freeze(citizen.occupation)),
                ("movement_status", getattr(movement, "status", "stationary")),
                ("movement_destination", _freeze(
                    movement_intent.destination if movement_intent is not None else None
                )),
                ("movement_reason", str(movement_intent.reason) if movement_intent is not None else None),
            ),
            footprint=footprint, footprint_status=footprint_status,
        ))

    # A business has no independent location. Its displayed position is
    # derived from the first stable-ID building that explicitly associates it.
    business_sites = {}
    for building in sorted(buildings, key=lambda item: str(item.building_id)):
        business = building.get_associated_business()
        if business is not None:
            business_sites.setdefault(str(business.business_id), building)

    for building in buildings:
        business = building.get_associated_business()
        building_position = _position(building.location)
        footprint, footprint_status = _make_footprint(
            building.location, building.dimensions, anchor="top_left",
        )
        entities.append(VisualEntity(
            entity_id=str(building.building_id), kind="building",
            name=str(building.building_type), position=building_position,
            state=str(building.construction_status),
            details=(
                ("condition", str(building.condition)),
                ("dimensions", _freeze(building.dimensions)),
                ("business_id", str(business.business_id) if business is not None else None),
            ),
            footprint=footprint, footprint_status=footprint_status,
        ))

    transportation = getattr(world, "transportation", None)
    vehicles = transportation.get_vehicles() if transportation is not None else ()
    for vehicle in vehicles:
        vehicle_position = _position(vehicle.location)
        footprint, footprint_status = _make_footprint(
            vehicle.location, anchor="center",
        )
        entities.append(VisualEntity(
            entity_id=str(vehicle.vehicle_id), kind="vehicle",
            name=str(vehicle.vehicle_type), position=vehicle_position,
            state=str(vehicle.operational_state),
            footprint=footprint, footprint_status=footprint_status,
        ))

    for project in tuple(getattr(simulation, "construction_projects", ())):
        project_position = _position(project.location)
        footprint, footprint_status = _make_footprint(
            project.location, project.dimensions, anchor="top_left",
        )
        entities.append(VisualEntity(
            entity_id=str(project.project_id), kind="construction",
            name=str(project.building_id), position=project_position,
            state=str(project.status),
            details=(
                ("building_id", str(project.building_id)),
                ("work_completed", _freeze(project.work_completed)),
                ("work_required", _freeze(project.work_required)),
            ),
            footprint=footprint, footprint_status=footprint_status,
        ))

    for business in tuple(getattr(simulation, "businesses", ())):
        site = business_sites.get(str(business.business_id))
        if site is None:
            business_position = None
        else:
            site_position = _position(site.location)
            site_footprint, _ = _make_footprint(
                site_position, site.dimensions, anchor="top_left",
            )
            business_position = (
                (site_footprint.left + site_footprint.width / 2,
                 site_footprint.top + site_footprint.height / 2)
                if site_footprint is not None else site_position
            )
        footprint, footprint_status = _make_footprint(
            business_position, anchor="center",
        )
        entities.append(VisualEntity(
            entity_id=str(business.business_id), kind="business",
            name=str(business.name),
            position=business_position,
            state="active" if business.is_active() else "inactive",
            details=(("building_id", str(site.building_id) if site is not None else None),),
            footprint=footprint, footprint_status=footprint_status,
        ))

    environment = world.environment.to_dict()
    return WorldScene(
        simulation_tick=simulation.tick,
        world_tick=world.current_tick,
        # World membership and valid locations use [0, width) x [0, height).
        bounds=_freeze((world.width, world.height)),
        environment=tuple(sorted((str(key), _freeze(value)) for key, value in environment.items())),
        population=len(citizens),
        living_population=sum(1 for citizen in citizens if citizen.is_alive()),
        entities=tuple(sorted(
            entities,
            key=lambda item: (
                item.kind, item.entity_id, item.name, item.position is None,
                repr(item.position), item.state, repr(item.details),
                item.footprint_status,
                (item.footprint.width, item.footprint.height,
                 item.footprint.anchor, item.footprint.size_source)
                if item.footprint is not None else (),
            ),
        )),
        resources=tuple(
            VisualResource(str(name), _freeze(amount))
            for name, amount in sorted(world.resources.items())
        ),
    )


def project_position(scene, position, viewport_size=None):
    """Project an authoritative world position without changing it.

    World coordinates are (x, y), with x increasing rightward and y
    downward from the top-left origin. Bounds are half-open: x in [0, width)
    and y in [0, height). Normalized coordinates divide by world dimensions.
    When supplied, viewport_size=(width, height) scales those normalized
    coordinates linearly; it does not add camera, zoom, or clipping behavior.
    Out-of-bounds coordinates are reported as outside and left unclamped.
    """
    if not isinstance(scene, WorldScene):
        raise TypeError("A WorldScene is required.")
    copied = _position(position)
    if copied is None:
        raise ValueError("Position must contain two numeric coordinates.")
    x, y = copied
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(value) for value in (x, y)):
        raise ValueError("Coordinates must be finite integers or floats.")
    width, height = scene.bounds
    if width <= 0 or height <= 0:
        raise ValueError("World dimensions must be positive.")
    normalized = (x / width, y / height)
    inside = 0 <= x < width and 0 <= y < height
    viewport = None
    if viewport_size is not None:
        if not isinstance(viewport_size, (tuple, list)) or len(viewport_size) != 2:
            raise ValueError("Viewport size must contain width and height.")
        view_width, view_height = viewport_size
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) or value <= 0
               for value in (view_width, view_height)):
            raise ValueError("Viewport dimensions must be positive finite numbers.")
        viewport = (normalized[0] * view_width, normalized[1] * view_height)
    return Projection(copied, normalized, viewport, inside)


def build_scene_frame(scene, camera):
    """Cull and project one detached ``WorldScene`` for a renderer.

    Viewport/world edges are half-open. Rectangles intersecting the viewport
    remain renderable, including partial intersections. Out-of-world entities
    can still be visible when the camera covers them; ``world_relation`` reports
    that independently. Unplaced/invalid and off-viewport entities remain in
    ``SceneFrame.culled_entities`` with explicit reasons and are never clamped.
    """
    if not isinstance(scene, WorldScene):
        raise TypeError("A WorldScene is required.")
    if not isinstance(camera, Camera):
        raise TypeError("A Camera is required.")
    if not isinstance(scene.bounds, (tuple, list)) or len(scene.bounds) != 2:
        raise ValueError("Scene bounds must contain width and height.")
    width = _positive_finite(scene.bounds[0], "World width")
    height = _positive_finite(scene.bounds[1], "World height")
    frame_entities = []

    for entity in scene.entities:
        position = _position(entity.position)
        footprint = entity.footprint
        screen_position = None
        screen_footprint = None
        inside_world = False
        visible = False
        world_relation = "unplaced"
        viewport_relation = "outside"
        if entity.position is None:
            visibility = {
                "invalid_position": "invalid_position",
                "invalid_dimensions": "invalid_footprint",
            }.get(entity.footprint_status, "unplaced")
        else:
            try:
                x, y = _coordinate_pair(entity.position, "Entity position")
            except ValueError:
                visibility = "invalid_position"
            else:
                if footprint is None:
                    visibility = {
                        "invalid_dimensions": "invalid_footprint",
                        "invalid_position": "invalid_position",
                        "unplaced": "unplaced",
                    }.get(entity.footprint_status, "no_footprint")
                elif not isinstance(footprint, Footprint) or footprint.world_position != (x, y):
                    visibility = "invalid_footprint"
                else:
                    screen_position = camera.world_to_screen((x, y))
                    screen_footprint = camera.project_footprint(footprint)
                    world_rect = ScreenRect(
                        footprint.left, footprint.top,
                        footprint.width, footprint.height,
                    )
                    world_relation = _rect_relation(world_rect, 0, 0, width, height)
                    inside_world = world_relation == "inside"
                    viewport_relation = _rect_relation(
                        screen_footprint, 0, 0,
                        camera.viewport_width, camera.viewport_height,
                    )
                    visible = viewport_relation != "outside"
                    visibility = {
                        "inside": "visible",
                        "partial": "partially_visible",
                        "outside": "outside_viewport",
                    }[viewport_relation]
        frame_entities.append(FrameEntity(
            entity_id=str(entity.entity_id),
            kind=str(entity.kind),
            name=str(entity.name),
            position=position,
            footprint=footprint if isinstance(footprint, Footprint) else None,
            screen_position=screen_position,
            screen_footprint=screen_footprint,
            state=str(entity.state),
            details=_freeze(entity.details),
            layer=_ENTITY_LAYER.get(entity.kind, 60),
            visible=visible,
            inside_world=inside_world,
            world_relation=world_relation,
            viewport_relation=viewport_relation,
            visibility=visibility,
        ))

    frame_entities.sort(key=lambda entity: (
        not entity.visible,
        entity.layer,
        entity.screen_footprint.y if entity.screen_footprint is not None else 0.0,
        entity.screen_footprint.x if entity.screen_footprint is not None else 0.0,
        entity.kind,
        entity.entity_id,
        entity.name,
        repr(entity.position),
        (entity.screen_footprint.width, entity.screen_footprint.height)
        if entity.screen_footprint is not None else (),
        entity.visibility,
        entity.footprint.size_source if entity.footprint is not None else "",
    ))
    return SceneFrame(
        simulation_tick=scene.simulation_tick,
        world_tick=scene.world_tick,
        world_bounds=(width, height),
        environment=_freeze(scene.environment),
        population=scene.population,
        living_population=scene.living_population,
        resources=tuple(
            VisualResource(
                str(resource.name), _freeze(resource.quantity),
                _position(resource.position),
            )
            for resource in scene.resources
        ),
        camera=camera,
        layers=SCENE_LAYERS,
        entities=tuple(frame_entities),
    )
