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
