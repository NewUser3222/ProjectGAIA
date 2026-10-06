# Project GAIA

Project GAIA is a persistent multi-agent civilization simulation.

The goal is to create a digital world where AI-controlled citizens can:

- Develop individual identities
- Remember experiences
- Interact with other citizens
- Work and trade
- Form relationships
- Reproduce
- Age and die
- Build structures
- Respond to resource conditions
- Develop organizations and cultures
- Create multi-generational history

The civilization should emerge from the interaction of agents, resources, environment, and simulation rules rather than being directly scripted into a predetermined society.

## Core Architecture

Project GAIA maintains a strict separation between:

- Human Control
- Simulation Engine
- GAIA Governor
- Observer
- Citizen Agents
- Visualization

### How authorities and GAIA work together to preserve simulation fairness

Human control sets the rules and can start, stop, or otherwise direct the
simulation through its controls. The Simulation Engine is the technical
authority that applies those rules and owns simulation state. GAIA operates
below the engine as a read-only observer and reporter; it cannot override
engine behavior or directly change citizens, resources, buildings, businesses,
transportation, or environmental state. Citizens make decisions within the
rules applied by the engine. This keeps reports separate from enforcement and
allows authority structures to emerge within civilization rather than making
government or policing mandatory simulation systems.

GAIA does not control:

- Emergency shutdown
- Human controls
- The Observer
- Host operating system
- Simulation infrastructure

The Observer independently records and analyzes the civilization.

`GAIAObserver` is an independently invoked, read-only recorder. A caller may
pass it a simulation snapshot; the simulation does not own or depend on the
Observer. It preserves citizen history and tick-stamped memories, archived
citizen identities and family links, and immutable world snapshots. Plain
citizen history strings have no source tick, so the Observer records the tick
when it first sees them rather than assigning a historical event time. Archived
identities include an incarnation number so a later citizen reusing a removed
citizen's ID does not overwrite the earlier archive. The Simulation Engine
also exposes immutable event records for births it creates and lifecycle
transitions or deaths observed during a simulation step. These records preserve
the engine source tick separately from the Observer's observation tick; legacy
history strings without engine timing retain an unknown source tick. When given
Governor reports, the Observer tracks new, persistent, recurring, and resolved
findings and retains immutable report snapshots separately from the Governor's
stateless current-condition analysis. `ObserverReport.to_dict()` and
`ObserverReport.to_json()` provide detached, deterministic exports that callers
can persist without file I/O; the Observer has no persistence backend. Callers
control the optional flow: call `GAIAGovernor.observe()`, optionally pass its
report to `GAIAObserver.record_governor_report()`, then pass the return value of
`GAIAObserver.observe()` to the store or another export destination. The
Simulation Engine has no Observer dependency.

The optional `SQLiteHistoryStore` in `src/gaia/persistence.py` is a
caller-managed adapter that accepts an Observer report or its detached mapping
export. It stores the canonical report for round-trip retrieval and normalized
rows for citizen incarnations, historical events, world snapshots, Governor
reports, and findings. Each save is transactional and idempotent for the same
export. SQLite is downstream of observation: neither the Simulation Engine nor
the Governor or Observer imports the persistence module. The adapter can be
replaced later, and visualization remains a separate consumer of simulation or
stored history data.

The SQLite adapter uses schema version 1 and rejects unsupported versions,
unversioned non-empty databases, and incomplete version 1 schemas. Its file-backed
round-trip and transaction rollback behavior are covered using temporary files
inside the test workspace; tests remove those files after each run. Callers own
the persistence lifecycle and choose when to save each detached Observer export.

Persisted history also has a read-only, storage-neutral contract in
`src/gaia/history.py` (`HistoryReader`). Its SQLite implementation provides
detached, deterministically ordered snapshots, citizen incarnations, events,
Governor reports and findings, with simulation and tick filtering. Event queries
keep source tick and observation tick filters distinct. A future
visualizer can receive this interface without querying SQLite tables. Live
Simulation Engine state, an Observer's current report, and persisted historical
snapshots are separate views; this interface does not expose simulation control
or imply that a stored snapshot is the current live world. Visualization remains
an independent consumer, and SQLite can be replaced without changing simulation
or rendering concepts.

