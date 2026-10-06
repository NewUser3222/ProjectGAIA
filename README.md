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
when it first sees them rather than assigning a historical event time. When
given Governor reports, it tracks new, persistent, recurring, and resolved
findings and retains immutable report snapshots separately from the Governor's
stateless current-condition analysis. `ObserverReport.to_json()` produces
deterministic JSON text for caller-managed storage without performing file I/O.

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
