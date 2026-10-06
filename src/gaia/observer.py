"""Independent, read-only historical recording for Project GAIA."""

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from weakref import WeakKeyDictionary


@dataclass(frozen=True)
class HistoricalEvent:
    """One source history or memory entry preserved by the Observer."""

    event_id: str
    sequence: int
    event_type: str
    subject_id: str
    subject_name: str
    description: str
    source: str
    source_index: int
    event_tick: int | None
    observed_simulation_tick: int
    observed_world_tick: int
    related_citizen_ids: tuple
    subject_incarnation: int = 1


@dataclass(frozen=True)
class CitizenArchive:
    """Latest observed identity and family links, retained after death/removal."""

    citizen_id: str
    name: str
    age: int
    generation: int
    life_stage: str
    lifecycle_state: str
    parents: tuple
    children: tuple
    relationships: tuple
    first_observed_tick: int
    last_observed_tick: int
    incarnation: int = 1


@dataclass(frozen=True)
class ObserverReport:
    """Immutable historical view returned by one Observer recording pass."""

    simulation_tick: int
    world_tick: int
    events: tuple
    citizens: tuple
    finding_history: tuple = ()
    world_snapshots: tuple = ()
    governor_reports: tuple = ()

    def to_dict(self):
        """Return a detached JSON-compatible value for caller-managed storage."""
        payload = json.dumps(
            asdict(self),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return json.loads(payload)

    def to_json(self):
        """Return deterministic JSON text without performing file I/O."""
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


@dataclass(frozen=True)
class WorldSnapshot:
    """Immutable copy of supported authoritative world data at observation."""

    sequence: int
    simulation_tick: int
    world_tick: int
    resources: tuple
    environment: tuple
    buildings: tuple
    businesses: tuple
    construction_projects: tuple
    vehicles: tuple
    market_activity: tuple


@dataclass(frozen=True)
class FindingHistory:
    """Observer-maintained temporal record for one stable Governor finding."""

    finding_id: str
    category: str
    subject: str
    severity: str
    message: str
    evidence: tuple
    first_seen_tick: int
    last_seen_tick: int
    first_seen_world_tick: int
    last_seen_world_tick: int
    observations: int
    status: str


@dataclass(frozen=True)
class GovernorHistorySummary:
    """Finding transitions observed between two Governor report snapshots."""

    simulation_tick: int
    world_tick: int
    new: tuple
    persistent: tuple
    recurring: tuple
    resolved: tuple


@dataclass(frozen=True)
class GovernorReportSnapshot:
    """Immutable health-report values retained for later historical analysis."""

    sequence: int
    simulation_tick: int
    world_tick: int
    population: int
    living_population: int
    births: int
    deaths: int
    resources: tuple
    building_count: int
    business_count: int
    vehicle_count: int
    construction_project_count: int
    construction_statuses: tuple
    environment: tuple
    market_activity: tuple
    completed_market_ticks: int
    findings: tuple


class GAIAObserver:
    """Record source histories without controlling or mutating a simulation."""

    HISTORY_EVENT_TYPES = {
        "Citizen created.": "citizen_created",
        "Citizen was born.": "birth",
        "Citizen died.": "death",
    }

    def __init__(self):
        self._events = []
        self._event_keys = set()
        self._citizens = {}
        self._citizen_first_seen = {}
        self._citizen_instances = WeakKeyDictionary()
        self._next_citizen_incarnation = {}
        self._finding_history = {}
        self._active_finding_ids = set()
        self._world_snapshots = []
        self._governor_reports = []

    def observe(self, simulation):
        """Append newly observed source entries and return an immutable report."""
        if simulation is None or not hasattr(simulation, "world"):
            raise TypeError("A simulation with a world is required.")

        world = simulation.world
        tick = simulation.tick
        world_tick = world.current_tick
        known_history_events = {}
        known_lifecycle_transitions = set()
        engine_records = getattr(simulation, "event_records", ())
        if not isinstance(engine_records, (tuple, list)):
            engine_records = ()
        for record in tuple(engine_records):
            identity = (
                str(getattr(record, "subject_id", "")),
                getattr(record, "subject_incarnation", 0),
            )
            event_type = getattr(record, "event_type", "")
            description = getattr(record, "description", "")
            sequence = getattr(record, "sequence", None)
            if (
                not identity[0]
                or not isinstance(identity[1], int)
                or isinstance(identity[1], bool)
                or identity[1] < 1
                or not isinstance(sequence, int)
                or isinstance(sequence, bool)
                or sequence < 0
                or not isinstance(event_type, str)
                or not event_type
                or not isinstance(description, str)
                or not description
            ):
                continue
            event_key = (identity, "simulation_engine", sequence)
            is_new_engine_event = event_key not in self._event_keys
            self._record_engine_event(record, tick, world_tick, identity)
            if event_type in {"birth", "death"}:
                signature = (identity, event_type, description)
                known_history_events[signature] = known_history_events.get(signature, 0) + 1
            elif event_type == "life_stage_transition" and is_new_engine_event:
                known_lifecycle_transitions.add((identity, description))

        for citizen in tuple(simulation.citizens):
            identity = self._identity_for(citizen, simulation)
            self._archive_citizen(
                citizen, tick, world_tick, identity, known_lifecycle_transitions
            )
            related = self._related_citizen_ids(citizen)
            history = getattr(citizen, "history", ())
            if not isinstance(history, (tuple, list)):
                history = ()
            memories = getattr(citizen, "memories", ())
            if not isinstance(memories, (tuple, list)):
                memories = ()
            for index, text in enumerate(tuple(history)):
                if not isinstance(text, str) or not text:
                    continue
                event_type = self.HISTORY_EVENT_TYPES.get(text, "citizen_history")
                signature = (identity, event_type, text)
                if known_history_events.get(signature, 0):
                    known_history_events[signature] -= 1
                    continue
                self._record(
                    citizen, "history", index, text,
                    event_type,
                    None, tick, world_tick, related, identity,
                )
            for index, memory in enumerate(tuple(memories)):
                if not isinstance(memory, dict):
                    continue
                text = memory.get("event")
                source_tick = memory.get("tick")
                if not isinstance(text, str) or not text:
                    continue
                if (
                    not isinstance(source_tick, int)
                    or isinstance(source_tick, bool)
                    or source_tick < 0
                ):
                    source_tick = None
                self._record(
                    citizen, "memory", index, text, "citizen_memory",
                    source_tick, tick, world_tick, related, identity,
                )

        self._world_snapshots.append(self._snapshot(simulation))

        return ObserverReport(
            simulation_tick=tick,
            world_tick=world_tick,
            events=tuple(self._events),
            citizens=tuple(self._citizens[key] for key in sorted(self._citizens)),
            finding_history=tuple(
                self._finding_history[key]
                for key in sorted(self._finding_history)
            ),
            world_snapshots=tuple(self._world_snapshots),
            governor_reports=tuple(self._governor_reports),
        )

    def _snapshot(self, simulation):
        world = simulation.world
        market = world.market_observations.to_dict()
        market_rows = tuple(
            (
                resource,
                activity,
                _freeze(market["current"][activity].get(resource, 0.0)),
                _freeze(market["recent"].get(resource, {}).get(activity, 0.0)),
            )
            for resource in sorted(
                set(market["recent"]) | {
                    resource
                    for totals in market["current"].values()
                    for resource in totals
                }
            )
            for activity in world.market_observations.ACTIVITY_TYPES
        )
        buildings = tuple(sorted((
            str(item.building_id),
            str(item.building_type),
            _freeze(item.location),
            _freeze(item.condition),
            _freeze(item.construction_status),
            _freeze(item.dimensions),
            _entity_id(item.owner),
            _entity_id(item.associated_business),
            tuple(sorted(str(c.citizen_id) for c in item.occupants)),
        ) for item in world.buildings))
        businesses = tuple(sorted((
            str(item.business_id),
            str(item.name),
            bool(item.is_active()),
            _freeze(item.get_money()),
            tuple(sorted((str(key), _freeze(value)) for key, value in item.inventory.items())),
            tuple(sorted(str(owner.citizen_id) for owner in item.owners)),
            tuple(sorted(str(employee.citizen_id) for employee in item.get_employees())),
        ) for item in simulation.businesses))
        projects = tuple(sorted((
            str(item.project_id),
            str(item.building_id),
            _freeze(item.status),
            _freeze(item.work_completed),
            _freeze(item.work_required),
        ) for item in simulation.get_construction_projects()))
        vehicles = tuple(sorted((
            str(item.vehicle_id),
            str(item.vehicle_type),
            _freeze(item.location),
            _freeze(item.operational_state),
            _entity_id(item.owner),
        ) for item in world.transportation.get_vehicles()))
        return WorldSnapshot(
            sequence=len(self._world_snapshots),
            simulation_tick=simulation.tick,
            world_tick=world.current_tick,
            resources=tuple(sorted(
                (str(key), _freeze(value))
                for key, value in world.resources.items()
            )),
            environment=tuple(sorted(
                (str(key), _freeze(value))
                for key, value in world.environment.to_dict().items()
            )),
            buildings=buildings,
            businesses=businesses,
            construction_projects=projects,
            vehicles=vehicles,
            market_activity=market_rows,
        )

    def record_governor_report(self, report):
        """Track finding transitions without changing simulation or report data."""
        if report is None or not hasattr(report, "findings"):
            raise TypeError("A Governor report with findings is required.")
        simulation_tick = getattr(report, "tick", 0)
        world_tick = getattr(report, "world_tick", 0)
        self._governor_reports.append(self._snapshot_governor_report(report))
        current = {}
        for finding in report.findings:
            identity = getattr(finding, "finding_id", None)
            if not identity:
                identity = _finding_identity(finding)
            current[identity] = finding

        new = []
        persistent = []
        recurring = []
        resolved = []
        for identity in sorted(current):
            finding = current[identity]
            previous = self._finding_history.get(identity)
            was_active = identity in self._active_finding_ids
            if previous is None:
                status = "new"
                observations = 1
                first_seen = simulation_tick
                first_seen_world = world_tick
            else:
                status = "persistent" if was_active else "recurring"
                observations = previous.observations + 1
                first_seen = previous.first_seen_tick
                first_seen_world = previous.first_seen_world_tick
            history = FindingHistory(
                finding_id=identity,
                category=finding.category,
                subject=finding.subject,
                severity=getattr(finding, "severity", "info"),
                message=finding.message,
                evidence=_freeze(getattr(finding, "evidence", ())),
                first_seen_tick=first_seen,
                last_seen_tick=simulation_tick,
                first_seen_world_tick=first_seen_world,
                last_seen_world_tick=world_tick,
                observations=observations,
                status=status,
            )
            self._finding_history[identity] = history
            {"new": new, "persistent": persistent, "recurring": recurring}[status].append(history)

        for identity in sorted(self._active_finding_ids - set(current)):
            previous = self._finding_history[identity]
            history = replace(previous, status="resolved")
            self._finding_history[identity] = history
            resolved.append(history)

        self._active_finding_ids = set(current)
        return GovernorHistorySummary(
            simulation_tick=simulation_tick,
            world_tick=world_tick,
            new=tuple(new),
            persistent=tuple(persistent),
            recurring=tuple(recurring),
            resolved=tuple(resolved),
        )

    def _snapshot_governor_report(self, report):
        findings = tuple(sorted((
            str(getattr(item, "finding_id", _finding_identity(item))),
            str(item.category),
            str(getattr(item, "severity", "info")),
            str(item.subject),
            str(item.message),
            _freeze(getattr(item, "evidence", ())),
            str(getattr(item, "temporal_status", "current")),
        ) for item in report.findings))
        resources = _freeze(getattr(report, "resources", ()))
        environment = _freeze(getattr(report, "environment", ()))
        markets = _freeze(getattr(report, "market_activity", ()))
        construction_statuses = _freeze(
            getattr(report, "construction_statuses", ())
        )
        return GovernorReportSnapshot(
            sequence=len(self._governor_reports),
            simulation_tick=getattr(report, "tick", 0),
            world_tick=getattr(report, "world_tick", 0),
            population=getattr(report, "population", 0),
            living_population=getattr(report, "living_population", 0),
            births=getattr(report, "births", 0),
            deaths=getattr(report, "deaths", 0),
            resources=resources,
            building_count=getattr(report, "building_count", 0),
            business_count=getattr(report, "business_count", 0),
            vehicle_count=getattr(report, "vehicle_count", 0),
            construction_project_count=getattr(report, "construction_project_count", 0),
            construction_statuses=construction_statuses,
            environment=environment,
            market_activity=markets,
            completed_market_ticks=getattr(report, "completed_market_ticks", 0),
            findings=findings,
        )

    def _record_engine_event(self, record, simulation_tick, world_tick, identity):
        sequence = record.sequence
        key = (identity, "simulation_engine", sequence)
        if key in self._event_keys:
            return
        self._event_keys.add(key)
        event_identity = json.dumps(
            (identity, "simulation_engine", sequence),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(event_identity.encode("utf-8")).hexdigest()[:16]
        source_tick = getattr(record, "source_tick", None)
        if (
            not isinstance(source_tick, int)
            or isinstance(source_tick, bool)
            or source_tick < 0
        ):
            source_tick = None
        related = getattr(record, "related_citizen_ids", ())
        if not isinstance(related, (tuple, list, set)):
            related = ()
        self._events.append(HistoricalEvent(
            event_id=f"obs-{digest}",
            sequence=len(self._events),
            event_type=record.event_type,
            subject_id=identity[0],
            subject_incarnation=identity[1],
            subject_name=str(getattr(record, "subject_name", "")),
            description=record.description,
            source="simulation_engine",
            source_index=sequence,
            event_tick=source_tick,
            observed_simulation_tick=simulation_tick,
            observed_world_tick=world_tick,
            related_citizen_ids=tuple(sorted(str(value) for value in related)),
        ))

    def _identity_for(self, citizen, simulation=None):
        known = self._citizen_instances.get(citizen)
        if known is not None:
            return known
        citizen_id = str(citizen.citizen_id)
        if simulation is not None and hasattr(simulation, "get_citizen_incarnation"):
            incarnation = simulation.get_citizen_incarnation(citizen)
        else:
            incarnation = self._next_citizen_incarnation.get(citizen_id, 0) + 1
        self._next_citizen_incarnation[citizen_id] = max(
            incarnation, self._next_citizen_incarnation.get(citizen_id, 0)
        )
        identity = (citizen_id, incarnation)
        self._citizen_instances[citizen] = identity
        return identity

    def _archive_citizen(
        self, citizen, tick, world_tick, identity, known_lifecycle_transitions
    ):
        citizen_id, incarnation = identity
        previous = self._citizens.get(identity)
        if previous is None:
            self._citizen_first_seen[identity] = tick
        elif previous.life_stage != citizen.life_stage:
            description = (
                f"Life stage changed from {previous.life_stage} to {citizen.life_stage}."
            )
            if (identity, description) not in known_lifecycle_transitions:
                self._record(
                    citizen,
                    "lifecycle_state",
                    len(self._world_snapshots),
                    description,
                    "life_stage_transition",
                    None,
                    tick,
                    world_tick,
                    self._related_citizen_ids(citizen),
                    identity,
                )
        parents = tuple(sorted(str(value) for value in citizen.get_parents()))
        children = tuple(sorted(str(value) for value in citizen.get_children()))
        relationships = tuple(sorted(
            (str(value.get("citizen_id")), str(value.get("type", "")))
            for value in citizen.relationships
            if isinstance(value, dict) and value.get("citizen_id") is not None
        ))
        self._citizens[identity] = CitizenArchive(
            citizen_id=citizen_id,
            incarnation=incarnation,
            name=str(citizen.name),
            age=_freeze(citizen.age),
            generation=_freeze(citizen.generation),
            life_stage=citizen.life_stage,
            lifecycle_state=_freeze(citizen.lifecycle_state),
            parents=parents,
            children=children,
            relationships=relationships,
            first_observed_tick=self._citizen_first_seen[identity],
            last_observed_tick=tick,
        )

    @staticmethod
    def _related_citizen_ids(citizen):
        related = set(citizen.get_parents()) | set(citizen.get_children())
        related.update(
            relationship["citizen_id"]
            for relationship in citizen.relationships
            if isinstance(relationship, dict)
            and relationship.get("citizen_id") is not None
        )
        return tuple(sorted(str(value) for value in related))

    def _record(
        self, citizen, source, source_index, description, event_type,
        event_tick, simulation_tick, world_tick, related, identity=None,
    ):
        citizen_id = str(citizen.citizen_id)
        identity = identity or self._identity_for(citizen)
        key = (identity, source, source_index)
        if key in self._event_keys:
            return
        self._event_keys.add(key)
        event_identity = json.dumps(
            (identity, source, source_index), ensure_ascii=False, separators=(",", ":")
        )
        digest = hashlib.sha256(event_identity.encode("utf-8")).hexdigest()[:16]
        self._events.append(HistoricalEvent(
            event_id=f"obs-{digest}",
            sequence=len(self._events),
            event_type=event_type,
            subject_id=citizen_id,
            subject_incarnation=identity[1],
            subject_name=str(citizen.name),
            description=description,
            source=source,
            source_index=source_index,
            event_tick=event_tick,
            observed_simulation_tick=simulation_tick,
            observed_world_tick=world_tick,
            related_citizen_ids=related,
        ))


def _finding_identity(finding):
    """Fallback stable key for compatible report-like finding objects."""
    values = (
        finding.category,
        finding.subject,
        getattr(finding, "severity", "info"),
        finding.message,
    )
    payload = "|".join(str(value) for value in values)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"gov-{digest}"


def _entity_id(entity):
    if entity is None:
        return None
    for attribute in ("citizen_id", "business_id", "building_id", "vehicle_id"):
        identity = getattr(entity, attribute, None)
        if identity is not None:
            return str(identity)
    return None


def _freeze(value):
    """Convert supported scalar/container state into nested immutable values."""
    if isinstance(value, dict):
        return tuple(sorted(
            (str(key), _freeze(item)) for key, item in value.items()
        ))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze(item) for item in value), key=repr))
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    value_type = type(value)
    return f"<{value_type.__module__}.{value_type.__qualname__}>"