For a current live frame, `src/gaia/visualization.py` provides
`snapshot_simulation(simulation)`, which copies supported values into a frozen,
deterministically ordered `WorldScene` without exposing engine entities or
issuing actions. The flow is:

```text
Simulation Engine
        ↓
WorldScene
        ↓
Camera / Viewport
        ↓
Footprint + Visibility
        ↓
SceneFrame
        ↓
RenderPlan / 2D Renderer
        ↓
Live UI
```

The scene interprets existing simulation coordinates without changing their
values: `(x, y)` has the top-left origin, X increases rightward, and Y increases
downward. World dimensions are `(width, height)` with valid positions in the
half-open range `0 <= x < width`, `0 <= y < height`; coordinates may be
integers or floats.
The scene preserves out-of-bounds coordinates and projection marks them outside
without clamping. `project_position()` computes normalized coordinates and
optionally scales them linearly into a viewport. `Camera` holds a top-left
world-space viewport origin, viewport dimensions in screen units, and zoom in
screen units per world unit. Its world-to-screen and inverse transforms are
linear and deterministic. Panning and zoom changes return new camera values;
they never change scene or simulation coordinates.

Each positioned entity has a detached `Footprint`. Existing building and
construction `dimensions` values are used as width/height
when they are valid. The engine does not specify whether an entity location is
a center or corner; the visualization contract interprets building/construction
locations as the rectangle's top-left. Citizens, vehicles, and business markers
use a simple 1-by-1 visualization-only footprint centered on their location.
These defaults are presentation metadata, not physical simulation properties.
An associated business uses the center of its building as its marker location;
unassociated businesses remain unplaced. Invalid explicit dimensions produce
an invalid-footprint state instead of a fabricated size.

`build_scene_frame(scene, camera)` projects scene entities and records separate
viewport and world relations, plus unplaced/invalid states. It classifies
footprints as fully inside, partially intersecting,
or fully outside the half-open viewport and world bounds. Partial intersections
remain renderable; projected rectangles can extend past viewport edges without
clamping or removing out-of-view entities from the source `WorldScene`.
`SceneFrame` carries ticks, world/environment/population
metadata, camera state, resources, stable layer definitions, and detached
render records ordered by layer and screen position. A renderer draws
`frame.render_entities` and can inspect `frame.culled_entities` for diagnostics.
The renderer receives this frame rather than `Simulation`, so it cannot reach
decision logic or mutable engine entities through the presentation contract.

The scene includes environment, population, citizens, buildings, vehicles,
construction, business activity, and world resource totals. Business placement
is derived from its explicit building association; a business without an
associated building remains unplaced. Resources are global totals rather than
spatial deposits and are represented without coordinates. The live adapter has
no SQLite or Governor dependency and does not execute actions or control
citizens. Historical visualization continues to use `HistoryReader`; the same
renderer-neutral scene boundary can support 2.5D or 3D presentation later.

### First 2D renderer

The first visible renderer is a small Tk canvas adapter. Its data flow is:

```text
Simulation Engine
        ↓
Detached WorldScene
        ↓
Camera / Viewport
        ↓
Footprints / Visibility
        ↓
SceneFrame
        ↓
Deterministic Render Commands
        ↓
Tk Canvas / UI
```

`src/gaia/rendering.py` interprets only `SceneFrame` and emits immutable,
deterministically ordered render commands with already projected screen
rectangles. `TkCanvasRenderer` draws those commands on a canvas; the command
generation and drawing adapter are separable, so renderer interpretation can
be tested headlessly. The renderer receives no `Simulation`, mutable entity,
Governor, Observer, or history/storage reference. Render commands and camera
state are presentation data and cannot issue simulation actions.

The developer application supports both a detached synthetic renderer fixture
and a live world configured with actual Simulation Engine models. Launch the
real live demo with:

