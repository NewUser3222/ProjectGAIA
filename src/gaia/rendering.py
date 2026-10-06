"""Renderer-facing command generation and a thin Tk canvas backend.

The command builder accepts only ``SceneFrame``. Tkinter is used as a small
standard-library window surface; no simulation types enter this module.
"""

from dataclasses import dataclass
import math

from src.gaia.visualization import SceneFrame, ScreenRect


@dataclass(frozen=True)
class DrawCommand:
    """One detached entity drawing instruction in deterministic layer order."""

    layer: int
    kind: str
    entity_id: str
    label: str
    state: str
    details: tuple
    shape: str
    style: str
    rectangle: ScreenRect


@dataclass(frozen=True)
class GridLine:
    """Projected world-grid line, in viewport screen coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class RenderPlan:
    """Headless, immutable drawing plan derived from one ``SceneFrame``."""

    viewport_size: tuple
    background_style: str
    world_rectangle: ScreenRect
    grid_lines: tuple
    commands: tuple
    overlay_text: str


def _grid_step(zoom):
    """Choose a stable 1/2/5 decade interval near 48 screen units."""
    raw = 48.0 / zoom
    if not math.isfinite(raw) or raw <= 0:
        raise ValueError("Camera zoom cannot produce a finite world grid.")
    power = 10.0 ** math.floor(math.log10(raw))
    ratio = raw / power
    factor = 1 if ratio <= 1 else 2 if ratio <= 2 else 5 if ratio <= 5 else 10
    return factor * power


def _grid_lines(frame):
    camera = frame.camera
    world_width, world_height = frame.world_bounds
    view_width, view_height = camera.world_view_size
    left = max(0.0, camera.position[0])
    top = max(0.0, camera.position[1])
    right = min(world_width, camera.position[0] + view_width)
    bottom = min(world_height, camera.position[1] + view_height)
    if right <= left or bottom <= top:
        return ()

    step = _grid_step(camera.zoom)
    lines = []
    x = math.ceil(left / step) * step
    while x < right:
        x1, y1 = camera.world_to_screen((x, top))
        x2, y2 = camera.world_to_screen((x, bottom))
        lines.append(GridLine(x1, y1, x2, y2))
        x += step
    y = math.ceil(top / step) * step
    while y < bottom:
        x1, y1 = camera.world_to_screen((left, y))
        x2, y2 = camera.world_to_screen((right, y))
        lines.append(GridLine(x1, y1, x2, y2))
        y += step
    return tuple(lines)


def build_render_plan(frame):
    """Translate visible ``SceneFrame`` records into deterministic commands."""
    if not isinstance(frame, SceneFrame):
        raise TypeError("A SceneFrame is required.")
    camera = frame.camera
    world_x, world_y = camera.world_to_screen((0, 0))
    world_rectangle = ScreenRect(
        world_x, world_y,
        frame.world_bounds[0] * camera.zoom,
        frame.world_bounds[1] * camera.zoom,
    )
    commands = []
    render_entities = frame.render_entities
    active_construction_buildings = {
        dict(entity.details).get("building_id")
        for entity in render_entities
        if entity.kind == "construction" and entity.state == "under_construction"
    }
    shapes = {
        "building": "rectangle",
        "construction": "rectangle",
        "business": "oval",
        "vehicle": "rectangle",
        "citizen": "oval",
    }
    for entity in render_entities:
        # The engine retains deceased citizens in its registry; keep that
        # detached status in the frame/population totals, but do not draw them
        # as active inhabitants of the live town.
        if entity.kind == "citizen" and entity.state == "dead":
            continue
        if entity.kind == "construction" and entity.state == "completed":
            continue
        if (
            entity.kind == "building"
            and entity.state == "under_construction"
            and entity.entity_id in active_construction_buildings
        ):
            continue
        if entity.screen_footprint is None:
            continue
        commands.append(DrawCommand(
            layer=entity.layer,
            kind=entity.kind,
            entity_id=entity.entity_id,
            label=entity.name,
            state=entity.state,
            details=entity.details,
            shape=shapes.get(entity.kind, "rectangle"),
            style=entity.kind,
            rectangle=entity.screen_footprint,
        ))
    env = dict(frame.environment)
    resources = "  ".join(
        f"{resource.name}: {resource.quantity}" for resource in frame.resources
    )
    overlay = (
        f"Tick {frame.simulation_tick}  |  Population "
        f"{frame.living_population}/{frame.population}  |  "
        f"Day {env.get('day', '—')}  |  "
        f"{env.get('season', '—')} / {env.get('weather', '—')}\n"
        f"Resources: {resources}\n"
        "Arrows/WASD pan · +/- zoom · F fit · 0 reset"
    )
    return RenderPlan(
        viewport_size=camera.viewport_size,
        background_style="world",
        world_rectangle=world_rectangle,
        grid_lines=_grid_lines(frame),
        commands=tuple(commands),
        overlay_text=overlay,
    )


class TkCanvasRenderer:
    """Thin drawing adapter for any Tk Canvas-compatible object.

    ``draw_frame`` only accepts detached renderer data. Injecting a canvas-like
    object also makes actual drawing calls testable without a display server.
    """

    _PALETTE = {
        "world": ("#17212b", "#17212b"),
        "building": ("#526575", "#d2dde6"),
        "construction": ("#765824", "#ffd166"),
        "business": ("#21a88e", "#d0fff5"),
        "vehicle": ("#397fb7", "#c7e5ff"),
        "citizen": ("#dbc27e", "#fff0be"),
    }

    def __init__(self, canvas, *, show_labels=True):
        self.canvas = canvas
        self.show_labels = bool(show_labels)

    def draw_frame(self, frame):
        plan = build_render_plan(frame)
        canvas = self.canvas
        canvas.delete("all")
        canvas.configure(background=self._PALETTE[plan.background_style][0])
        for line in plan.grid_lines:
            canvas.create_line(
                line.x1, line.y1, line.x2, line.y2,
                fill="#293743", width=1,
            )
        world = plan.world_rectangle
        canvas.create_rectangle(
            world.x, world.y, world.right, world.bottom,
            outline="#91a9bd", width=2, fill="",
        )
        for command in plan.commands:
            fill, outline = self._style(command)
            rect = command.rectangle
            draw = canvas.create_oval if command.shape == "oval" else canvas.create_rectangle
            options = {"fill": fill, "outline": outline, "width": 1}
            if command.kind == "construction" or command.state == "under_construction":
                options["dash"] = (5, 3)
            draw(rect.x, rect.y, rect.right, rect.bottom, **options)
            if command.kind == "construction":
                self._draw_construction_progress(command)
            if self.show_labels:
                canvas.create_text(
                    rect.x + 3, rect.y + 2,
                    text=command.label or command.entity_id,
                    anchor="nw", fill="#f2f5f7", font=("TkDefaultFont", 8),
                )
        canvas.create_text(
            10, 8, text=plan.overlay_text, anchor="nw",
            fill="#e6edf3", font=("TkDefaultFont", 9),
        )
        return plan

    def _style(self, command):
        if command.state == "under_construction":
            return self._PALETTE["construction"]
        fill, outline = self._PALETTE.get(command.style, self._PALETTE["building"])
        if command.state in {"dead", "destroyed", "disabled", "inactive", "abandoned"}:
            return "#4b5055", "#9da4aa"
        return fill, outline

    def _draw_construction_progress(self, command):
        details = dict(command.details)
        try:
            completed = float(details["work_completed"])
            required = float(details["work_required"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return
        if not math.isfinite(completed) or not math.isfinite(required) or required <= 0:
            return
        ratio = min(1.0, max(0.0, completed / required))
        rect = command.rectangle
        bar_height = min(4.0, rect.height)
        bar_width = rect.width * ratio
        if bar_width <= 0 or bar_height <= 0:
            return
        self.canvas.create_rectangle(
            rect.x, rect.bottom - bar_height,
            rect.x + bar_width, rect.bottom,
            fill="#ffd166", outline="",
        )