```powershell
.\.venv\Scripts\python.exe -m src.gaia.visualization_demo --live
```

The live starting world is assembled with `Simulation`, `Citizen`, `Building`,
`Business`, `ConstructionProject`, and `Vehicle` models; it is not a synthetic
`WorldScene`. Starting conditions include four citizens, three completed
buildings, an associated market, an active clinic project with an assigned
citizen worker, two routed vehicles, resources, and environment state.
Simulation rules determine subsequent state.

Each `Simulation.step()` has a deterministic order: advance world/market time,
environment and resource regeneration; move registered vehicles along valid
routes; clean up inactive workers and let businesses plan production; advance
living citizens through age, exposure and needs; evaluate and execute each
citizen's best currently available action in simulation list order; advance
accepted citizen movement intents in stable citizen-ID order; then run the
existing adjacent-citizen social interaction pass and record lifecycle events.
Work actions use the existing job, production, and payroll accounting.
World market observations are advanced once before citizen transactions.

Vehicle routes are straight lines: each registered operational vehicle moves
in stable vehicle-ID order by at most its configured speed in world units and
lands exactly at its destination on arrival. Vehicles without a valid route
remain still. Route endpoints are checked against the half-open world bounds.
The legacy explicit `travel()` operation remains immediate and clears a route.

Construction is now a citizen action. An assigned living, eligible worker sees
a `construct` option from the decision engine; the engine chooses it only when
it outranks that citizen's active needs and other available actions. The
existing `ActionExecutor` calls the project's `perform_work()` validation and
completion path, with a default contribution of 10 work units per selected
action. A deferred need or work action therefore defers construction. Projects
must be started successfully, which validates and consumes the required
materials once through `ConstructionCostSystem`. Completed, abandoned, planned,
unassigned, and ineligible projects do not contribute. The project tick guard
prevents duplicate work by one worker within a tick. Construction has no energy
cost because the current project model defines none; adding such a cost needs a
simulation rule and accounting change, not a renderer effect.

`DecisionEngine` also supports deterministic action providers and registered
executor handlers for future action types. Providers describe options from
citizen/world state; built-in action handlers for eating, gathering, purchases,
employment, and construction cannot be replaced, preserving their validation
and accounting. The engine executes only the selected option. Existing freeform
citizen goals do not yet define machine-readable conditions or actions, and
citizens do not yet have general movement destinations. No action provider
infers intent from arbitrary goal text or fabricates a destination.

Successful construction completion is recorded as an engine event at the
authoritative tick; citizen memories for work, purchases, gathering, and other
existing activities remain available to the Observer's read-only history pass.
Citizen movement uses `MovementIntent`, a frozen value containing a world-space
destination, reason, and optional stable target kind/ID. The intent contains no
live entity references and does not move its citizen. Call
`Simulation.request_movement()` to validate membership, life state, finite
coordinates, half-open world bounds, target identity/location, and positive
citizen speed. The Simulation stores accepted intent/status; citizens do not
write their own position through this API.

At the end of each running tick, the Simulation advances active citizen routes
in stable citizen-ID order. Citizens move directly toward the destination at
their existing age-based `speed`, in world units per tick. Movement does not
overshoot, and the final step snaps to the exact destination. Invalid or lost
targets, death, invalid speed/position, or a world-bound violation cancel the
route. Repeating the same request is idempotent; a different accepted request
cancels and replaces an active route. No random wandering, roads, or pathfinding
are involved.

Actions can declare a destination through their existing `ActionOption`
requirements. The Simulation accepts the movement intent and defers that action
while the citizen travels; the action is reconsidered after arrival on a later
tick. Construction actions target their active project site, so assigned
workers contribute only after reaching it. Work for a business associated with
an active building similarly waits for the building location. Employment at an
unassociated business remains abstract. Existing purchase/commerce transactions
also remain abstract because the market has no physical service-point contract.
Social interactions retain their current behavior; citizen movement can target
another citizen for future location-aware social rules.

The next live snapshot reflects authoritative citizen positions and includes
detached movement status/destination metadata. The renderer still only displays
the latest `WorldScene`/`SceneFrame`; it does not move citizens or manage routes.
Accepted, cancelled, and completed trips become Simulation Engine events with
meaningful endpoints, without recording intermediate coordinates each tick.
Observer can retain those events through the existing history export and SQLite
schema. Active routes are transient live state and are not restored from history;
the current persistence contract stores observed history, not resumable
Simulation instances, so no schema migration was added.

The live UI starts paused. **Run** asks the Simulation Engine to start and the
Tk timer requests exactly one `Simulation.step()` per 250 ms callback while
running (nominally four ticks per second, with no catch-up ticks). A callback
then snapshots once, builds one `SceneFrame`, and draws it. **Pause** stops
engine advancement; **Step** advances exactly one engine tick and leaves a
previously paused simulation paused; **Reset** creates a fresh configured
Simulation and preserves the camera. Simulation tick counts advance only in
`Simulation.step()`. Frame generation and drawing never advance time.
Dead citizens remain in detached population/state data retained by the engine,
but the live render plan omits them as active inhabitants. Removed vehicles and
other unregistered entities disappear from the next snapshot.

The UI uses the Python standard-library Tkinter canvas (available in the project
environment). Arrow keys or WASD pan, `+`/`-` zoom, `F` fits the world, and `0`
or `R` resets the camera. Camera position/zoom survive new live frames and
remain independent of entity coordinates. Resizing updates the viewport while
preserving the camera origin and zoom, unless fit mode is active.

For the original static renderer fixture, omit `--live`:

```powershell
.\.venv\Scripts\python.exe -m src.gaia.visualization_demo
```

The live bridge in `src/gaia/live_visualization.py` is the only presentation
component that knows about `Simulation`; it uses the engine's explicit
start/stop/step API and copies state through `snapshot_simulation()`. The
low-level renderer still receives only detached `SceneFrame` data. UI controls
express human requests, while the Simulation Engine remains the sole authority
that applies simulation rules. Neither render commands nor camera operations
can mutate the world. The synthetic fixture remains useful for isolated
renderer checks, and the same renderer-neutral frame contract can support later
2.5D/3D presentations.

Governor reports are deterministic snapshots derived from Simulation Engine
state. They summarize population, resources, environment, transportation,
construction and business conditions, and the engine's current and rolling
market observations. Findings describe detected conditions; they do not issue
commands or change simulation state. The Simulation Engine remains responsible
for validation, state transitions, and technical emergency controls.

## Development Philosophy

Project GAIA will be developed incrementally.

Initial development focuses on:

1. Development environment
2. Simulation core
3. One citizen
4. Five-to-ten citizens
5. Life cycle
6. Resources
7. Economy and society
8. GAIA
9. Observer
10. Visualization
11. Construction
12. Cities
13. Multi-generational civilization
14. 3D visualization

Existing libraries, frameworks, engines, and infrastructure should be reused whenever practical rather than unnecessarily recreated from scratch.

However, the core simulation rules, world state, safety boundaries, and experimental methodology remain under Project GAIA's control.

## Storage

Project GAIA is designed to operate from an external drive.

Primary project location:

`E:\ProjectGAIA`

Persistent simulation data should remain on the external drive whenever practical, including:

- World databases
- Agent memories
- Historical records
- Logs
- Snapshots
- Backups
- World assets
- Simulation state

## Current Status

Phase 0 — Development Environment

- [x] External project location created
- [x] Git installed
- [x] Git repository initialized
- [x] Python 3.13.5 installed
- [x] Python virtual environment created
- [x] VS Code configured
- [x] Project Python interpreter selected
- [ ] Initial Git commit
- [ ] Simulation core

## Long-Term Goal

Create a persistent artificial world where intelligent agents live, interact, build, reproduce, age, die, and leave behind a history that future generations inherit — while allowing a human observer to watch the civilization develop rather than dictating what it becomes.
